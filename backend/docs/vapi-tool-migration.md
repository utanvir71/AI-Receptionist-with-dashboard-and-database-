# Vapi Tool Migration Notes

Status: planning/setup note.

## Current Vapi Tools

The assistant currently has these tools connected:

- `abcd-steakhouse-knowledge`
- `end-call`
- `create_restaurant_reservation`

The first two can stay.

The existing `create_restaurant_reservation` tool was created for the old Make.com workflow. It currently records a pending reservation request and does not guarantee table availability. That behavior no longer matches the production V1 plan, because the new backend must check table/room availability and confirm the booking automatically.

## What To Keep

### `abcd-steakhouse-knowledge`

Keep this tool connected.

Use it for restaurant-information questions:

- hours
- menu
- prices
- parking
- directions
- seating rules
- private-room policy
- events
- corkage
- walk-ins
- pets

### `end-call`

Keep this tool connected.

The prompt already says to use it only when the caller is finished, says goodbye, or asks to hang up.

## What To Replace

### Old `create_restaurant_reservation`

Replace or repoint this tool after the FastAPI backend is running.

Current issue:

- description says it records a pending request
- it points to a Make.com webhook
- it does not check Google Calendar table conflicts
- it does not assign internal tables/rooms
- it does not support modify/cancel/search
- it does not match the final prompt, which expects confirmed reservations

## Production V1 Tool Set

Create these custom tools in Vapi:

- `check_availability`
- `create_reservation`
- `search_reservation`
- `modify_reservation`
- `cancel_reservation`
- optional: `manager_followup`

Manager live transfer should use Vapi's built-in transfer call tool.

## Tool Naming

Use the new names above instead of the old Make.com name.

The prompt in `docs/vapi-receptionist-prompt.md` already uses these new tool names:

- `check_availability`
- `create_reservation`
- `search_reservation`
- `modify_reservation`
- `cancel_reservation`

If you keep the old tool name temporarily, the prompt must be changed back to match it. For production, the cleaner path is to rename/create tools with the final names.

## Server URL During Local Development

During local development:

1. Run FastAPI locally, probably on port `8000`.
2. Expose it with ngrok.
3. Use the ngrok HTTPS URL in Vapi tool server settings.

Example Vapi server URLs:

```text
https://<ngrok-domain>/vapi/reservations/check-availability
https://<ngrok-domain>/vapi/reservations/create
https://<ngrok-domain>/vapi/reservations/search
https://<ngrok-domain>/vapi/reservations/modify
https://<ngrok-domain>/vapi/reservations/cancel
```

Exact paths can be adjusted during coding, but Vapi and FastAPI must match exactly.

## Authentication

The old Make.com tool has no authentication in the screenshot.

For the FastAPI backend, add an HTTP header in each Vapi custom tool:

```text
Authorization: Bearer <VAPI_TOOL_SECRET>
```

The backend will define `VAPI_TOOL_SECRET` in the env file. Vapi should use the same value as the header secret.

## Recommended Tool Schemas

### `check_availability`

Purpose: check whether a requested reservation can be booked and return caller-safe fallback options if not.

Parameters:

- `party_size` number, required
- `reservation_start` string, required, ISO 8601 with Seoul offset
- `seating_preference` string, required: `window_side`, `private_room`, `no_preference`, `general_note`
- `notes` string, optional

### `create_reservation`

Purpose: create a confirmed reservation after caller confirms the final summary.

Parameters:

- `customer_name` string, required
- `phone` string, required
- `party_size` number, required
- `reservation_start` string, required, ISO 8601 with Seoul offset
- `seating_preference` string, required
- `notes` string, optional
- `allergy_notes` string, optional
- `call_id` string, optional

### `search_reservation`

Purpose: find an existing reservation before modification or cancellation.

Parameters:

- `phone` string, required
- `reservation_start` string, required, ISO 8601 with Seoul offset
- `customer_name` string, optional

### `modify_reservation`

Purpose: update an existing reservation after lookup and caller confirmation.

Parameters:

- `phone` string, required
- `original_reservation_start` string, required
- `new_reservation_start` string, optional
- `new_party_size` number, optional
- `new_customer_name` string, optional
- `new_phone` string, optional
- `new_seating_preference` string, optional
- `new_notes` string, optional
- `new_allergy_notes` string, optional

### `cancel_reservation`

Purpose: mark an existing reservation as cancelled after caller confirmation.

Parameters:

- `phone` string, required
- `reservation_start` string, required
- `customer_name` string, optional

### `manager_followup`

Purpose: email manager when transfer fails or manager follow-up is needed.

Parameters:

- `customer_name` string, required
- `phone` string, required
- `party_size` number, optional
- `reservation_start` string, optional
- `reason` string, required
- `notes` string, optional

## Response Body Variables

In Vapi, configure response variables only if needed by the prompt.

Useful response fields:

- `status`
- `message`
- `reservation_id`
- `reservation_start`
- `reservation_end`
- `available`
- `alternatives`
- `reason`

Do not expose internal fields like `assigned_resource` to the caller.

The backend can return internal data, but the prompt must not read it aloud.

## Tool Descriptions

Use descriptions that match production behavior.

For `create_reservation`, use:

```text
Creates a confirmed restaurant reservation after the caller confirms all details. The backend checks availability, assigns an internal table or room, records the booking, and sends SMS confirmation.
```

Do not use the old wording:

```text
Record a pending restaurant reservation request...
```

That wording is now wrong.

## Migration Steps

1. Keep `abcd-steakhouse-knowledge`.
2. Keep `end-call`.
3. Build and run the FastAPI backend locally.
4. Start ngrok for the FastAPI port.
5. Create the new Vapi custom tools with the new names.
6. Point each tool to the matching ngrok endpoint.
7. Add the authorization header.
8. Replace the assistant prompt with `docs/vapi-receptionist-prompt.md`.
9. Test one call flow at a time:
   - availability only
   - create reservation
   - unavailable fallback
   - modify reservation
   - cancel reservation
   - private room
   - manager transfer
10. Remove the old Make.com `create_restaurant_reservation` tool after the new create flow works.

## Temporary Compatibility Option

If you want to keep the old `create_restaurant_reservation` tool during early testing, we can make the FastAPI backend expose a compatibility endpoint with that old name.

This is not recommended for final production because the prompt and tool names become confusing. The cleaner production setup is the new separated tool set.
