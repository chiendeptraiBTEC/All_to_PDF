.PHONY: install run test test-cov lint format typecheck check

install:
	python -m pip install -e ".[dev]"

run:
	uvicorn all_to_pdf.main:app --app-dir backend/src --reload

test:
	pytest

test-cov:
	pytest --cov=all_to_pdf --cov-report=term-missing --cov-report=html

lint:
	ruff check backend/src backend/tests

format:
	ruff format backend/src backend/tests

typecheck:
	mypy

check: lint typecheck test-cov
