.PHONY: help install test cov typecheck docs docs-serve docs-deploy build \
		publish clean lint format qa release-check tag

help:
	@echo "install     install the package and dev dependencies"
	@echo "test        run the test suite"
	@echo "cov         run the test suite with a coverage report"
	@echo "typecheck   run mypy"
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

typecheck:
	@uv run mypy --strict src/

lint:
	@uv run ruff check --fix src/

format:
	@uv run ruff format src/

qa: format lint typecheck

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
