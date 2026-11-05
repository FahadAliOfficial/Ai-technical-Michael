from __future__ import annotations

from typing import Any


class SchemaValidationError(ValueError):
    pass


def semantic_role(name: str, schema: dict[str, Any]) -> str:
    text = f"{name} {schema.get('description', '')}".lower().replace("_", " ")
    if "product" in text and any(token in text for token in ("ids", "identifiers", "codes")):
        return "product_ids"
    if "product" in text and any(token in text for token in ("id", "identifier", "code", "sku")):
        return "product_id"
    if "categor" in text or "product type" in text:
        return "category"
    if any(token in text for token in ("maximum price", "price ceiling", "budget", "max price")):
        return "max_price"
    if "query" in text or "search text" in text or "customer request" in text:
        return "query"
    if "region" in text or "market" in text or "location" in text:
        return "region"
    if "quantity" in text or "units" in text:
        return "quantity"
    if "include" in text and any(token in text for token in ("unavailable", "out of stock")):
        return "include_unavailable"
    return name


class ArgumentAdapter:
    def bind(self, parameters: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
        properties = parameters.get("properties", {})
        required = set(parameters.get("required", []))
        result: dict[str, Any] = {}
        defaults = {"region": "US", "quantity": 1, "include_unavailable": False}

        for name, schema in properties.items():
            role = semantic_role(name, schema)
            value = context.get(role, defaults.get(role, schema.get("default")))
            if value is not None:
                result[name] = value
            elif name in required:
                raise SchemaValidationError(f"No value is available for required parameter {name!r}")
        validate_arguments(parameters, result)
        return result


def validate_arguments(schema: dict[str, Any], arguments: dict[str, Any]) -> None:
    properties = schema.get("properties", {})
    required = schema.get("required", [])
    missing = [name for name in required if name not in arguments]
    if missing:
        raise SchemaValidationError(f"Missing required arguments: {', '.join(missing)}")
    if schema.get("additionalProperties") is False:
        extras = sorted(set(arguments) - set(properties))
        if extras:
            raise SchemaValidationError(f"Unexpected arguments: {', '.join(extras)}")

    type_map = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    for name, value in arguments.items():
        spec = properties.get(name, {})
        expected = spec.get("type")
        if expected in type_map and not isinstance(value, type_map[expected]):
            raise SchemaValidationError(f"Argument {name!r} must be {expected}")
        if "enum" in spec and value not in spec["enum"]:
            raise SchemaValidationError(f"Argument {name!r} must be one of {spec['enum']}")
        if expected == "array" and "items" in spec:
            item_type = spec["items"].get("type")
            if item_type in type_map and any(not isinstance(item, type_map[item_type]) for item in value):
                raise SchemaValidationError(f"Items in {name!r} must be {item_type}")


def normalize_arguments(parameters: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    properties = parameters.get("properties", {})
    return {semantic_role(name, properties.get(name, {})): value for name, value in arguments.items()}

