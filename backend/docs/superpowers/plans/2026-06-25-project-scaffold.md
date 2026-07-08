# Project Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the initial repository structure for the ABCD Steakhouse AI receptionist FastAPI backend without implementing reservation business logic.

**Architecture:** Use a modular FastAPI layout with API routes, schemas, services, core configuration, utilities, and tests separated by responsibility. Keep secrets in a local `.env` file and publish only `.env.example` to GitHub.

**Tech Stack:** Python, FastAPI, Pydantic settings, pytest, Google Calendar API later, Twilio later, ngrok for local Vapi testing.

---

### Task 1: Repository Hygiene

**Files:**
- Create: `.gitignore`
- Create: `.env.example`
- Create: `.env`
- Create: `README.md`

- [x] **Step 1: Add ignore rules**

Ignore Python caches, virtual environments, local secrets, editor files, logs, ngrok output, and `.superpowers/` brainstorming scratch files.

- [x] **Step 2: Add environment templates**

Create `.env.example` for GitHub and `.env` for local values. `.env` is ignored by Git.

- [x] **Step 3: Add project README**

Document setup, local run command, ngrok usage, and key project docs.

### Task 2: FastAPI File Structure

**Files:**
- Create: `app/main.py`
- Create: `app/api/v1/router.py`
- Create: `app/api/v1/vapi_tools.py`
- Create: `app/core/config.py`
- Create: `app/core/logging.py`
- Create: `app/core/security.py`
- Create: `app/models/resources.py`
- Create: `app/schemas/reservations.py`
- Create: `app/services/calendar_service.py`
- Create: `app/services/notification_service.py`
- Create: `app/services/reservation_service.py`
- Create: `app/services/resource_allocator.py`
- Create: `app/utils/time.py`
- Create: package `__init__.py` files

- [x] **Step 1: Create package directories**

Create focused modules for API routing, configuration, schemas, services, resource modeling, and utility helpers.

- [x] **Step 2: Add placeholder modules**

Add docstrings and clear responsibility boundaries only. Reservation logic will be implemented in the next coding phase.

### Task 3: Test And Tooling Structure

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/unit/.gitkeep`
- Create: `tests/integration/.gitkeep`
- Create: `pyproject.toml`

- [x] **Step 1: Add test folders**

Separate unit tests from integration tests.

- [x] **Step 2: Add Python project metadata**

Define dependencies and pytest configuration.

### Task 4: Documentation Structure

**Files:**
- Existing: `docs/ai-receptionist-v1-plan.md`
- Existing: `docs/vapi-receptionist-prompt.md`
- Existing: `docs/vapi-tool-migration.md`
- Existing: `docs/kb/abcd-steakhouse-kb.md`

- [x] **Step 1: Keep planning docs in `docs/`**

Use the existing documents as the source of truth for implementation.

- [x] **Step 2: Reference docs from README**

Make the repo easy to navigate before pushing to GitHub.
