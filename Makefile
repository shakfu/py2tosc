.PHONY: help install test cov typecheck docs docs-serve docs-deploy build \
		dist-check publish-test publish \
		clean lint format qa release-check tag

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
	@echo "release-check  verify the tree is ready to tag and release"
	@echo "tag         create the vX.Y.Z tag for the declared version"
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

# The only route the docs have to gh-pages: nothing deploys them automatically.
# This commits and force-pushes with your own credentials, so what lands is
# whatever is in your working tree, not whatever passed CI. Run `make docs`
# first if you want to see it before it is published.
docs-deploy:
	@uv run mkdocs gh-deploy --force --strict

build:
	@uv build
	@uv run twine check --strict dist/*

# `uv build` adds to dist/ without clearing it, so a wheel left over from an
# earlier version would be checked and uploaded alongside the current one.
# Always rebuild from an empty dist/ before validating or publishing.
check:
	@uv run twine check --strict dist/*

# Releases are made by hand, so this is the gate: nothing in CI re-checks the
# version, the changelog or the tree before `make publish` uploads. Run it, then
# tag, then publish.
release-check: qa test build
	@version=$$(uv run --no-default-groups python -c "import py2tosc; print(py2tosc.__version__)"); \
	echo "version: $$version"; \
	grep -q "^## \[$$version\]" CHANGELOG.md \
		|| { echo "ERROR: CHANGELOG.md has no '## [$$version]' section"; exit 1; }; \
	grep -q "unreleased" CHANGELOG.md \
		&& echo "WARNING: CHANGELOG.md still says 'unreleased' - date the entry first"; \
	git diff --quiet || { echo "ERROR: working tree is dirty"; exit 1; }; \
	echo "ready: git tag v$$version && git push origin v$$version"

tag: release-check
	@version=$$(uv run --no-default-groups python -c "import py2tosc; print(py2tosc.__version__)"); \
	git tag -a "v$$version" -m "py2tosc v$$version"; \
	echo "created tag v$$version - push it with: git push origin v$$version"

# TestPyPI is the rehearsal: the same upload path, but a version number burned
# there costs nothing. Needs a testpypi entry in ~/.pypirc, or TWINE_USERNAME
# and TWINE_PASSWORD in the environment.
publish-test: dist-check
	@uv run twine upload --repository testpypi dist/*

# A filename accepted by PyPI can never be reused, even after a delete, so this
# is the one target in the file with no undo, and nothing upstream of it will
# catch a mistake. Requires CONFIRM=1 so that a mistyped or tab-completed target
# cannot spend a version number.
publish: dist-check
	@version=$$(uv run --no-default-groups python -c "import py2tosc; print(py2tosc.__version__)"); \
	if [ "$(CONFIRM)" != "1" ]; then \
		echo "would publish py2tosc $$version to PyPI, permanently."; \
		echo "run 'make release-check' first, then:"; \
		echo "  make publish CONFIRM=1"; \
		exit 1; \
	fi; \
	echo "publishing py2tosc $$version to PyPI"; \
	uv run twine upload dist/*

clean:
	@rm -rf dist site htmlcov .coverage .pytest_cache .mypy_cache
	@find . -name __pycache__ -type d -prune -exec rm -rf {} +
