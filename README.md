# Smart Procure-to-Pay Backend

This repository hosts the Django + DRF backend for the Procure-to-Pay workflow. It exposes REST APIs for staff, approvers, and finance roles, integrates AI-driven document extraction/validation, and streams structured logs/metrics for observability.

## Quick Start

```bash
python -m venv venv && source venv/Scripts/activate  # Windows PowerShell: .\venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env  # adjust secrets before running
python manage.py migrate
python manage.py runserver
```

Key environment knobs are defined in `.env.example`. The app refuses to start if `DJANGO_SECRET_KEY` is missing to avoid accidental insecure deployments.

## Observability & Security

- `GET /health/` &rarr; DB-aware health probe (200 if healthy, 503 otherwise).
- `GET /metrics` &rarr; Prometheus metrics via `django-prometheus`.
- Structured JSON logs in `logs/p2p.log`, plus colorized console output for local debugging.
- Optional Sentry integration (set `SENTRY_DSN`).
- Outbound email notifications use [Resend](https://resend.com/) &mdash; set `RESEND_API_KEY` and `RESEND_FROM_EMAIL` in `.env` to enable staff/approver notifications.
- Request/receipt uploads validated for type and size; throttles guard login and heavy AI operations.
- **Automation helpers**
  - `scripts/observe.sh` &mdash; hits `/health/`, previews `/metrics`, and tails `logs/p2p.log`.
  - `scripts/run_quality_checks.sh` &mdash; runs Django deploy checks, dry-run migrations, tests, and `ruff`.

## Testing & Quality Gates

```bash
python manage.py test tests           # unit/API tests
python manage.py check --deploy       # Django built-in safety checks
python manage.py makemigrations --check --dry-run  # ensure models/migrations in sync
make lint                             # ruff lint (PEP 8, import order)
# or run the scripted pipeline
./scripts/run_quality_checks.sh
```

## Running with Docker Compose

1. Copy `.env.example` to `.env` and adjust secrets as needed.
2. Build and start the stack (Postgres, Django, Prometheus, Grafana):

```bash
docker compose up --build
```

Services:

- Django API: http://localhost:8000
- Prometheus: http://localhost:9090 (scrapes `/metrics` from Django automatically)
- Grafana: http://localhost:3000 (default credentials admin/admin)

Prometheus reads `prometheus.yml` and targets the `web` service inside the compose network. Grafana stores dashboards in the `grafana_data` volume.

See `docs/MAINTENANCE.md` for architectural notes and `docs/STANDARDS.md` for coding conventions.
