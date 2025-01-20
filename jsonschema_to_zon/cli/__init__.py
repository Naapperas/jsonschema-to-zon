from jsonschema_to_zon.lib import SchemaReader

reader = SchemaReader()

schema = reader.read_file(
    "/home/naapperas/workspace/personal/python/jsonschema_to_zon/tests/data/simple_schema.json"
)

validator = schema.generate()

validator.validate({})
validator.validate({"firstName": "Nuno", "lastName": "Pereira", "age": 5})
