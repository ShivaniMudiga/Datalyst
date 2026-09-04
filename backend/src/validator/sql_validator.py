"""The validation pipeline: syntax -> permission -> safety -> semantic.

Permission and safety run before semantic because they are structural: asking
"do these columns exist?" of a CREATE TABLE yields a semantic error, and a
semantic error tells the model to fix the query and retry - which it cannot.
Cheapest and most decisive check first, so the error_type is always the one
the model should act on.

The query is parsed once, here, pinned to the PostgreSQL dialect. Every later
stage inspects that one expression instead of re-parsing the string.
"""

from __future__ import annotations

import sqlglot

from src.validator.permission_validator import PermissionValidator
from src.validator.safety_validator import SafetyValidator
from src.validator.semantic_validator import SemanticValidator
from src.validator.validation_result import ValidationResult

DIALECT = "postgres"


def parse(query: str):
    """Parse one PostgreSQL statement. Returns ``(expression, ValidationResult)``.

    Rejects stacked statements outright: ``SELECT 1; DROP TABLE t`` parses as two
    statements, and validating only the first would wave the second straight through.
    """
    try:
        statements = sqlglot.parse(query, dialect=DIALECT)
    except Exception as error:
        return None, ValidationResult(
            valid=False, stage="Syntax", error_type="syntax", message=str(error)
        )

    statements = [statement for statement in statements if statement is not None]

    if len(statements) != 1:
        return None, ValidationResult(
            valid=False,
            stage="Syntax",
            error_type="syntax",
            message="Send exactly one SQL statement per query.",
        )

    return statements[0], None


class SQLValidator:
    def __init__(self, schema: dict | None = None, allowed_operations: set[str] | None = None):
        self.semantic = SemanticValidator(schema)
        self.permission = PermissionValidator(allowed_operations)
        self.safety = SafetyValidator()

    def validate(self, query: str) -> ValidationResult:
        expression, failure = parse(query)
        if failure is not None:
            return failure

        for validator in (self.permission, self.safety, self.semantic):
            result = validator.validate(expression)
            if not result.valid:
                return result

        return ValidationResult(valid=True, stage="Safety", message="Validation passed.")
