.PHONY: lint format typecheck test coverage ci

lint:
	ruff check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy --strict src/

test:
	pytest tests/ -x --ignore=tests/db/test_crud.py

coverage:
	pytest tests/ --cov=src --cov-report=term-missing --ignore=tests/db/test_crud.py

ci: lint typecheck test
