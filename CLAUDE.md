# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bank interest rate lookup website (Vietnamese: "Lãi Suất"). Admin uploads PDF documents organized by categories; public users browse and view them in-browser via PDF.js.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run dev server (localhost:5000, debug mode)
python app.py

# Initialize database with default admin (admin/admin123)
flask --app app init-db

# Run all tests
./venv/bin/pytest tests/ -v

# Run single test file
./venv/bin/pytest tests/test_admin.py -v

# Run single test
./venv/bin/pytest tests/test_admin.py::TestCategoryCRUD::test_create_category -v

# Production
gunicorn app:create_app()
```

## Architecture

**App factory pattern** in `app.py` → `create_app()` initializes extensions, registers blueprints, sets up error handlers and CLI commands.

**Extensions pattern** (`extensions.py`): `db`, `login_manager`, `csrf`, `limiter` are instantiated at module level without an app, then `init_app()` is called inside `create_app()`. All modules import from `extensions.py` to avoid circular imports.

**Two blueprints:**
- `routes_public.py` — homepage, REST API (`/api/categories`, `/api/categories/<id>/pdfs`), PDF serving (`/pdf/<id>`)
- `routes_admin.py` — login/logout, password change, category CRUD, PDF upload/delete. All admin routes require `@login_required`.

**Models** (`models.py`): `Category`, `Pdf`, `Admin`. Category→Pdf is one-to-many with `ondelete="RESTRICT"`. Admin passwords use bcrypt.

**Frontend**: Vanilla JS (ES modules). `app.js` handles public PDF viewer with PDF.js 4.x (`.mjs` imports). `admin.js` handles admin CRUD with fetch API. Both send CSRF token via `X-CSRFToken` header from `<meta name="csrf-token">`.

## Key Implementation Details

- **Database**: SQLite with WAL mode and foreign keys ON. DB file at `instance/database.db`.
- **PDF validation**: `_validate_pdf()` checks both `.pdf` extension AND `%PDF-` magic bytes. Files stored as `{uuid8}-{secure_filename}` in `uploads/`.
- **Rate limiting**: 5 requests/minute on POST `/admin/login` only.
- **Session**: 8-hour permanent sessions. `force_password_change` flag redirects to change-password on first login.
- **Category creation**: `POST /admin/categories` accepts `multipart/form-data` with required `name` and optional PDF file + `pdf_title`.
- **Category update**: `PUT /admin/categories/<id>` accepts JSON with `name` and/or `sort_order`.
- **Max upload size**: 16MB (`MAX_CONTENT_LENGTH`).

## Test Setup

pytest with fixtures in `tests/conftest.py`:
- `app` — fresh app with in-memory SQLite (`sqlite://`) and temp upload dir, CSRF disabled
- `client` — unauthenticated test client
- `auth_client` — pre-authenticated (creates admin user, logs in)

42 tests across 3 files. Category creation tests use `multipart/form-data` (not JSON).

## CSS Design System

Crimson brand (`#AE1C3F` primary). CSS variables defined in `:root`. Viewport-locked layout: containers use `height: 100vh; overflow: hidden` with `min-height: 0` on flex children so only `.pdf-viewer` scrolls. Google Fonts: Playfair Display (display) + Be Vietnam Pro (body).

## Language

All user-facing text is in Vietnamese.
