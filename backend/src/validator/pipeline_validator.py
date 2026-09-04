"""Validation for MongoDB aggregation pipelines.

The SQL side needs a parser because SQL is a string. A pipeline is already a
list of dicts, so there is nothing to parse - the whole check is "is this the
shape we expect, and does it contain only stages that read".

Error types match the SQL validator's, because the system prompt tells the
model what to do with each one: ``syntax`` and ``semantic`` mean fix it and
retry, ``permission`` and ``safety`` mean stop.
"""

from __future__ import annotations

import json
from typing import Any

from src.validator.validation_result import ValidationResult

# Stages that only read. Everything not listed is refused rather than reasoned
# about: a new MongoDB release adding a writing stage must not open a hole.
ALLOWED_STAGES = frozenset(
    {
        "$match", "$group", "$sort", "$limit", "$skip", "$project", "$addFields",
        "$set", "$unset", "$unwind", "$lookup", "$count", "$facet", "$sample",
        "$sortByCount", "$bucket", "$bucketAuto", "$replaceRoot", "$replaceWith",
        "$densify", "$fill", "$setWindowFields", "$graphLookup", "$redact",
    }
)

# Operators that write, or run server-side JavaScript, at any depth.
BANNED_OPERATORS = frozenset(
    {"$out", "$merge", "$where", "$function", "$accumulator", "$eval", "$expr$function"}
)


def _fail(stage: str, error_type: str, message: str) -> ValidationResult:
    return ValidationResult(valid=False, stage=stage, error_type=error_type, message=message)


def _banned_operator(node: Any) -> str | None:
    """Any banned operator, however deeply nested inside the pipeline."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(key, str) and key in BANNED_OPERATORS:
                return key
            found = _banned_operator(value)
            if found:
                return found
    elif isinstance(node, list):
        for item in node:
            found = _banned_operator(item)
            if found:
                return found
    return None


# Stages that read a second collection, always through `from`. Without this,
# a $lookup could join a collection the schema map never showed the user.
JOINING_STAGES = frozenset({"$lookup", "$graphLookup"})


def _check_stages(pipeline: list, where: str, referenced: set[str]) -> ValidationResult | None:
    """Every stage is one allowed operator. Recurses into sub-pipelines, and
    collects every collection the pipeline reads for the caller to check."""
    for index, stage in enumerate(pipeline):
        if not isinstance(stage, dict) or len(stage) != 1:
            return _fail(
                "Syntax",
                "syntax",
                f"{where} stage {index} must be an object with exactly one stage operator.",
            )

        name, body = next(iter(stage.items()))

        if name not in ALLOWED_STAGES:
            return _fail(
                "Permission",
                "permission",
                f"The {name} stage is not allowed on this connection.",
            )

        if name in JOINING_STAGES and isinstance(body, dict):
            target = body.get("from")
            if isinstance(target, str):
                referenced.add(target)

        for nested in _sub_pipelines(name, body):
            failure = _check_stages(nested, f"{name} sub-pipeline", referenced)
            if failure is not None:
                return failure

    return None


def _sub_pipelines(name: str, body: Any) -> list[list]:
    """Stages that carry pipelines of their own.

    Deliberately narrow. A `$match` body is full of lists of objects - `$or`,
    `$and`, `$in` - and walking into those would reject `{"$or": [...]}` as an
    unknown stage.
    """
    if name == "$facet" and isinstance(body, dict):
        return [value for value in body.values() if isinstance(value, list)]
    if isinstance(body, dict) and isinstance(body.get("pipeline"), list):
        return [body["pipeline"]]
    return []


def parse(query: str) -> tuple[dict | None, ValidationResult | None]:
    """Parse the model's argument into ``{"collection", "pipeline"}``."""
    try:
        request = json.loads(query)
    except (TypeError, json.JSONDecodeError) as error:
        return None, _fail("Syntax", "syntax", f"Not valid JSON: {error}")

    if not isinstance(request, dict):
        return None, _fail(
            "Syntax",
            "syntax",
            'Send an object: {"collection": "name", "pipeline": [ ... ]}.',
        )

    collection = request.get("collection")
    pipeline = request.get("pipeline")

    if not isinstance(collection, str) or not collection:
        return None, _fail("Syntax", "syntax", 'Missing "collection".')
    if not isinstance(pipeline, list):
        return None, _fail("Syntax", "syntax", '"pipeline" must be an array of stages.')

    return {"collection": collection, "pipeline": pipeline}, None


class PipelineValidator:
    def __init__(self, collections: set[str] | None = None):
        self.collections = collections

    def validate(self, query: str) -> ValidationResult:
        request, failure = parse(query)
        if failure is not None:
            return failure

        banned = _banned_operator(request["pipeline"])
        if banned:
            return _fail("Safety", "safety", f"{banned} is not allowed.")

        # Every collection this pipeline touches, not just the one it runs on:
        # a $lookup reads its `from` collection just as directly.
        referenced = {request["collection"]}
        failure = _check_stages(request["pipeline"], "Pipeline", referenced)
        if failure is not None:
            return failure

        if self.collections is not None:
            unknown = sorted(referenced - self.collections)
            if unknown:
                return _fail(
                    "Semantic", "semantic", f"There is no collection named {unknown[0]}."
                )

        return ValidationResult(valid=True, stage="Safety", message="Validation passed.")
