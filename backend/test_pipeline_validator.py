"""The Mongo pipeline validator: what gets through and what does not."""

import json
import sys

sys.path.insert(0, ".")

from src.datasource.mongo import jsonable
from src.validator.pipeline_validator import PipelineValidator

V = PipelineValidator(collections={"orders", "customers"})


def check(collection, pipeline):
    return V.validate(json.dumps({"collection": collection, "pipeline": pipeline}))


def test_reads_pass():
    assert check("orders", [{"$match": {"status": "paid"}}, {"$count": "n"}]).valid
    # $or is a list of objects inside $match - it must not be read as stages.
    assert check("orders", [{"$match": {"$or": [{"a": 1}, {"b": 2}]}}]).valid
    assert check("orders", [{"$lookup": {"from": "customers", "pipeline": [{"$match": {}}]}}]).valid
    assert check("orders", [{"$facet": {"top": [{"$sort": {"total": -1}}, {"$limit": 5}]}}]).valid


def test_writes_are_refused():
    for pipeline in (
        [{"$match": {}}, {"$out": "stolen"}],
        [{"$merge": {"into": "orders"}}],
        [{"$match": {"$where": "true"}}],
        [{"$group": {"_id": None, "n": {"$accumulator": {}}}}],
        # Hidden one stage deep, inside a $lookup's own pipeline.
        [{"$lookup": {"from": "customers", "pipeline": [{"$out": "stolen"}]}}],
    ):
        result = check("orders", pipeline)
        assert not result.valid, pipeline
        assert result.error_type in {"safety", "permission"}, result


def test_bad_shapes():
    assert V.validate("not json").error_type == "syntax"
    assert V.validate('{"collection": "orders"}').error_type == "syntax"
    assert V.validate('["a"]').error_type == "syntax"
    assert check("orders", [{"$match": {}, "$sort": {}}]).error_type == "syntax"
    assert check("nope", [{"$match": {}}]).error_type == "semantic"


def test_joins_may_only_reach_known_collections():
    """A $lookup reads its `from` collection as directly as the one it runs on."""
    for pipeline in (
        [{"$lookup": {"from": "secrets", "localField": "a", "foreignField": "b", "as": "c"}}],
        [{"$graphLookup": {"from": "secrets", "startWith": "$a", "as": "c"}}],
        # Buried in a sub-pipeline, where the stage walk has to find it.
        [{"$facet": {"x": [{"$lookup": {"from": "secrets", "as": "c"}}]}}],
        [{"$lookup": {"from": "customers", "pipeline": [{"$lookup": {"from": "secrets", "as": "c"}}]}}],
    ):
        result = check("orders", pipeline)
        assert result.error_type == "semantic", (pipeline, result)
        assert "secrets" in result.message, result

    # A join to a collection that is in the snapshot is still fine.
    assert check("orders", [{"$lookup": {"from": "customers", "as": "c"}}]).valid


def test_bson_is_made_serialisable():
    class ObjectId:
        def __str__(self):
            return "507f1f77"

    rows = jsonable([{"_id": ObjectId(), "tags": ["a"], "n": 3, "missing": None}])
    json.dumps(rows)  # would raise if anything survived unconverted
    assert rows[0]["_id"] == "507f1f77"


if __name__ == "__main__":
    for name, test in sorted(globals().items()):
        if name.startswith("test_"):
            test()
            print(f"ok  {name}")
