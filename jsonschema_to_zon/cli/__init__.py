"""_summary_
"""

from pathlib import Path

from jsonschema_to_zon.lib import SchemaReader


reader = SchemaReader()

schema = reader.read_file(
    Path(__file__).parent.parent.parent / "tests" / "data" / "simple_schema.json"
)

validator = schema.generate()

validator.validate(
    {
        "fruits": [],
        "vegetables": [
            {"veggieName": "batata", "veggieLike": True},
            {"veggieName": "caralho", "veggieLike": True},
        ],
    }
)
