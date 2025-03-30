"""
Classes and methods for reading files containing valid JSON Schemas
"""

from __future__ import annotations

import json
import math
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Any, Self
from collections.abc import Mapping, Sized, Iterable, Container

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
        self.comment = None
        self.title = None
        self.description = None

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
        contents: Mapping[str, str | int | float | list | dict | bool | None],
    ) -> Self:
        """Parses a dictionary containing a JSON Schema definition and returns a `Schema` object.

        Args:
            contents (Mapping[str, str | int | float | list | dict | bool | None]): a dictionary containing a definition of a JSON Schema document.

        Raises:
            InvalidSchemaDefinition: if `contents` contains an invalid schema definition

        Returns:
            Self: the parsed Schema object
        """

        # TODO: implement validation of schema.

        # Parse top-level properties of the Schema document

        if "$id" not in contents:
            raise InvalidSchemaDefinition("'$id' not found in JSON Schema document")

        title = None
        if "title" in contents:
            title = contents["title"]

        defs = {}
        if "$defs" in contents:
            defs = contents["$defs"]

            defs = {
                f"#/$defs/{def_name}": _parse(def_schema)
                for def_name, def_schema in defs.items()
            }

        # Parse the rest of the Schema document.

        schema = _parse(contents)
        defs["#"] = schema
        schema.defs = defs
        schema.title = title

        return schema


def _parse(
    contents: Mapping[str, str | int | float | list | dict | bool | None],
) -> Schema:

    schema: Schema = None
    match contents:
        case {"type": schema_type, **rest}:
            try:
                match schema_type:
                    case "object":
                        schema = ObjectSchema(rest)
                    case "array":
                        schema = ArraySchema(rest)
                    case "integer":
                        schema = IntegerSchema(rest)
                    case "number":
                        schema = NumberSchema(rest)
                    case "boolean":
                        schema = BooleanSchema()
                    case "string":
                        schema = StringSchema(rest)
                    case _:
                        raise InvalidSchemaDefinition(
                            f"Unknown schema type: {schema_type}"
                        )

            except InvalidSchemaDefinition as e:
                raise InvalidSchemaDefinition(f"Error when parsing schema: {e}") from e
        case {"enum": values, **rest}:
            schema = EnumSchema(values, rest)
        case {"const": value, **rest}:
            schema = ConstSchema(value, rest)
        case {"$ref": def_ref}:
            schema = RefSchema(def_ref)
        case {"not": sub_schema}:
            schema = NotSchema(sub_schema)
        case {"allOf": subschemas}:
            schema = AllOfSchema(subschemas)
        case {"anyOf": subschemas}:
            schema = AnyOfSchema(subschemas)
        case _:
            raise InvalidSchemaDefinition(
                f"Unknown schema type found in JSON Schema document: {contents}"
            )

    return schema


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

        if "dependentRequired" in self.definition:

            dependents = self.definition["dependentRequired"]

            def _dependent(data) -> bool:

                if not isinstance(data, dict):
                    return False

                for dependent, dependencies in dependents.items():
                    if dependent in data:
                        for dependency in dependencies:
                            if dependency not in data:
                                return False

                return True

            validator = validator.refine(_dependent, "Dependent properties")

        return validator


class StringSchema(Schema):
    """Sub-schema for String values in a JSON Schema document"""

    def __init__(self, definition: dict[str, Any]):
        super().__init__()

        self.definition = definition

    def generate(self) -> Zon:
        validator: Zon = zon.string()

        if "minLength" in self.definition:
            validator = validator.min(self.definition["minLength"])

        if "maxLength" in self.definition:
            validator = validator.max(self.definition["maxLength"])

        if "pattern" in self.definition:
            validator = validator.regex(self.definition["pattern"])

        return validator


class IntegerSchema(Schema):
    """Sub-schema for Integer numeric values in a JSON Schema document"""

    def __init__(self, definition: dict[str, Any]):
        super().__init__()

        self.definition = definition

    def generate(self):
        validator = zon.number().int()

        if "multipleOf" in self.definition:
            validator = validator.multiple_of(self.definition["multipleOf"])

        if "minimum" in self.definition:
            validator = validator.gte(self.definition["minimum"])

        if "exclusiveMinimum" in self.definition:
            validator = validator.gt(self.definition["exclusiveMinimum"])

        if "maximum" in self.definition:
            validator = validator.lte(self.definition["maximum"])

        if "exclusiveMaximum" in self.definition:
            validator = validator.lt(self.definition["exclusiveMaximum"])

        return validator


class NumberSchema(Schema):
    """Sub-schema for arbitrary numeric values in a JSON Schema document"""

    def __init__(self, definition: dict[str, Any]):
        super().__init__()

        self.definition = definition

    def generate(self):
        validator = zon.number().float()

        if "multipleOf" in self.definition:
            validator = validator.multiple_of(self.definition["multipleOf"])

        if "minimum" in self.definition:
            validator = validator.gte(self.definition["minimum"])

        if "exclusiveMinimum" in self.definition:
            validator = validator.gt(self.definition["exclusiveMinimum"])

        if "maximum" in self.definition:
            validator = validator.lte(self.definition["maximum"])

        if "exclusiveMaximum" in self.definition:
            validator = validator.lt(self.definition["exclusiveMaximum"])

        return validator


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

        return data


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
            if "contains" not in definition:
                raise InvalidSchemaDefinition(
                    '\'definition["items"]\' or \'definition["prefixItems"] \
                        must be present when defining an Array schema'
                )

        else:
            self.schema_type = ArraySchema.TYPE.LIST

        if "minContains" in definition:
            if (
                not isinstance(
                    (min_contains := definition["minContains"]), (float, int)
                )
                or min_contains < 0
            ):
                raise InvalidSchemaDefinition(
                    f"Invalid value for 'minContains': {min_contains}"
                )

        if "maxContains" in definition:
            if (
                not isinstance(
                    (max_contains := definition["maxContains"]), (float, int)
                )
                or max_contains < 0
            ):
                raise InvalidSchemaDefinition(
                    f"Invalid value for 'maxContains': {max_contains}"
                )

        if "minItems" in definition:
            if (
                not isinstance((min_items := definition["minItems"]), (float, int))
                or min_items < 0
            ):
                raise InvalidSchemaDefinition(
                    f"Invalid value for 'minItems': {min_items}"
                )

        if "maxItems" in definition:
            if (
                not isinstance((max_items := definition["maxItems"]), (float, int))
                or max_items < 0
            ):
                raise InvalidSchemaDefinition(
                    f"Invalid value for 'maxItems': {max_items}"
                )

        self.must_contain = definition.get("contains", None)
        self.definition = definition

    def generate(self):

        if self.schema_type == ArraySchema.TYPE.TUPLE:
            tuple_items_schemas = self.definition["prefixItems"]

            def _compile_schema(schema_definition: dict[str, Any]):
                schema = _parse(schema_definition)
                schema.defs = self.defs  # FIXME: should be different

                return schema

            tuple_items_validators = [
                _compile_schema(schema_def).generate()
                for schema_def in tuple_items_schemas
            ]

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

        if self.must_contain is not None:

            def _contains(data) -> bool:

                if not isinstance(data, (list, tuple)):
                    return False

                must_contain_schema_definition = self.must_contain

                must_contain_schema = _parse(must_contain_schema_definition)
                must_contain_schema.defs = self.defs

                must_contain_schema_validator = must_contain_schema.generate()

                valid_counter = 0

                for value in data:
                    value_valid, _ = must_contain_schema_validator.safe_validate(value)

                    valid_counter += value_valid

                return (
                    max(0, self.definition.get("minContains", 0))
                    < valid_counter
                    < min(math.inf, self.definition.get("minContains", math.inf))
                )

            validator = validator.refine(
                _contains,
                f'Array or tuple must contain values that conform to "{self.must_contain}"',
            )

        if "minItems" in self.definition or "maxItems" in self.definition:

            def _length(data) -> bool:

                if not isinstance(data, Sized):
                    return False

                return (
                    self.definition.get("minItems", -math.inf)
                    <= len(data)
                    <= self.definition.get("maxItems", math.inf)
                )

            validator = validator.refine(
                _length,
                "Length check",
            )

        if self.definition.get("uniqueItems", False):

            def _unique(data) -> bool:

                if not isinstance(data, Sized):
                    return False

                return len(set(data)) == len(data)

            validator = validator.refine(
                _unique,
                "Uniqueness check",
            )

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


class NotValidator(Zon):
    """Zon that validates that input data is not valid under the underlying validator"""

    def __init__(self, other: Zon):
        super().__init__()

        self.other = other

    def _default_validate(self, data, ctx):

        valid, _ = self.other.safe_validate(data)

        # if data is not valid, no need to know why so we can discard the inner validator's errors

        if valid:
            ctx.add_issue(
                ZonIssue(
                    value=data, message=f"Expected {data} to not be valid", path=[]
                )
            )

        return data


class NotSchema(Schema):
    """Sub-schema that makes it so data cannot validate against the underlying schema."""

    def __init__(self, sub_schema_definition: dict[str, Any]):
        super().__init__()

        self.sub_schema_definition = sub_schema_definition

    def generate(self):
        sub_schema = _parse(self.sub_schema_definition)
        sub_schema.defs = self.defs

        sub_schema_validator = sub_schema.generate()

        return NotValidator(sub_schema_validator)


class AllOfSchema(Schema):
    """Sub-schema that validates a given instance against _all_ of the sub-schemas given"""

    def __init__(self, subschemas: Iterable[dict[str, Any]]):
        super().__init__()

        self.subschemas = subschemas

    def generate(self):

        subschema_definition = self.subschemas[0]
        subschema = _parse(subschema_definition)
        validator = subschema.generate()

        for i in range(1, len(self.subschemas)):
            subschema_definition = self.subschemas[i]
            subschema = _parse(subschema_definition)
            validator = validator.and_also(subschema.generate())

        return validator


class AnyOfSchema(Schema):
    """Sub-schema that validates a given instance against _any_ of the sub-schemas given"""

    def __init__(self, subschemas: Iterable[dict[str, Any]]):
        super().__init__()

        self.subschemas = subschemas

    def generate(self):

        subschema_definition = self.subschemas[0]
        subschema = _parse(subschema_definition)
        validator = subschema.generate()

        for i in range(1, len(self.subschemas)):
            subschema_definition = self.subschemas[i]
            subschema = _parse(subschema_definition)
            validator = validator.or_else([subschema.generate()])

        return validator


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
