from typing import Any


class SchemaValidationError(ValueError):
    pass


class RestrictedJsonSchemaValidator:
    """Fail-closed JSON Schema subset used by the first runtime slice."""

    _supported_keywords = {
        "type",
        "required",
        "properties",
        "additionalProperties",
        "items",
        "enum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
    }

    def validate_schema(self, schema: dict[str, Any], path: str = "$") -> None:
        unsupported = set(schema) - self._supported_keywords
        if unsupported:
            names = ", ".join(sorted(unsupported))
            raise SchemaValidationError(
                f"Unsupported JSON Schema keyword at {path}: {names}"
            )
        schema_type = schema.get("type")
        if schema_type not in {
            "object",
            "array",
            "string",
            "number",
            "integer",
            "boolean",
            "null",
        }:
            raise SchemaValidationError(f"Unsupported or missing type at {path}")
        if schema_type == "object":
            properties = schema.get("properties", {})
            if not isinstance(properties, dict):
                raise SchemaValidationError(f"properties must be an object at {path}")
            for name, child in properties.items():
                if not isinstance(child, dict):
                    raise SchemaValidationError(
                        f"Property schema must be an object at {path}.{name}"
                    )
                self.validate_schema(child, f"{path}.{name}")
        if schema_type == "array" and "items" in schema:
            items = schema["items"]
            if not isinstance(items, dict):
                raise SchemaValidationError(f"items must be an object at {path}")
            self.validate_schema(items, f"{path}[]")

    def validate(self, value: Any, schema: dict[str, Any], path: str = "$") -> None:
        self.validate_schema(schema, path)
        schema_type = schema["type"]
        if not self._matches_type(value, schema_type):
            raise SchemaValidationError(
                f"Expected {schema_type} at {path}, got {type(value).__name__}"
            )
        if "enum" in schema and value not in schema["enum"]:
            raise SchemaValidationError(f"Value is not in enum at {path}")
        if schema_type == "object":
            self._validate_object(value, schema, path)
        elif schema_type == "array":
            self._validate_array(value, schema, path)
        elif schema_type == "string":
            self._validate_string(value, schema, path)

    def _validate_object(
        self, value: dict[str, Any], schema: dict[str, Any], path: str
    ) -> None:
        required = schema.get("required", [])
        missing = [name for name in required if name not in value]
        if missing:
            raise SchemaValidationError(
                f"Missing required properties at {path}: {', '.join(missing)}"
            )
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            additional = set(value) - set(properties)
            if additional:
                raise SchemaValidationError(
                    f"Additional properties are not allowed at {path}"
                )
        for name, child_schema in properties.items():
            if name in value:
                self.validate(value[name], child_schema, f"{path}.{name}")

    def _validate_array(
        self, value: list[Any], schema: dict[str, Any], path: str
    ) -> None:
        if len(value) < schema.get("minItems", 0):
            raise SchemaValidationError(f"Array is too short at {path}")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaValidationError(f"Array is too long at {path}")
        if "items" in schema:
            for index, item in enumerate(value):
                self.validate(item, schema["items"], f"{path}[{index}]")

    @staticmethod
    def _validate_string(
        value: str, schema: dict[str, Any], path: str
    ) -> None:
        if len(value) < schema.get("minLength", 0):
            raise SchemaValidationError(f"String is too short at {path}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaValidationError(f"String is too long at {path}")

    @staticmethod
    def _matches_type(value: Any, schema_type: str) -> bool:
        if schema_type == "object":
            return isinstance(value, dict)
        if schema_type == "array":
            return isinstance(value, list)
        if schema_type == "string":
            return isinstance(value, str)
        if schema_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if schema_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if schema_type == "boolean":
            return isinstance(value, bool)
        if schema_type == "null":
            return value is None
        return False
