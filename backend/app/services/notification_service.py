"""SMS and manager email notification boundary."""

from __future__ import annotations

from collections.abc import Callable
from email.message import EmailMessage
import smtplib
from typing import Any, Protocol

from app.core.config import Settings
from app.schemas.reservations import ManagerFollowupRequest
from app.services.calendar_service import ReservationRecord


class ReservationNotifier(Protocol):
    """Notification operations used after reservation changes."""

    def send_confirmation(self, record: ReservationRecord) -> None:
        """Send a reservation confirmation message."""
        ...

    def send_modification(self, record: ReservationRecord) -> None:
        """Send a reservation modification message."""
        ...

    def send_cancellation(self, record: ReservationRecord) -> None:
        """Send a reservation cancellation message."""
        ...


class ManagerEmailNotifier(Protocol):
    """Notification operation used after failed manager transfer."""

    def send_manager_followup(self, request: ManagerFollowupRequest) -> None:
        """Send manager follow-up details."""
        ...


class NoOpReservationNotifier:
    """Reservation notifier used when SMS credentials are not configured."""

    def send_confirmation(self, record: ReservationRecord) -> None:
        return None

    def send_modification(self, record: ReservationRecord) -> None:
        return None

    def send_cancellation(self, record: ReservationRecord) -> None:
        return None


class NoOpManagerEmailNotifier:
    """Manager email notifier used when SMTP credentials are not configured."""

    def send_manager_followup(self, request: ManagerFollowupRequest) -> None:
        return None


class TwilioReservationNotifier:
    """Send customer reservation SMS messages through Twilio."""

    def __init__(self, *, client: Any, from_number: str) -> None:
        self._client = client
        self._from_number = from_number

    def send_confirmation(self, record: ReservationRecord) -> None:
        self._send_sms(to=record.phone, body=confirmation_sms_body(record))

    def send_modification(self, record: ReservationRecord) -> None:
        self._send_sms(to=record.phone, body=modification_sms_body(record))

    def send_cancellation(self, record: ReservationRecord) -> None:
        self._send_sms(to=record.phone, body=cancellation_sms_body(record))

    def _send_sms(self, *, to: str, body: str) -> None:
        self._client.messages.create(
            from_=self._from_number,
            to=to,
            body=body,
        )


class SmtpManagerEmailNotifier:
    """Send manager follow-up emails through SMTP."""

    def __init__(
        self,
        *,
        smtp_host: str,
        smtp_port: int,
        smtp_username: str,
        smtp_password: str,
        smtp_from_email: str,
        manager_email: str,
        smtp_factory: Callable[[str, int], Any] = smtplib.SMTP,
    ) -> None:
        self._smtp_host = smtp_host
        self._smtp_port = smtp_port
        self._smtp_username = smtp_username
        self._smtp_password = smtp_password
        self._smtp_from_email = smtp_from_email
        self._manager_email = manager_email
        self._smtp_factory = smtp_factory

    def send_manager_followup(self, request: ManagerFollowupRequest) -> None:
        message = EmailMessage()
        message["To"] = self._manager_email
        message["From"] = self._smtp_from_email
        message["Subject"] = f"ABCD Steakhouse manager follow-up: {request.reason}"
        message.set_content(self._manager_email_body(request))

        with self._smtp_factory(self._smtp_host, self._smtp_port) as smtp:
            smtp.starttls()
            if self._smtp_username and self._smtp_password:
                smtp.login(self._smtp_username, self._smtp_password)
            smtp.send_message(message)

    def _manager_email_body(self, request: ManagerFollowupRequest) -> str:
        lines = [
            "Manager follow-up is required.",
            "",
            f"Reason: {request.reason}",
            f"Customer: {request.customer_name}",
            f"Phone: {request.phone}",
        ]
        if request.party_size is not None:
            lines.append(f"Party size: {request.party_size}")
        if request.reservation_start is not None:
            lines.append(f"Reservation start: {request.reservation_start.isoformat()}")
        if request.notes:
            lines.append(f"Notes: {request.notes}")
        return "\n".join(lines)


def confirmation_sms_body(record: ReservationRecord) -> str:
    """Return the short English confirmation SMS body."""
    return (
        "Confirmed: Your ABCD Steakhouse Gangnam reservation is confirmed for "
        f"{_sms_date(record)} at {_sms_time(record)} for {record.party_size} guests."
    )


def modification_sms_body(record: ReservationRecord) -> str:
    """Return the short English modification SMS body."""
    return (
        "Updated: Your ABCD Steakhouse Gangnam reservation is updated to "
        f"{_sms_date(record)} at {_sms_time(record)} for {record.party_size} guests."
    )


def cancellation_sms_body(record: ReservationRecord) -> str:
    """Return the short English cancellation SMS body."""
    return (
        "Cancelled: Your ABCD Steakhouse Gangnam reservation for "
        f"{_sms_date(record)} at {_sms_time(record)} has been cancelled."
    )


def build_reservation_notifier(settings: Settings) -> ReservationNotifier:
    """Build the reservation SMS notifier from settings."""
    if not (
        settings.twilio_account_sid
        and settings.twilio_auth_token
        and settings.twilio_from_number
    ):
        return NoOpReservationNotifier()

    from twilio.rest import Client

    return TwilioReservationNotifier(
        client=Client(settings.twilio_account_sid, settings.twilio_auth_token),
        from_number=settings.twilio_from_number,
    )


def build_manager_email_notifier(settings: Settings) -> ManagerEmailNotifier:
    """Build the manager email notifier from settings."""
    if not (settings.smtp_host and settings.smtp_from_email and settings.manager_email):
        return NoOpManagerEmailNotifier()

    return SmtpManagerEmailNotifier(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        smtp_from_email=settings.smtp_from_email,
        manager_email=settings.manager_email,
    )


def _sms_date(record: ReservationRecord) -> str:
    return record.start.strftime("%Y-%m-%d")


def _sms_time(record: ReservationRecord) -> str:
    return record.start.strftime("%H:%M")
