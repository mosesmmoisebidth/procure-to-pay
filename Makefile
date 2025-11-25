SHELL := /bin/bash

.PHONY: lint fmt test check

lint:
	@ruff check .

fmt:
	@ruff check --select I --fix .

test:
	@python manage.py test tests

check: lint test
