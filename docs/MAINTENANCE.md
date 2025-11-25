# Maintenance & Extensibility

## Layered architecture

```
core/                 Settings, middleware, shared utilities, health checks
accounts/             Authentication, auth tokens, user profiles & permissions
procurement_app/      Purchase requests, workflow actions, finance views
documents/            Extraction & validation services (AI + OCR)
tests/                API tests that exercise the major user journeys
```

### Adding a new feature

1. **Model + serializer** – add or extend models in the relevant app, then expose the fields through a DRF serializer.
2. **Service layer** – business rules live inside `procurement_app/services/` or a small helper rather than directly inside views. This keeps viewsets thin.
3. **API surface** – expose logic through viewsets/actions and register them in `urls.py`. Reuse throttles (`core/throttling.py`), request-context logging, and validators to stay consistent.
4. **Observability** – emit a security/business log via `core.security_logging` for critical actions, and add metrics if the feature needs dashboard visibility.
5. **Tests** – add focused tests inside `tests/` (API, serializer, or model tests). Run `python manage.py test tests`.

### Configuration

- All sensitive values come from `.env`. Use the helpers in `core/utils/config.py` (`env_bool`, `env_list`, etc.) when introducing new settings.
- `python manage.py check --deploy` should stay clean; if you add middleware or security-critical settings, update the check list accordingly.

### Background processing

AI extraction runs synchronously today. If you offload to Celery/queues later, keep the same structured logging interface so Kibana/Sentry stays useful.

## Operational playbook

- **Startup**: `pip install -r requirements.txt`, copy `.env.example`, run migrations, `python manage.py runserver`.
- **Logs**: check `logs/p2p.log` (JSON) or the console (color) for troubleshooting.
- **Metrics**: scrape `/metrics` with Prometheus or view via `docker-compose up es kibana filebeat` to get ELK locally.
- **Health**: load balancers hit `/health/`.
