# jsonschema_to_zon - Convert your JSON Schema documents into valid Zon validators

[![Coverage Status](https://coveralls.io/repos/github/Naapperas/jsonschema-to-zon/badge.svg?branch=main)](https://coveralls.io/github/Naapperas/jsonschema-to-zon?branch=main)

A python utility that allows reading and JSON Schema documents and converting them into `zon` validators that respect the schema defined in those files.

Developed as a companion project to [`zon`](https://github.com/Naapperas/zon).

## Installation

### Pip

This package is available on PyPI, so you can install it with `pip`:

```bash
pip install jsonschema-to-zon
```

### Source

Alternatively, you can clone this repository and install it from source. Please make sure that you have [`uv`](https://docs.astral.sh/uv) installed on your system.

```bash
git clone https://github.com/Naapperas/jsonschema_to_zon
cd zon
uv pip install .
```

## Usage

In order to use the library, you first create a `Schema` object. This `Schema` object contains parsed information about your JSON Schema document. From this `Schema` object, you can invoke the `generate` command to generate the final `Zon` validator instance.

```py

schema = ... # Create Schema. Described below
validator = schema.generate()

# Now you are ready to use the API provided by 'zon'
```

### Generating `Schema` objects

Currently, there are 3 ways to generate `Schema` objects: passing in a file path, passing the contents of the JSON Schemas document as a string, or passing these same contents as a Python dictionary. The first 2 methods require the use of a `SchemaReader`.

#### Reading from a file

The most commonly expected method of using the library is from parsing a centrally served JSON Schema document:

```py
reader = SchemaReader()
schema = reader.read_file('/path/to/your/file')

# Now you can do whatever you want with your schema object.
```

#### Reading from a string

If your JSON Schema definition is not present in a file, but is served in some other way (reading a DB record or served as part of an HTTP response, for example), you can also use the same `SchemaReader` class to generate a corresponding `Schema` object.

```py
SCHEMA_STR = ...

reader = SchemaReader()

schema = reader.read_str(SCHEMA_STR)

# Now you can do whatever you want with your schema object.
```

#### Parsing a Python `dict` object

If you decide to construct your schema programatically using any of `dict`-like types supported in Python (including custom types supporting `dict`-like operations), you can invoke `Schema.parse` to generate the correct `Schema` object for you:

```py

SCHEMA_DICT = {...}

schema = Schema.parse(SCHEMA_DICT)

# Now you can do whatever you want with your schema object.
```

## Examples

Examples of using `jsonschema-to-zon` will be created soon.

## Documentation

Documentation is still not available, but it will be soon.

## Tests

Tests can be found in the [tests](tests) folder. `jsonschema-to-zon` uses `pytest` for unit testing.

To run the tests, simply run:

```bash
pytest test
```
Coverage can be found on [Coveralls](https://coveralls.io/github/Naapperas/jsonschema-to-zon).

## Contributing

Contribution guidelines can be found in [CONTRIBUTING](CONTRIBUTING.md)

Past and current contributors can be found in [CONTRIBUTORS](CONTRIBUTORS.md)

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.