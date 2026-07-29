import sqlglot
from sqlglot import expressions as exp

from src.explorer.schema_explorer import SchemaExplorer
from src.validator.validation_result import ValidationResult


class SemanticValidator:

    def __init__(self):
        self.schema = SchemaExplorer().get_database_schema()

    def validate(self, query: str) -> ValidationResult:

        try:

            expression = sqlglot.parse_one(query)

        except Exception:

            return ValidationResult(
                valid=False,
                stage="Semantic",
                message="Unable to parse SQL."
            )

        # -----------------------------
        # Validate tables
        # -----------------------------

        tables = [
            table.name
            for table in expression.find_all(exp.Table)
        ]

        for table in tables:

            if table not in self.schema:

                return ValidationResult(
                    valid=False,
                    stage="Semantic",
                    error_type="semantic",
                    message=f"Table '{table}' does not exist."
                )

        # -----------------------------
        # Validate columns
        # -----------------------------

        if len(tables) == 1:

            table_name = tables[0]

            valid_columns = self.schema[table_name].keys()

            columns = [
                column.name
                for column in expression.find_all(exp.Column)
            ]

            for column in columns:

                if column == "*":
                    continue

                if column not in valid_columns:

                    return ValidationResult(
                valid=False,
                stage="Semantic",
                error_type="semantic",
                message=f"Column '{column}' does not exist in table '{table}'."
            )

        return ValidationResult(
            valid=True,
            stage="Semantic",
            message="Semantic validation passed."
        )