from __future__ import annotations

import re
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
            if value is None and schema.get("type") == "object" and schema.get("properties"):
                value = self.bind(schema, context)
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

    type_map: dict[str, Any] = {
        "string": str,
        "number": (int, float),
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    def validate_value(name: str, value: Any, spec: dict[str, Any]) -> None:
        expected = spec.get("type")
        allowed_types = expected if isinstance(expected, list) else [expected]
        if value is None and "null" in allowed_types:
            return
        valid_types = [type_map[item] for item in allowed_types if item in type_map]
        bool_as_number = isinstance(value, bool) and any(item in {"integer", "number"} for item in allowed_types)
        if bool_as_number or (valid_types and not any(isinstance(value, item_type) for item_type in valid_types)):
            raise SchemaValidationError(f"Argument {name!r} must be one of {allowed_types}")
        if "enum" in spec and value not in spec["enum"]:
            raise SchemaValidationError(f"Argument {name!r} must be one of {spec['enum']}")
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if "minimum" in spec and value < spec["minimum"]:
                raise SchemaValidationError(f"Argument {name!r} must be >= {spec['minimum']}")
            if "maximum" in spec and value > spec["maximum"]:
                raise SchemaValidationError(f"Argument {name!r} must be <= {spec['maximum']}")
        if isinstance(value, str):
            if "minLength" in spec and len(value) < spec["minLength"]:
                raise SchemaValidationError(f"Argument {name!r} is shorter than minLength")
            if "maxLength" in spec and len(value) > spec["maxLength"]:
                raise SchemaValidationError(f"Argument {name!r} is longer than maxLength")
            if "pattern" in spec and re.search(spec["pattern"], value) is None:
                raise SchemaValidationError(f"Argument {name!r} does not match the required pattern")
        if isinstance(value, list):
            if "minItems" in spec and len(value) < spec["minItems"]:
                raise SchemaValidationError(f"Argument {name!r} has too few items")
            if "maxItems" in spec and len(value) > spec["maxItems"]:
                raise SchemaValidationError(f"Argument {name!r} has too many items")
            item_spec = spec.get("items", {})
            for index, item in enumerate(value):
                validate_value(f"{name}[{index}]", item, item_spec)
        if isinstance(value, dict) and (expected == "object" or "object" in allowed_types):
            validate_arguments(spec, value)

    for name, value in arguments.items():
        spec = properties.get(name, {})
        validate_value(name, value, spec)


def normalize_arguments(parameters: dict[str, Any], arguments: dict[str, Any]) -> dict[str, Any]:
    properties = parameters.get("properties", {})
    normalized: dict[str, Any] = {}
    for name, value in arguments.items():
        specification = properties.get(name, {})
        if isinstance(value, dict) and specification.get("type") == "object":
            normalized.update(normalize_arguments(specification, value))
        else:
            normalized[semantic_role(name, specification)] = value
    return normalized

