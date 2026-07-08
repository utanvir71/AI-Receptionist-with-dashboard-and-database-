# AI Receptionist V1 Plan

Status: evolving planning document.

## Goal

Build a production-level AI phone receptionist for ABCD Steakhouse Gangnam. Customers call the SIP number, Vapi answers the call, and a custom FastAPI backend handles reservation availability, booking, modification, cancellation, notifications, and manager escalation.

V1 uses Google Calendar as the reservation source of truth. Later versions can add a database for reservations, menu, events, restaurant settings, CRM data, and operational dashboards.

## Confirmed Decisions

- Backend stack: Python FastAPI.
- Vapi calls backend tool endpoints.
- Google Calendar is the V1 reservation source of truth.
- Use one shared reservation calendar.
- Store assigned table or room internally in calendar event metadata.
- Do not tell callers the table or room number.
- Reservations are confirmed immediately when backend availability checks pass.
- Every reservation blocks exactly 100 minutes.
- Customer SMS messages are English only for V1.
- Customer confirmations, modifications, and cancellations are sent by SMS using Twilio international SMS.
- Manager failed-transfer follow-up is sent by email.
- No call transcript or recording link in manager email for V1.
- V1 uses only Google Calendar for staff operations. No staff dashboard or manual override UI in V1.
- Development runs on a local FastAPI server exposed through ngrok.
- Use a separate test Google Calendar first. Test calendar name: `ABCD Steakhouse Demo Reservations`.
- Manager transfer number, manager email, Google Calendar ID, Twilio credentials, and other secrets will be supplied through environment variables during coding.

## Reservation Hours

- Restaurant hours: every day, 11:00 to 21:00.
- Kitchen closes and last order is 20:00.
- Allowed reservation start windows:
  - 11:00 to 14:30
  - 17:00 to 19:30
- No reservation starts from 14:31 to 16:59.
- Any exact minute is allowed inside the valid windows. There are no fixed 15-minute or 30-minute intervals.
- If a requested time is outside the valid window, offer nearby valid times if available.

## Vapi Conversation Behavior

- Ask one question at a time.
- For every booking, collect:
  - customer name
  - phone number
  - party size
  - reservation date
  - reservation time
  - seating preference
- Seating preference choices:
  - window-side
  - private room
  - no preference
  - general note
- Allergy or special notes are captured only if the caller brings them up.
- Never guarantee that food is allergen-free.
- For allergy notes, say the restaurant team must verify ingredients and cross-contamination risk.
- Before final booking, summarize the exact date, time, name, phone number, party size, and seating preference.
- Tell the caller that reservation updates will be sent by SMS to the provided phone number.

## Backend Tool Endpoints

Planned separate endpoints:

- `check_availability`
- `create_reservation`
- `search_reservation`
- `modify_reservation`
- `cancel_reservation`

Backend responses should use caller-safe statuses such as:

- `available`
- `confirmed`
- `unavailable`
- `not_found`
- `ambiguous`
- `invalid_request`
- `outside_reservation_hours`
- `conflict`
- `manager_required`
- `error`

The backend may return internal resource IDs, but the Vapi prompt must not reveal them to callers.

## Google Calendar Event Structure

Each confirmed booking creates one event with:

- title format: `{party_size} guests - {customer_name}`, for example `4 guests - Tanvir`
- customer name
- phone number in E.164 format
- party size
- reservation start
- reservation end
- duration minutes: 100
- seating preference
- internal resource ID
- resource type
- customer notes
- allergy notes
- Vapi call ID
- SMS status
- booking status

Use Google Calendar `extendedProperties.private` for machine-readable metadata. The event description should remain human-readable for restaurant staff.

Recommended booking statuses:

- `confirmed`
- `modified`
- `cancelled`
- `sms_failed`
- `needs_manager_followup`

Cancelled reservations should stay in Google Calendar as non-blocking records instead of being deleted.

## Conflict Rule

A resource is unavailable when an existing non-cancelled event overlaps the requested 100-minute block:

```text
existing.start < requested.end AND existing.end > requested.start
```

For modification, exclude the caller's current reservation from the conflict check.

## Table Allocation Rules

- The system uses the smallest suitable regular table first.
- If multiple suitable regular tables have the same capacity, prefer window-side first.
- Private rooms are only used when the caller requests a private room.
- Private rooms are not fallback seating for normal reservations.
- The caller never hears the internal table or room number.

Regular tables:

- Table 1: max 3
- Table 2: max 3
- Table 1 + Table 2: max 8
- Table 3: max 4
- Table 4: max 4
- Table 5: max 3
- Table 6: max 3
- Table 7: max 6
- Table 10: max 6
- Table 11: max 6
- Table 12: max 6
- Table 13: max 3
- Table 14: max 3
- Table 15: max 4
- Table 16: max 4

Only Table 1 and Table 2 can be combined. No other regular table combinations are allowed.

Regular seating rules:

- 1 to 6 guests: regular table only, unless the caller requests a private room.
- 7 to 8 guests: Table 1 + Table 2 only for regular seating.
- 9 to 12 guests: ask whether the caller wants a private room. If not, say regular seating is not possible.
- More than 12 guests: collect details and transfer to manager.

## Window-Side Rules

Window-side resources:

- Tables 1 to 7
- Room 5

If the caller requests window-side seating and none is available at the requested time, say window-side is unavailable and ask whether they prefer:

- same time with another seat
- nearby time with window-side seating

Do not loosen the seating preference unless the caller agrees.

## Private Room Rules

Private rooms:

- Room 1: max 6
- Room 2: max 6
- Room 3: max 6
- Room 4: max 5
- Room 5: max 6
- Room 1 + Room 2: max 12

Private-room requirements:

- 1 to 6 guests: steak order required, minimum 320,000 won
- 7 to 8 guests: steak order required, minimum 420,000 won
- 9 to 12 guests: steak order required, minimum 620,000 won

The AI must explain the requirement and ask whether the caller agrees before checking or confirming a private-room booking.

If private room is unavailable, offer up to 3 nearby same-day private-room times within plus/minus 2 hours.

## Availability Fallback Rules

If the requested time is unavailable:

- Offer up to 3 nearby same-day options within plus/minus 2 hours.
- Preserve seating preference unless the caller agrees to change it.
- If the caller rejects those options, ask for one preferred date/time and check again.
- Do not keep looping through repeated option lists.

Loop limits:

- one fallback list per failed requested time
- one corrected retry for reservation lookup
- two invalid date/time retries before manager follow-up

## Modify Reservation Flow

1. Ask for phone number.
2. Ask for original reservation date/time.
3. Search by phone and date/time.
4. Ask what the caller wants to change.
5. If date, time, party size, or seating preference changes, rerun availability and allocation.
6. If only name, phone, or notes change, keep the same internal resource.
7. If the requested modification is unavailable, offer nearby valid options.
8. If no option is accepted, keep the original reservation unchanged unless caller explicitly cancels.
9. Send updated details by SMS after successful modification.

## Cancel Reservation Flow

1. Ask for phone number.
2. Ask for reservation date/time.
3. Search by phone and date/time.
4. Confirm cancellation with the caller.
5. Mark the event as `cancelled`.
6. Make cancelled events non-blocking for availability.
7. Send cancellation SMS.

## Manager Escalation

Use Vapi transfer for:

- parties over 12
- whole-restaurant booking requests
- caller asks for manager/staff
- repeated backend/tool failure
- policy unavailable in the KB

Before transfer, collect:

- customer name
- phone number
- party size
- requested date/time
- reason for manager
- notes

If transfer fails, email the manager with the collected details.

## Notifications

Customer SMS:

- sent through Twilio international SMS
- English only for V1
- use E.164 phone number format
- keep messages short

Default short SMS templates:

- Confirmation: `Confirmed: Your ABCD Steakhouse Gangnam reservation is confirmed for {date} at {time} for {party_size} guests.`
- Modification: `Updated: Your ABCD Steakhouse Gangnam reservation is updated to {date} at {time} for {party_size} guests.`
- Cancellation: `Cancelled: Your ABCD Steakhouse Gangnam reservation for {date} at {time} has been cancelled.`

If SMS fails after the reservation is created, the reservation remains confirmed. The AI still tells the caller the reservation is confirmed. Backend records `sms_failed` in logs only for V1.

Manager email:

- failed transfer follow-up
- backend/system issue requiring manager attention
- no transcript or recording link in V1

## Backend Modules

Planned structure:

- `app/main.py`
- `app/config.py`
- `app/api/vapi_tools.py`
- `app/schemas/reservations.py`
- `app/services/reservation_service.py`
- `app/services/calendar_service.py`
- `app/services/resource_allocator.py`
- `app/services/notification_service.py`
- `app/security/vapi_auth.py`
- `app/utils/time.py`
- `app/utils/idempotency.py`

## Security And Reliability

- Authenticate Vapi tool calls with a bearer token or Vapi request signature if available.
- Validate all inputs with Pydantic.
- Normalize phone numbers to E.164.
- Use Seoul timezone for all validation.
- Do not expose Google Calendar or Twilio raw errors to callers.
- Use structured logs with call ID and request ID.
- Add idempotency protection for duplicate Vapi tool calls.
- Calendar create/update failures should not be reported as confirmed.
- Calendar success plus SMS failure should still be reported as confirmed.

## Later Database Path

V1: Google Calendar only.

V2: Add database as audit/read model:

- reservations
- reservation events
- notification attempts
- restaurant settings
- menu items
- resources
- calls

Later, database can become source of truth and Google Calendar can become a synced staff-facing projection.

## Open Items

- Exact environment variable names will be defined when coding starts.
- Manager transfer phone number or Vapi destination value.
- Manager email address value.
- Twilio sender number and production SMS setup values.
