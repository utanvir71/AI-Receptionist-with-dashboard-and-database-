"""Notification boundary behavior."""

from datetime import datetime
from email.message import EmailMessage

from app.core.config import Settings
from app.models.resources import SeatingPreference
from app.schemas.reservations import ManagerFollowupRequest
from app.services.calendar_service import ReservationRecord
from app.services.notification_service import (
    NoOpReservationNotifier,
    SmtpManagerEmailNotifier,
    TwilioReservationNotifier,
    build_manager_email_notifier,
    build_reservation_notifier,
    cancellation_sms_body,
    confirmation_sms_body,
    modification_sms_body,
)
from app.utils.time import SEOUL_TZ


def seoul_datetime(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=SEOUL_TZ)


def reservation_record(**overrides: object) -> ReservationRecord:
    values = {
        "customer_name": "Jane Kim",
        "phone": "+821012345678",
        "party_size": 4,
        "start": seoul_datetime(2026, 7, 1, 18),
        "end": seoul_datetime(2026, 7, 1, 19, 40),
        "seating_preference": SeatingPreference.NO_PREFERENCE,
        "resource_ids": ("table_3",),
        "id": "reservation-123",
    }
    values.update(overrides)
    return ReservationRecord(**values)


class FakeTwilioMessages:
    def __init__(self) -> None:
        self.created: list[dict[str, object]] = []

    def create(self, **kwargs: object) -> object:
        self.created.append(kwargs)
        return object()


class FakeTwilioClient:
    def __init__(self) -> None:
        self.messages = FakeTwilioMessages()


class FakeSMTP:
    instances: list["FakeSMTP"] = []

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.started_tls = False
        self.login_calls: list[tuple[str, str]] = []
        self.sent_messages: list[EmailMessage] = []
        FakeSMTP.instances.append(self)

    def __enter__(self) -> "FakeSMTP":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def starttls(self) -> None:
        self.started_tls = True

    def login(self, username: str, password: str) -> None:
        self.login_calls.append((username, password))

    def send_message(self, message: EmailMessage) -> None:
        self.sent_messages.append(message)


def test_sms_templates_use_short_english_copy() -> None:
    record = reservation_record()

    assert (
        confirmation_sms_body(record)
        == "Confirmed: Your ABCD Steakhouse Gangnam reservation is confirmed for 2026-07-01 "
        "at 18:00 for 4 guests."
    )
    assert (
        modification_sms_body(record)
        == "Updated: Your ABCD Steakhouse Gangnam reservation is updated to 2026-07-01 "
        "at 18:00 for 4 guests."
    )
    assert (
        cancellation_sms_body(record)
        == "Cancelled: Your ABCD Steakhouse Gangnam reservation for 2026-07-01 "
        "at 18:00 has been cancelled."
    )


def test_twilio_reservation_notifier_sends_confirmation_sms() -> None:
    client = FakeTwilioClient()
    notifier = TwilioReservationNotifier(client=client, from_number="+15551234567")

    notifier.send_confirmation(reservation_record())

    assert client.messages.created == [
        {
            "from_": "+15551234567",
            "to": "+821012345678",
            "body": (
                "Confirmed: Your ABCD Steakhouse Gangnam reservation is confirmed for "
                "2026-07-01 "
                "at 18:00 for 4 guests."
            ),
        }
    ]


def test_build_reservation_notifier_uses_noop_when_twilio_config_is_missing() -> None:
    notifier = build_reservation_notifier(Settings(_env_file=None))

    assert isinstance(notifier, NoOpReservationNotifier)
    notifier.send_confirmation(reservation_record())
    notifier.send_modification(reservation_record())
    notifier.send_cancellation(reservation_record())


def test_manager_email_notifier_sends_failed_transfer_details() -> None:
    FakeSMTP.instances.clear()
    notifier = SmtpManagerEmailNotifier(
        smtp_host="smtp.example.com",
        smtp_port=587,
        smtp_username="smtp-user",
        smtp_password="smtp-pass",
        smtp_from_email="receptionist@abcd-steakhouse.example",
        manager_email="manager@abcd-steakhouse.example",
        smtp_factory=FakeSMTP,
    )

    notifier.send_manager_followup(
        ManagerFollowupRequest(
            customer_name="Jane Kim",
            phone="+821012345678",
            party_size=6,
            reservation_start=seoul_datetime(2026, 7, 1, 18),
            reason="manager transfer failed",
            notes="Caller asked for whole restaurant booking.",
        )
    )

    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.example.com"
    assert smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.login_calls == [("smtp-user", "smtp-pass")]
    assert len(smtp.sent_messages) == 1
    message = smtp.sent_messages[0]
    assert message["To"] == "manager@abcd-steakhouse.example"
    assert message["From"] == "receptionist@abcd-steakhouse.example"
    assert message["Subject"] == "ABCD Steakhouse manager follow-up: manager transfer failed"
    assert "Customer: Jane Kim" in message.get_content()
    assert "Reservation start: 2026-07-01T18:00:00+09:00" in message.get_content()
    assert "Caller asked for whole restaurant booking." in message.get_content()


def test_build_manager_email_notifier_uses_noop_when_smtp_config_is_missing() -> None:
    notifier = build_manager_email_notifier(Settings(_env_file=None))

    notifier.send_manager_followup(
        ManagerFollowupRequest(
            customer_name="Jane Kim",
            phone="+821012345678",
            reason="manager transfer failed",
        )
    )
