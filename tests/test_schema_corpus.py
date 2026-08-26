"""One description per schema, and what that corpus is for.

`ui_json.required_schema` answers "what does this description need", and every
answer it gives comes from `_needs` -- a hand-written record of which schema
each spelling arrived in. Nothing in the reader knows *when* a spelling was
introduced, so unlike every other table here that one cannot be generated, and
a bump that forgets to extend it under-reports silently. A silent under-report
is worse than no check at all: it reads as a clean bill of health, and the
`py2tosc validate` warning built on it goes quiet exactly when it should fire.

This is the guard. One file per schema, each declaring the lowest number that
builds it and using what that number introduced, and three assertions over
them that between them close both halves of the hole:

- **A schema with no description fails.** So `SCHEMA = 3` without a fixture is
  a failing test rather than an untested number.
- **A description whose declared schema is not what `required_schema` computes
  fails.** So a fixture added without the matching `_needs` branch is a
  failing test rather than a wrong answer.
- **The standalone checker agrees with the library on every one of them.**
  `scripts/check_json.py` carries its own hand-written copy of `_needs`, which
  the generated-table drift test cannot see, since it is code rather than a
  table.

Adding a schema means adding a file here, and that is the intended cost.
"""

import importlib.util
import json

import pytest

from _corpus import DATA, PROJECT_ROOT
from py2tosc import ui_json

SCHEMAS = DATA / "schemas"

#: One description per schema, by the number it declares.
DESCRIPTIONS = {
    json.loads(path.read_text())["schema"]: path
    for path in sorted(SCHEMAS.glob("*.ui.json"))
}


def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_json", PROJECT_ROOT / "scripts" / "check_json.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_json = _checker()


def test_every_schema_this_release_reads_has_a_description():
    """A bump without a fixture is a number nothing exercises."""
    missing = sorted(set(ui_json.SCHEMAS) - set(DESCRIPTIONS))
    assert not missing, (
        f"no description in {SCHEMAS.relative_to(PROJECT_ROOT)} declares "
        f"schema {missing}; a schema that nothing exercises is a schema "
        f"`required_schema` has never been asked about"
    )


def test_no_description_declares_a_schema_this_release_cannot_read():
    """The corpus is of this release, not of a future one."""
    extra = sorted(set(DESCRIPTIONS) - set(ui_json.SCHEMAS))
    assert not extra, f"schema {extra} is declared here but not in SCHEMAS"


@pytest.mark.parametrize("schema", sorted(DESCRIPTIONS), ids=str)
def test_a_description_needs_exactly_the_schema_it_declares(schema):
    """The assertion that `_needs` still knows what each schema introduced.

    Under-reporting is the failure worth catching: a fixture using schema N's
    spelling while `required_schema` answers N-1 means the table was not
    extended, and every warning built on it is wrong in the quiet direction.
    Over-reporting fails here too, which is the cheaper mistake but still one.
    """
    data = json.loads(DESCRIPTIONS[schema].read_text())
    assert ui_json.required_schema(data) == schema


@pytest.mark.parametrize("schema", sorted(DESCRIPTIONS), ids=str)
def test_a_description_builds_on_the_release_that_reads_its_schema(schema):
    """Files are durable and readers advance, so every one of these still builds."""
    doc = ui_json.build(json.loads(DESCRIPTIONS[schema].read_text()))
    assert list(doc.walk())
    assert doc.validate() == []


@pytest.mark.parametrize("schema", sorted(DESCRIPTIONS), ids=str)
def test_the_standalone_checker_agrees_about_what_each_one_needs(schema):
    """Its `_needs` is a hand copy, and no generated table covers code."""
    data = json.loads(DESCRIPTIONS[schema].read_text())
    assert check_json.required_schema(data) == schema
    assert check_json.check(data) == []


def test_the_oldest_description_uses_nothing_a_later_schema_added():
    """The floor has to stay reachable, which is what a floor is.

    Not a restatement of the parametrized check: this one would fail if the
    schema-1 file were quietly modernised, which is the way a corpus like this
    rots -- by someone fixing a fixture to look like the others.
    """
    floor = ui_json.SCHEMAS.start
    data = json.loads(DESCRIPTIONS[floor].read_text())
    assert ui_json.required_schema(data) == floor
    assert ui_json.build({**data, "schema": floor}).root.children
