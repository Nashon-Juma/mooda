# 📘 Project Best Practices

## 1. Project Purpose
Mooda is a Flask-based web application for mood tracking and self-reflection. It enables users to record daily emotional check-ins on a 1–5 scale, write journals, and share progress with a psychologist via a rotating doctor key. It integrates a Hugging Face emotion classifier to analyze free-text inputs and visualizes results client-side. The app uses MySQL for persistence, supports user authentication, and includes optional premium features with Paystack payments and subscription management.

## 2. Project Structure
- Root
  - .env, .example.env — environment configuration
  - Makefile — install, lint, test, DB config, run server
  - requirements.txt — Python dependencies
  - Procfile, runtime.txt — deployment helpers
  - README.md — setup and development docs
  - db_config.py — database setup script
  - tests/ — repo-level tests (e.g., DB smoke test)
  - static/ — frontend assets (css, js, img, audio)
  - templates/ — Jinja2 templates (layout, partials, pages)
  - src/
    - __main__.py — production entry via waitress
    - app.py — Flask app factory and routes
    - validator.py — WTForms validators and forms
    - utils/ — domain and infrastructure modules
      - db_connection/ — pooled DB connector (MySQL)
      - user/, register/, login/ — auth and identity
      - journal/, checkup/, data_summary/ — core domain features
      - emotion/ — emotion history persistence
      - payment/, subscription/ — payments and premium features

Key roles
- src/app.py: request routing, templates, external API calls (HF), session handling, and glue code across domain modules.
- src/__main__.py: runs server in production with waitress.
- src/utils/db_connection/db_connection.py: connection pooling, retry logic, forward-compatible DB API (execute_query, fetch_one, fetch_all) + legacy cursor compatibility (cnx, cursor).
- templates/: Jinja2 pages with shared layout and includes (navbar, footer, etc.).
- static/js/: front-end scripting; note duplication risk with inline scripts in some templates (e.g., analyze.html).

Configuration and environment
- python-dotenv loads .env early in src/app.py.
- Required env: DATABASE_*, APP_SECRET_KEY, APP_PORT, HF_API_TOKEN, optional HF_MODEL, PAYSTACK_PUBLIC_KEY/SECRET, PAYSTACK_WEBHOOK_SECRET, APP_URL, FLASK_ENV.

## 3. Test Strategy
Frameworks and commands
- Unit tests use unittest (Makefile runs coverage with unittest discovery). pytest is available but not used in current tests.
- Linting with flake8 and pylint. Black for formatting (documented in README badges).
- Run: make test dir=./src/utils/<package>

Organization and conventions
- Test files reside alongside modules (e.g., src/utils/<pkg>/test_*.py) and a repo-level tests/test_db.py.
- Naming: test_*.py with unittest.TestCase classes and methods starting with test_.
- Mocking: unittest.mock (MagicMock, patch) to isolate DB calls by patching DBConnection.

Guidelines
- Prefer unit tests for domain modules (User, Register, Login, Journal, Checkup, DataSummary, Emotion, Subscription, Payment). Mock DB and external APIs (requests.post/get for HF/Paystack).
- Keep integration tests separate (e.g., tests/integration/) and guard with env checks; skip if DATABASE_* not configured.
- For DB code, test both forward API (execute_query/fetch_one/fetch_all) and legacy cursor usage where still present.
- For Flask routes, use Flask’s test_client for request/response and session behavior; mock external services.
- Ensure timeouts are set in HTTP tests; simulate HF 401/503, network errors, invalid JSON.
- Track and enforce coverage thresholds where feasible; focus on error paths and input validation.

## 4. Code Style
General
- Python 3.11.
- Use Black for formatting and flake8/pylint for linting (see Makefile). Keep imports grouped and sorted; avoid unused imports.
- Prefer logging over print for diagnostics (logging is already configured in DBConnection; extend to other modules).

Typing
- Gradually add type hints to public functions and class methods. Start with DB wrappers, service classes, and route helpers.

Naming
- Files and functions: snake_case (e.g., try_login, try_journal).
- Classes: PascalCase (User, Register, Login, Journal, Checkup, DataSummary, Emotion, Payment, Subscription, DBConnection).
- Constants: UPPER_SNAKE_CASE.

Docstrings and comments
- Module and public API docstrings are recommended. Use concise, action-focused docstrings and include argument/return semantics.
- Keep inline comments focused on non-obvious intent.

Error and exception handling
- External requests: always use timeouts and handle expected HTTP statuses (app.py already handles 401, 503, >=400 for HF).
- DB code: catch mysql.connector.Error. Return explicit result objects or raise domain exceptions; be consistent.
- Avoid mixing print with flash/log. Use logging and propagate structured errors to callers, then flash in route handlers.
- Prefer early validation and explicit 4xx responses for bad inputs.

Security and auth
- Bcrypt for password hashing (already used). Ensure bytes encoding before bcrypt calls.
- Never log secrets or full tokens. Keep HF_API_TOKEN, Paystack keys in env only.
- Flask secret key must be set via env (APP_SECRET_KEY). Consider enabling CSRF protection for forms.
- Validate and sanitize user input via WTForms; rely on Jinja2 autoescape in templates.

## 5. Common Patterns
- Service classes per domain (User, Journal, Checkup, DataSummary, Emotion, Subscription, Payment) encapsulate DB or external APIs.
- DBConnection provides:
  - Pooled connections and reconnection.
  - Forward API: execute_query, fetch_one, fetch_all (recommended).
  - Legacy compatibility: .cnx and .cursor for existing modules; gradually migrate to forward API.
- Decorators/utilities
  - retry_operation for robust DB actions.
  - premium_required wrapper for route access control.
- External gateway pattern
  - Payment wraps Paystack API calls.
  - Hugging Face inference in app.py is a gateway; consider extracting to a dedicated client module for testability.
- Front-end charts powered by Chart.js with localStorage history.

## 6. Do's and Don'ts
✅ Do
- Centralize configuration via .env and load it once during startup.
- Use DBConnection forward methods; close resources via context managers or .close().
- Use parameterized SQL queries exclusively (already applied) to avoid SQL injection.
- Add timeouts to all HTTP requests; handle known error codes and retry or inform the user appropriately.
- Keep route functions slim; delegate to service classes.
- Write unit tests with mocks for DB and HTTP; add integration tests behind env flags.
- Return consistent JSON structures from API routes; include error objects with status codes.
- Validate user input through WTForms validators defined in src/validator.py.

❌ Don’t
- Don’t store or log secrets/tokens in code or repository.
- Don’t mix print statements with logging for operational messages.
- Don’t perform heavy logic directly in route handlers; don’t call external APIs without timeouts.
- Don’t rely on legacy cursor patterns for new code; avoid raw string interpolations in queries.
- Don’t duplicate front-end JS between inline template scripts and static files; pick one canonical location.

## 7. Tools & Dependencies
Key libraries
- Backend: Flask, Jinja2, Werkzeug, waitress, setproctitle.
- DB: mysql-connector-python, python-dotenv for env, bcrypt for hashing.
- HTTP: requests.
- Validation: WTForms, validate_email.
- Dev: black, flake8, pylint, coverage, unittest (pytest present but not currently used).
- Frontend: Tailwind (CDN), Chart.js (CDN).

Setup
- Python >= 3.11; MySQL available and reachable.
- Commands:
  - Install: make init
  - DB config: make db (runs db_config.py)
  - Run (production/waitress): make run
  - Lint + tests + coverage: make test dir=./src/utils/<package>

Environment variables (examples)
- DATABASE_NAME, DATABASE_HOSTNAME, DATABASE_USER, DATABASE_PASSWORD, DATABASE_PORT (optional)
- APP_SECRET_KEY, APP_PORT
- HF_API_TOKEN (required), HF_MODEL (optional)
- PAYSTACK_PUBLIC_KEY, PAYSTACK_SECRET_KEY, PAYSTACK_WEBHOOK_SECRET (for webhook verification)
- APP_URL (for Paystack callback), FLASK_ENV

## 8. Other Notes
- Database API convergence: Several modules still use legacy .cnx/.cursor while DBConnection provides execute_query/fetch_one/fetch_all. Prefer the forward API in new or refactored code for reliability and consistency.
- Emotion and Subscription schemas: Ensure your actual MySQL schema aligns with the code. The Emotion/Subscription modules refer to tables emotions/subscriptions and a users table in FKs. Confirm your schema uses User (capitalized) with user_id and adjust table/column names accordingly or update code to match your schema.
- External API boundaries: Consider extracting the Hugging Face inference logic from app.py into src/utils/emotion_client.py to improve testability and reuse.
- Front-end duplication: analyze.html contains substantial inline JS while static/js/analyze/DOM.js also implements analysis UI logic. Consolidate into static JS files and import from templates to avoid drift.
- Error UX: Preserve helpful error messages to the UI (e.g., HF 503 warm-up) and surface retry guidance, while logging technical details server-side.
- Sessions: Access session minimally; check is_loggedin() before sensitive routes; prefer decorators for recurring checks (e.g., @login_required, @premium_required).
- Future refactors: consider Flask blueprints to split routes by feature (auth, journal, checkup, analysis, billing) and reduce app.py size.
- LLM code generation hints: follow the existing patterns, keep SQL parameterized, use DBConnection forward methods, don’t introduce new frameworks (ORM/DI) unless explicitly requested, and respect the existing naming and folder conventions.
