from __future__ import annotations

import re

from .models import Requirements


def _number(value: str) -> float:
    return float(value.replace(",", ""))


def _last_match(pattern: str, text: str) -> re.Match[str] | None:
    matches = list(re.finditer(pattern, text, flags=re.IGNORECASE))
    return matches[-1] if matches else None


class RuleBasedRequirementParser:
    """Deterministic fallback and test oracle for common shopping language."""

    def parse(self, request: str, previous: Requirements | None = None) -> Requirements:
        text = request.strip()
        lower = text.lower()
        values = previous.model_dump() if previous else Requirements().model_dump()
        values["conflicts"] = []
        values["clarification_question"] = None

        if "laptop" in lower or "notebook" in lower:
            values["category"] = "laptop"

        budget_patterns = (
            r"(?:budget(?:\s+is|\s+of)?|maximum\s+budget|max\s+budget)\s*(?:is|of|:)?\s*\$?([\d,]+(?:\.\d+)?)",
            r"(?:under|below|up to|no more than)\s*\$([\d,]+(?:\.\d+)?)",
            r"\$([\d,]+(?:\.\d+)?)\s*(?:budget|max(?:imum)?|or less)",
        )
        budgets: list[float] = []
        for pattern in budget_patterns:
            budgets.extend(_number(m.group(1)) for m in re.finditer(pattern, text, re.IGNORECASE))
        if budgets:
            unique = list(dict.fromkeys(budgets))
            if len(unique) > 1 and not any(word in lower for word in ("changed", "increase", "decrease", "now")):
                values["conflicts"].append(f"Multiple maximum budgets were provided: {unique}")
                values["clarification_question"] = "What is the single maximum budget I should use?"
            else:
                values["max_price"] = budgets[-1]
        elif re.search(r"(?:under|below|up to|no more than)\s*,\d{3}\b", text, re.IGNORECASE):
            values["conflicts"].append(
                "The budget appears incomplete because the currency amount lost its leading characters."
            )
            values["clarification_question"] = (
                "What is your maximum budget? In PowerShell, wrap requests containing $ in single quotes."
            )

        ram = _last_match(r"(?:at least|minimum|min(?:imum)?\s+of)?\s*(\d+)\s*gb\s*(?:of\s*)?ram", text)
        if ram:
            values["min_ram_gb"] = int(ram.group(1))

        storage = _last_match(
            r"(?:at least|minimum|min(?:imum)?\s+of)?\s*(\d+(?:\.\d+)?)\s*(tb|gb)\s*(?:of\s+)?(?:(ssd|hdd)(?:\s+storage)?|storage)",
            text,
        )
        if storage:
            amount = float(storage.group(1))
            values["min_storage_gb"] = int(amount * 1024 if storage.group(2).lower() == "tb" else amount)
            if storage.group(3):
                values["storage_type"] = storage.group(3).upper()
        elif "ssd" in lower:
            values["storage_type"] = "SSD"

        battery = _last_match(r"(?:battery(?:\s+life)?[^\d]{0,25})(\d+(?:\.\d+)?)\s*(?:\+\s*)?hours?", text)
        if battery is None:
            battery = _last_match(r"(\d+(?:\.\d+)?)\s*(?:\+\s*)?hours?(?:\s+of)?\s+battery", text)
        if battery:
            values["preferred_battery_hours"] = float(battery.group(1))

        weight = _last_match(r"(?:under|below|less than|max(?:imum)?(?:\s+of)?)\s*(\d+(?:\.\d+)?)\s*kg", text)
        if weight:
            values["preferred_max_weight_kg"] = float(weight.group(1))

        if "software development" in lower or "programming" in lower or "developer" in lower:
            values["purpose"] = "software development"

        contradictory_ram = re.search(r"(?:at least|min(?:imum)?)\s*(\d+)\s*gb\s*ram.*(?:at most|max(?:imum)?)\s*(\d+)\s*gb\s*ram", lower)
        if contradictory_ram and int(contradictory_ram.group(1)) > int(contradictory_ram.group(2)):
            values["conflicts"].append("The minimum RAM is greater than the maximum RAM.")
            values["clarification_question"] = "Which RAM requirement should I use?"

        return Requirements.model_validate(values)

