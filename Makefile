.PHONY: help install test cov typecheck docs docs-serve docs-deploy build \
		publish clean lint lint-check format qa check check-all

help:
	@echo "install     install the package and dev dependencies"
	@echo "test        run the test suite"
	@echo "cov         run the test suite with a coverage report"
	@echo "typecheck   run mypy"
	@echo "lint        run ruff and fix what it can"
	@echo "lint-check  run ruff and ruff format read-only, as CI does"
	@echo "format      reformat src/ with ruff"
	@echo "qa          format, lint and typecheck (rewrites files)"
	@echo "check-all   run every CI gate read-only"
	@echo "docs        build the documentation into site/"
	@echo "docs-serve  serve the documentation with live reload"
	@echo "docs-deploy build the docs and push them to the gh-pages branch"
	@echo "build       build the wheel and sdist into dist/"
	@echo "check 	   validate the artefacts with twine"
	@echo "publish     upload dist/ to PyPI"
	@echo "clean       remove build and test artefacts"

install:
	@uv sync

test:
	@uv run pytest -v

cov:
	@uv run pytest --cov=py2tosc --cov-report=term-missing --cov-report=html

# The standalone checker is held to the same bar as the package, because it
# is code other projects copy. `check_enums.py` predates the rule and is not
# named here; adding it is a separate job.
typecheck:
	@uv run mypy --strict src/ scripts/check_json.py scripts/make_check_json.py

lint:
	@uv run ruff check --fix src/ scripts/

lint-check:
	@uv run ruff check src/ scripts/
	@uv run ruff format --check src/ scripts/

format:
	@uv run ruff format src/ scripts/

# `qa` rewrites files: it is the target you run while working. `check-all` never
# writes to src/ and runs the same gates CI does, so a clean run here means a
# clean run there. Ordered fastest-first so a failure surfaces early.
qa: format lint typecheck

check-all: lint-check typecheck test docs build

docs:
	@uv run mkdocs build --strict

docs-serve:
	@uv run mkdocs serve

docs-deploy:
	@uv run mkdocs gh-deploy --force --strict

build:
	@uv build
	@uv run twine check --strict dist/*

check:
	@uv run twine check --strict dist/*

publish:
	uv run twine upload dist/*

clean:
	@rm -rf dist site htmlcov .coverage .pytest_cache .mypy_cache
	@find . -name __pycache__ -type d -prune -exec rm -rf {} +
