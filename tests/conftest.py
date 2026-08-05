"""Shared fixtures.

The corpus itself is described in `_corpus.py`, so test modules can import it
without going through pytest's fixture machinery.
"""

from pathlib import Path

import pytest

import py2tosc
from _corpus import SAMPLE_TOSC, SAMPLE_XML, payload


@pytest.fixture
def sample_bytes() -> bytes:
    """The sample layout's XML, decompressed out of the `.tosc`."""
    return payload(SAMPLE_TOSC)


@pytest.fixture
def sample_xml() -> bytes:
    """The sample layout as exported to `.xml` by the editor."""
    return SAMPLE_XML.read_bytes()


@pytest.fixture
def sample_xml_path() -> Path:
    """Path to the editor's `.xml` export of the sample layout."""
    return SAMPLE_XML


@pytest.fixture
def doc() -> py2tosc.Document:
    """The sample layout, parsed."""
    return py2tosc.load(SAMPLE_TOSC)
