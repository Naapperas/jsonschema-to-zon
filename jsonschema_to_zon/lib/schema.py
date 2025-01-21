"""
Classes and methods for reading files containing valid JSON Schemas
"""

import json
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Container, Iterable, Mapping, Self

import zon
from zon import Zon, ZonIssue

__all__ = ["SchemaReader", "Schema", "InvalidSchemaDefinition"]


# TODO: see if we should use another sub-module for validator generation


class InvalidSchemaDefinition(Exception):
    """Indicates that an attempt to parse an invalid JSON Schema document was made."""


class Schema(ABC):
    """Representation of a JSON Schema, that can be traversed and processed."""

    def __init__(self):
        self._version = ""
        self.id = None
        self.defs: dict[str, Schema] = {}

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

        defs = {}
        if "$defs" in contents:
            defs = contents["$defs"]

            defs = {
                f"#/$defs/{def_name}": _parse(def_schema)
                for def_name, def_schema in defs.items()
            }

        # Parse the rest of the Schema document.

        schema = _parse(contents)
        schema.defs = defs

        return schema


def _parse(
    contents: Mapping[str, str | int | float | list | dict | bool | None],
) -> Schema:

    match contents:
        case {"type": schema_type, **rest}:
            try:

                schema: Schema = None
                match schema_type:
                    case "object":
                        schema = ObjectSchema(rest)
                    case "array":
                        schema = ArraySchema(rest)
                    case "integer":
                        schema = IntegerSchema()
                    case "number":
                        schema = NumberSchema()
                    case "boolean":
                        schema = BooleanSchema()
                    case "string":
                        schema = StringSchema()
                    case _:
                        raise InvalidSchemaDefinition(
                            f"Unknown schema type: {schema_type}"
                        )

                return schema

            except InvalidSchemaDefinition as e:
                raise InvalidSchemaDefinition(f"Error when parsing schema: {e}") from e
        case {"enum": values, **rest}:
            return EnumSchema(values, rest)
        case {"const": value, **rest}:
            return ConstSchema(value, rest)
        case {"$ref": def_ref}:
            return RefSchema(def_ref)
        case _:
            raise InvalidSchemaDefinition(
                f"Unknown schema type found in JSON Schema document: {contents}"
            )


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
            sub_schema.defs = self.defs  # FIXME: should be different

            validator = sub_schema.generate().optional()

            if property_name in self.definition["required"]:
                validator = validator.unwrap()

            validator_properties[property_name] = validator

        validator = zon.record(
            validator_properties,
        )

        if self.definition["additionalProperties"] is False:
            validator = validator.strict()
        elif (
            self.definition["additionalProperties"]
            != ObjectSchema._MARKER_ADDITIONAL_PROPERTIES
        ):
            additional_property_schema = _parse(self.definition["additionalProperties"])
            additional_property_schema.defs = self.defs  # FIXME: should be different

            extra_keys_validator = additional_property_schema.generate()

            validator = validator.catchall(extra_keys_validator)

        return validator


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


class JSONSchemaEnum(Zon):
    """Validator for enumerated values in a JSON Schema document.

    The default `enum` Zon is not useful in this context because it only validates string elements.
    """

    def __init__(self, values: Container):
        super().__init__()

        self.values = values

    def _default_validate(self, data, ctx):
        if data not in self.values:
            ctx.add_issue(
                ZonIssue(
                    value=data, message=f"Not an element in {self.values}", path=None
                )
            )


class EnumSchema(Schema):
    """Sub-schema for enumerated values in a JSON Schema document"""

    def __init__(self, values: Container, definition: dict[str, Any]):
        super().__init__()

        self.definition = definition
        self.values = values

    def generate(self):
        return JSONSchemaEnum(self.values)


class ConstSchema(Schema):
    """Sub-schema for constant values in a JSON Schema document."""

    def __init__(self, value: Any, definition: dict[str, Any]):
        super().__init__()

        self.definition = definition
        self.value = value

    def generate(self):
        return zon.literal(self.value)


class ArraySchema(Schema):
    """Sub-schema for arrays in a JSON Schema document."""

    class TYPE(Enum):
        """Internal type used to denote, on validator generation time, \
            which array type should be used"""

        LIST = auto()
        TUPLE = auto()

    def __init__(self, definition: dict[str, Any]):
        super().__init__()

        self.schema_type: ArraySchema.TYPE = None
        if "prefixItems" in definition:
            self.schema_type = ArraySchema.TYPE.TUPLE
        elif "items" not in definition:
            raise InvalidSchemaDefinition(
                '\'definition["items"]\' or \'definition["prefixItems"] \
                    must be present when defining an Array schema'
            )
        else:
            self.schema_type = ArraySchema.TYPE.LIST

        self.definition = definition

    def generate(self):

        if self.schema_type == ArraySchema.TYPE.TUPLE:
            tuple_items_schemas = self.definition["prefixItems"]

            def _compile_schema(schema_definition: dict[str, Any]):
                schema = _parse(schema_definition)
                schema.defs = self.defs  # FIXME: should be different

                return schema

            tuple_items_validators = list(
                map(
                    lambda schema_def: _compile_schema(schema_def).generate(),
                    tuple_items_schemas,
                )
            )

            validator = zon.element_tuple(tuple_items_validators)

            additional_items_validator = zon.anything()
            if "items" in self.definition:
                if self.definition["items"] is False:
                    additional_items_validator = zon.never()
                else:
                    additional_items_schema_definition = self.definition["items"]

                    additional_items_schema = _parse(additional_items_schema_definition)
                    additional_items_schema.defs = (
                        self.defs
                    )  # FIXME: should be different

                    additional_items_validator = additional_items_schema.generate()

            validator = validator.rest(additional_items_validator)
        else:
            items_schema_definition = self.definition["items"]

            items_schema = _parse(items_schema_definition)
            items_schema.defs = self.defs  # FIXME: should be different

            items_validator = items_schema.generate()

            validator = zon.element_list(items_validator)

        return validator


class RefSchema(Schema):
    """Sub-schema for when referenced schemas are used in-place of actual schemas.

    Useful for reusability.
    """

    def __init__(self, ref: str):
        super().__init__()

        self.ref = ref

    def generate(self):
        return self.defs[self.ref].generate()


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
