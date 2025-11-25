# Coding Standards & Consistency

## Style

- Follow **PEP 8** for Python and Django conventions (snake_case names, 79–100 char lines, docstrings for public helpers).
- Type hints are encouraged for new modules/services, especially shared utilities.
- Imports use the standard order: stdlib, third-party, then local modules.

## Django / DRF conventions

- Views should inherit from DRF viewsets or APIViews. Keep business logic in services/helpers.
- Serializers own validation; use shared validators (e.g., `procurement_app.validators.validate_document`) instead of ad‑hoc checks.
- Always register throttles/logging/context middleware when adding new endpoints.
- Prefer `reverse("namespace:view-name")` in tests and code instead of hard-coded paths.

## Tooling

- Before committing:  
  `python manage.py check --deploy`  
  `python manage.py test tests`
- Optional linters: install `ruff`/`flake8` locally and run on the `accounts/`, `procurement_app/`, and `core/` packages.
- Keep migrations clean using `python manage.py makemigrations --check --dry-run`.

## Documentation

- Update `README.md` when setup steps change.  
- Add/extend `docs/MAINTENANCE.md` when you introduce new architectural components or workflows.

These practices keep the codebase predictable and reviewer-friendly while scaling the project.
