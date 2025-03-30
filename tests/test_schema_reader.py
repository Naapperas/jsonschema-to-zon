from unittest.mock import patch, mock_open

import pytest

import jsonschema_to_zon


@pytest.fixture
def schema_content_str():
    return """{
    "$id": "https://example.com/conditional-validation-dependentRequired.schema.json",
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Conditional Validation with dependentRequired",
    "type": "object",
    "properties": {
        "foo": {
            "type": "boolean"
        },
        "bar": {
            "type": "string"
        }
    },
    "dependentRequired": {
        "foo": [
            "bar"
        ]
    }
}"""


@pytest.fixture
def schema_content_file_path():
    from pathlib import Path

    return Path(__file__).parent / "data" / "simple_schema.json"


@pytest.fixture
def reader():
    return jsonschema_to_zon.SchemaReader()


def test_schema_read_file(reader, schema_content_str, schema_content_file_path):

    with patch("__main__.open", mock_open(read_data=schema_content_str)):
        try:
            reader.read_file(schema_content_file_path)
        except:
            assert False
        else:
            assert (
                True  # We expect that this operation success without raising an error
            )


def test_schema_read_str(reader, schema_content_str):

    try:
        reader.read_str(schema_content_str)
    except:
        assert False
    else:
        assert True
