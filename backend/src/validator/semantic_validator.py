"""Do the tables and columns in this query actually exist?

CTEs and derived tables are names the query defines for itself. They are not in
the schema and must not be checked against it - rejecting them would rule out
exactly the multi-step analytical queries this product is for.
"""

from __future__ import annotations

from sqlglot import expressions as exp

from src.validator.validation_result import ValidationResult


def _fail(message: str) -> ValidationResult:
    return ValidationResult(
        valid=False, stage="Semantic", error_type="semantic", message=message
    )


class SemanticValidator:
    def __init__(self, schema: dict | None = None):
        self._schema = schema

    def validate(self, expression: exp.Expression) -> ValidationResult:
        schema = self._schema
        if schema is None:
            # No snapshot read yet, so there is nothing to check names against.
            # Permission and safety have already run; let it through.
            return ValidationResult(
                valid=True, stage="Semantic", message="No schema to check against."
            )

        # Names the query defines for itself: CTEs and derived tables.
        local_names = {cte.alias_or_name for cte in expression.find_all(exp.CTE)}
        local_names |= {
            subquery.alias_or_name
            for subquery in expression.find_all(exp.Subquery)
            if subquery.alias_or_name
        }

        # alias (or bare name) -> real table, for the tables that are real.
        sources: dict[str, str] = {}
        for table in expression.find_all(exp.Table):
            if table.name in local_names:
                continue
            if table.db and table.db != "public":
                # Another schema, e.g. information_schema. Not ours to check.
                sources[table.alias_or_name] = ""
                continue
            if table.name not in schema:
                return _fail(f"Table '{table.name}' does not exist.")
            sources[table.alias_or_name] = table.name

        for column in expression.find_all(exp.Column):
            qualifier = column.table

            if qualifier:
                if qualifier in local_names:
                    continue  # a CTE's or subquery's own output column
                table_name = sources.get(qualifier)
                if not table_name:
                    continue  # unknown or non-public qualifier
            elif len(sources) == 1 and not local_names:
                # ponytail: unqualified columns are only resolved when the query has
                # exactly one real source and no self-defined names. Anything more
                # needs real scope resolution (sqlglot.optimizer.qualify); until then
                # we skip rather than risk rejecting a valid query.
                table_name = next(iter(sources.values()))
                if not table_name:
                    continue
            else:
                continue

            if column.name != "*" and column.name not in schema[table_name]:
                return _fail(
                    f"Column '{column.name}' does not exist in table '{table_name}'."
                )

        return ValidationResult(
            valid=True, stage="Semantic", message="Semantic validation passed."
        )
