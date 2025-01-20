"""
Classes and methods for reading files containing valid JSON Schemas
"""

from typing import Mapping, Self, Any, Iterable
from abc import ABC, abstractmethod

import zon
from zon import Zon

import json

__all__ = ["SchemaReader", "Schema", "InvalidSchemaDefinition"]


class InvalidSchemaDefinition(Exception):
    """Indicates that an attempt to parse an invalid JSON Schema document was made."""


class Schema(ABC):
    """Representation of a JSON Schema, that can be traversed and processed."""

    def __init__(self):
        self._version = ""
        self.id = None

    @property
    def version(self) -> str:
        """The version of the parsed schema"""
        return self._version

    @abstractmethod
    def generate(self) -> Zon:
        """Generates a Zon instance from this Schema object.

        Returns:
            Zon: the validator instance generated from this Schema object.
        """

    @staticmethod
    def parse(
        contents: Mapping[str, str | int | float | list | dict | bool | None]
    ) -> Self:
        """Parses a dictionary containing a JSON Schema definition and returns a `Schema` object.

        Args:
            contents (Mapping[str, str  |  int  |  float  |  list  |  dict  |  bool  |  None]):
            a dictionary containing a definition of a JSON Schema document.

        Raises:
            InvalidSchemaDefinition: if `contents` contains an invalid schema definition

        Returns:
            Schema: the parsed Schema object
        """
        # TODO: implement validation of schema.

        # Parse top-level properties of the Schema document

        if "$id" not in contents:
            raise InvalidSchemaDefinition("'$id' not found in JSON Schema document")

        # Parse the rest of the Schema document.

        return _parse(contents)


def _parse(
    contents: Mapping[str, str | int | float | list | dict | bool | None]
) -> Schema:

    if "type" not in contents:
        raise InvalidSchemaDefinition(
            f"'type' not found in JSON Schema document: {contents}"
        )

    try:
        match contents["type"]:
            case "object":
                return ObjectSchema(contents)
            case "array":
                pass
            case "integer":
                return IntegerSchema()
            case "number":
                return NumberSchema()
            case "boolean":
                return BooleanSchema()
            case "string":
                return StringSchema()
    except InvalidSchemaDefinition as e:
        raise InvalidSchemaDefinition(f"Error when parsing object: {e}") from e


class BooleanSchema(Schema):
    """Sub-schema for Boolean values in a JSON Schema document"""

    def generate(self) -> Zon:
        return zon.boolean()


class ObjectSchema(Schema):
    """Sub-schema for Object values in a JSON Schema document"""

    _MARKER_ADDITIONAL_PROPERTIES = "_const_additional_properties"

    def __init__(self, definition: dict[str, Any]):
        super().__init__()

        # https://json-schema.org/draft/2020-12/json-schema-core#section-10.3.2.1-4
        # if "properties" not in definition:
        #     raise InvalidSchemaDefinition("No properties found for object schema")

        if "required" in definition:
            # TODO: this fails for iterables that use "__getitem__"
            if not isinstance(definition["required"], Iterable):
                raise InvalidSchemaDefinition(
                    "'definition[\"required\"]' should be iterable"
                )

            # https://json-schema.org/understanding-json-schema/reference/object#required
            # if not any(map(lambda e: isinstance(e, str), definition["required"])):
            #     raise InvalidSchemaDefinition(
            #         "'definition[\"required\"]' must contain at least one string"
            #     )
        else:
            definition["required"] = []

        if "additionalProperties" not in definition:
            definition["additionalProperties"] = (
                ObjectSchema._MARKER_ADDITIONAL_PROPERTIES
            )
        else:
            match definition["additionalProperties"]:
                case {**_unused}:
                    pass
                case False:
                    pass
                case v:
                    raise InvalidSchemaDefinition(
                        f"'definition[\"additionalProperties\"]' \
                        must either be a valid JSON Schema or False, got {v}"
                    )

        self.definition = definition

    def generate(self) -> Zon:
        validator_properties = {}

        for property_name, property_definition in self.definition.get(
            "properties", {}
        ).items():
            sub_schema = _parse(property_definition)

            validator = sub_schema.generate().optional()

            if property_name in self.definition["required"]:
                validator = validator.unwrap()

            validator_properties[property_name] = validator

        extra_keys_policy = zon.ZonRecord.UnknownKeyPolicy.PASSTHROUGH
        extra_keys_validator = None
        if self.definition["additionalProperties"] is False:
            extra_keys_policy = zon.ZonRecord.UnknownKeyPolicy.STRICT
        elif (
            self.definition["additionalProperties"]
            != ObjectSchema._MARKER_ADDITIONAL_PROPERTIES
        ):
            additional_property_schema = _parse(self.definition["additionalProperties"])

            extra_keys_validator = additional_property_schema.generate()

        return zon.record(
            validator_properties,
            # unknown_key_policy=extra_keys_policy,
            # catchall=extra_keys_validator,
        )


class StringSchema(Schema):
    """Sub-schema for String values in a JSON Schema document"""

    def generate(self) -> Zon:
        return zon.string()


class IntegerSchema(Schema):
    """Sub-schema for Integer numeric values in a JSON Schema document"""

    def generate(self):
        return zon.number().int()


class NumberSchema(Schema):
    """Sub-schema for arbitrary numeric values in a JSON Schema document"""

    def generate(self):
        return zon.number().float()


class SchemaReader:
    """
    Class used for reading JSON Schemas out of a file.
    """

    def __init__(self):
        pass

    def read_file(self, path: str) -> Schema:
        """Reads the contents of the file at `path` and parses them into a `Schema` object.

        Args:
            path (str): the path of the file possibly containing a valid JSON Schema document.

        Returns:
            Schema: the parsed JSON Schema
        """

        with open(path, "r", encoding="utf-8") as schema_file:
            contents = json.load(schema_file)

            return Schema.parse(contents)

    def read_str(self, contents_str: str) -> Schema:
        """Reads the input and parses it into a `Schema` object.

        Args:
            contents_str (str): a string containing a JSON Schema document

        Returns:
            Schema: the parsed JSON Schema
        """
        contents = json.loads(contents_str)

        return Schema.parse(contents)
