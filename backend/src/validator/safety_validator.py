"""Structural checks that hold regardless of the connection's permissions."""

from __future__ import annotations

from sqlglot import expressions as exp

from src.validator.validation_result import ValidationResult

BLOCKED = {
    exp.Drop: "DROP",
    exp.Alter: "ALTER",
    exp.TruncateTable: "TRUNCATE",
    exp.Grant: "GRANT",
    exp.Create: "CREATE",
    exp.Set: "SET",
}


def _fail(message: str) -> ValidationResult:
    return ValidationResult(
        valid=False, stage="Safety", error_type="safety", message=message
    )


class SafetyValidator:
    def validate(self, expression: exp.Expression) -> ValidationResult:
        for node_type, name in BLOCKED.items():
            if isinstance(expression, node_type):
                return _fail(f"{name} statements are not allowed.")

        # A bare DELETE or UPDATE would rewrite the whole table.
        if isinstance(expression, (exp.Delete, exp.Update)):
            if expression.find(exp.Where) is None:
                name = "DELETE" if isinstance(expression, exp.Delete) else "UPDATE"
                return _fail(f"{name} without WHERE is not allowed.")

        return ValidationResult(
            valid=True, stage="Safety", message="Safety validation passed."
        )
