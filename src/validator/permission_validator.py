import json
import sqlglot

from src.validator.validation_result import ValidationResult


class PermissionValidator:

    def __init__(self):

        with open("config/permissions.json", "r") as file:
            self.permissions = json.load(file)

    def validate(self, query: str) -> ValidationResult:

        try:
            expression = sqlglot.parse_one(query)

        except Exception:
            return ValidationResult(
                valid=False,
                stage="Permission",
                error_type="permission",
                message="Unable to parse SQL."
            )

        operation = expression.key.upper()

        allowed_operations = self.permissions["allowed_operations"]

        if operation not in allowed_operations:

            return ValidationResult(
            valid=False,
            stage="Permission",
            error_type="permission",
            message=f"{operation} operations are not allowed."
        )

        return ValidationResult(
            valid=True,
            stage="Permission",
            message=f"{operation} operation is permitted."
        )