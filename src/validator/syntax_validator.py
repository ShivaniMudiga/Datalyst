import sqlglot

from src.validator.validation_result import ValidationResult


class SyntaxValidator:

    def validate(self, query: str) -> ValidationResult:

        try:
            sqlglot.parse_one(query)

            return ValidationResult(
                valid=True,
                stage="Syntax",
                message="SQL syntax is valid."
            )

        except Exception as e:

            return ValidationResult(
                valid=False,
                stage="Syntax",
                error_type="syntax",
                message=str(e)
            )