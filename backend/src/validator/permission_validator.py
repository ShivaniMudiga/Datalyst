"""Is this operation allowed here?

Fast feedback for the model only. The database role is the real gate - this
check exists so a blocked query comes back in milliseconds with a reason the
model can act on, not as a Postgres error after a round trip.
"""

from __future__ import annotations

from sqlglot import expressions as exp

from src.validator.validation_result import ValidationResult

READ_OPERATIONS = frozenset({"select", "union", "intersect", "except", "with", "subquery"})


class PermissionValidator:
    def __init__(self, allowed_operations: set[str] | None = None):
        self.allowed = frozenset(
            operation.lower() for operation in (allowed_operations or READ_OPERATIONS)
        )

    def validate(self, expression: exp.Expression) -> ValidationResult:
        operation = expression.key.lower()

        if operation not in self.allowed:
            return ValidationResult(
                valid=False,
                stage="Permission",
                error_type="permission",
                message=f"{operation.upper()} operations are not allowed on this connection.",
            )

        return ValidationResult(
            valid=True,
            stage="Permission",
            message=f"{operation.upper()} operation is permitted.",
        )
