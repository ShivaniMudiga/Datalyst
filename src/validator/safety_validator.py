import sqlglot

from sqlglot import expressions as exp

from src.validator.validation_result import ValidationResult


class SafetyValidator:

    def validate(self, query: str) -> ValidationResult:

        try:
            expression = sqlglot.parse_one(query)

        except Exception:
            return ValidationResult(
                valid=False,
                stage="Safety",
                error_type="safety",
                message="Unable to parse SQL."
            )

        # -------------------------
        # Block DROP
        # -------------------------

        if isinstance(expression, exp.Drop):

            return ValidationResult(
                valid=False,
                stage="Safety",
                error_type="safety",
                message="DROP statements are not allowed."
            )

        # -------------------------
        # Block TRUNCATE
        # -------------------------

        if expression.key.upper().startswith("TRUNCATE"):

            return ValidationResult(
                valid=False,
                stage="Safety",
                error_type="safety",
                message="TRUNCATE statements are not allowed."
            )

        # -------------------------
        # Block ALTER
        # -------------------------

        if isinstance(expression, exp.Alter):

            return ValidationResult(
                valid=False,
                stage="Safety",
                error_type="safety",
                message="ALTER statements are not allowed."
            )

        # -------------------------
        # DELETE must have WHERE
        # -------------------------

        if isinstance(expression, exp.Delete):

            if expression.find(exp.Where) is None:

                return ValidationResult(
                    valid=False,
                    stage="Safety",
                    error_type="safety",
                    message="DELETE without WHERE is not allowed."
                )

        # -------------------------
        # UPDATE must have WHERE
        # -------------------------

        if isinstance(expression, exp.Update):

            if expression.find(exp.Where) is None:

                return ValidationResult(
                valid=False,
                stage="Safety",
                error_type="safety",
                message="UPDATE without WHERE is not allowed."
            )

        return ValidationResult(
            valid=True,
            stage="Safety",
            message="Safety validation passed."
        )