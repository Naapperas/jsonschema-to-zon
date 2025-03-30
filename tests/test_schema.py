import pytest

import jsonschema_to_zon
import zon


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
def reader():
    return jsonschema_to_zon.SchemaReader()


@pytest.fixture
def schema(reader, schema_content_str):
    return reader.read_str(schema_content_str)


def test_schema_generates_correct_validator(schema):
    validator = schema.generate()

    assert isinstance(validator, zon.ZonRecord)
