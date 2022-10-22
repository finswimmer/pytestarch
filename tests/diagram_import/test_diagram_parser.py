import pytest
from conftest import ROOT_DIR

from pytestarch.diagram_import.diagram_parser import PumlParser
from pytestarch.exceptions import PumlParsingError


def test_error_raised_when_no_puml_start_tag_found() -> None:
    path = ROOT_DIR / "tests/resources/pumls/no_start_tag.puml"
    parser = PumlParser()

    with pytest.raises(
        PumlParsingError,
        match="PUML file needs a start and an end tag.",
    ):
        parser.parse(path)


def test_modules_parsed_correctly_from_puml() -> None:
    path = ROOT_DIR / "tests/resources/pumls/very_simple_example.puml"
    parser = PumlParser()

    parsed_dependencies = parser.parse(path)

    assert parsed_dependencies.all_modules == {"M_A", "M_B"}


def test_dependencies_parsed_correctly_from_puml() -> None:
    path = ROOT_DIR / "tests/resources/pumls/very_simple_example.puml"
    parser = PumlParser()

    parsed_dependencies = parser.parse(path)

    assert parsed_dependencies.dependencies == {"M_A": {"M_B"}}


def test_diagram_with_mro_file() -> None:
    path = (
        ROOT_DIR / "tests/resources/pumls/multiple_component_example_with_brackets.puml"
    )
    parser = PumlParser()

    parsed_dependencies = parser.parse(path)

    expected_modules = {
        "exporter",
        "importer",
        "logging_util",
        "model",
        "orchestration",
        "persistence",
        "runtime",
        "services",
        "simulation",
        "util",
    }
    expected_dependenies = {
        "runtime": {"persistence", "orchestration", "services", "logging_util", "util"},
        "services": {"persistence", "model", "util", "importer"},
        "orchestration": {
            "exporter",
            "simulation",
            "model",
            "logging_util",
            "util",
            "importer",
        },
        "importer": {"model", "util"},
        "logging_util": {"util"},
        "simulation": {"model", "util", "logging_util"},
        "persistence": {"model", "util"},
        "exporter": {"model", "util", "logging_util"},
    }

    assert parsed_dependencies.all_modules == expected_modules
    assert parsed_dependencies.dependencies == expected_dependenies
