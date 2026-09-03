"""End-to-end check of the MongoDB path, against a real MongoDB.

    docker run -d --name ttmd-mongo -p 27017:27017 \
      -e MONGO_INITDB_ROOT_USERNAME=root -e MONGO_INITDB_ROOT_PASSWORD=secret mongo:7
    backend/.venv/bin/python test_mongo_e2e.py

Seeds a small shop database, connects to it the way the setup screen does,
and drives the same code the chat does: introspect -> store snapshot ->
run_query. Restores whatever connection was configured before it ran.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone

sys.path.insert(0, ".")

from pymongo import MongoClient

from test_support import sign_in

sign_in()

from src.agent import tools
from src.datasource.base import check, create
from src.db.chat_store import ConnectionStore
from src.graph.nodes import reset_prompt_cache, system_prompt
from src.knowledge.snapshot import read_and_store

ROOT = "mongodb://root:secret@localhost:27017/shopdb?authSource=admin"

CONNECTION = {
    "db_type": "mongodb",
    "host": "localhost",
    "port": "27017",
    "database": "shopdb",
    "username": "shop_reader",
    "password": "reader_pw",
    "permission": "read_only",
    "purpose": "Track orders and customers for a small shop.",
}

# Credentials that authenticate perfectly well and can write. Not `root`: root
# lives in `admin`, so it cannot authenticate against shopdb at all, and the
# check under test is about privileges, not authentication.
WRITER = dict(CONNECTION, username="shop_writer", password="writer_pw")


def seed() -> None:
    """A shop, and a read-only user to read it with.

    Documents are deliberately uneven - a missing field, a mixed-type field,
    an ObjectId, a date - because that is what the sampling introspection and
    the JSON coercion have to survive.
    """
    client = MongoClient(ROOT, serverSelectionTimeoutMS=8000)
    database = client["shopdb"]
    database.drop_collection("orders")
    database.drop_collection("customers")

    customers = database["customers"]
    customer_ids = customers.insert_many(
        [
            {"name": "Ada", "city": "Bengaluru", "tier": "gold"},
            {"name": "Bo", "city": "Chennai"},  # no tier: makes the field nullable
            {"name": "Cy", "city": "Bengaluru", "tier": "silver"},
        ]
    ).inserted_ids

    database["orders"].insert_many(
        [
            {
                "customer_id": customer_ids[index % 3],
                "total": 100.0 + index,
                # Mixed types on purpose: the snapshot must report both.
                "quantity": index if index % 2 else float(index),
                "status": "paid" if index % 3 else "refunded",
                "placed_at": datetime(2026, 1, 1 + index, tzinfo=timezone.utc),
            }
            for index in range(30)
        ]
    )

    database.command("dropAllUsersFromDatabase")
    database.command(
        "createUser", CONNECTION["username"], pwd=CONNECTION["password"], roles=["read"]
    )
    # The one setup must refuse: valid credentials that happen to be writable.
    database.command(
        "createUser", WRITER["username"], pwd=WRITER["password"], roles=["readWrite"]
    )
    client.close()


def query(sql: str):
    return tools.run_query(sql)


def pipeline(collection: str, stages: list) -> str:
    return json.dumps({"collection": collection, "pipeline": stages})


def main() -> None:
    store = ConnectionStore()
    previous = store.credentials()
    previous_purpose = store.get().purpose if store.get() else ""
    previous_snapshot = store.get_snapshot()

    try:
        seed()
        print("ok  seeded shopdb (3 customers, 30 orders, read-only user)")

        # 1. What the setup screen does when the user clicks Test.
        check(CONNECTION)
        print("ok  credentials accepted")

        bad = dict(CONNECTION, password="wrong")
        try:
            check(bad)
            raise AssertionError("a wrong password was accepted")
        except AssertionError:
            raise
        except Exception as error:
            assert "auth" in str(error).lower(), error
            print("ok  a wrong password is rejected")

        # Credentials that work but can write are refused: the role is the only
        # read-only gate Mongo has, so setup will not let the user skip it.
        try:
            check(WRITER)
            raise AssertionError("writable credentials were accepted")
        except AssertionError:
            raise
        except Exception as error:
            assert "can write to shopdb" in str(error), error
            assert 'role: "read"' in str(error), error
            print("ok  writable credentials are refused, with the fix in the message")

        # 2. Saving the connection, exactly as POST /connection does.
        store.save(**CONNECTION)
        tools.reset_data_source()
        reset_prompt_cache()
        source = tools.data_source()
        assert type(source).__name__ == "MongoDataSource", source
        print(f"ok  data source for db_type=mongodb is {type(source).__name__}")

        # 3. The analyse step: introspect and store the snapshot.
        events = list(read_and_store())
        snapshot = events[-1]["snapshot"]
        tables = {table["name"]: table for table in snapshot["tables"]}
        assert set(tables) == {"customers", "orders"}, tables.keys()
        assert tables["orders"]["row_count"] == 30, tables["orders"]
        assert snapshot["relationships"] == []

        columns = {c["name"]: c for c in tables["customers"]["columns"]}
        assert columns["_id"]["primary_key"] is True
        assert columns["tier"]["nullable"] is True, columns["tier"]
        assert columns["name"]["nullable"] is False, columns["name"]

        quantity = {c["name"]: c for c in tables["orders"]["columns"]}["quantity"]
        assert quantity["type"] == "double|int", quantity
        print(f"ok  introspected {snapshot['totals']['tables']} collections, "
              f"{snapshot['totals']['columns']} fields, {snapshot['totals']['rows']} documents")

        # 4. The system prompt the model actually sees.
        prompt = system_prompt()
        assert "MongoDB database" in prompt, prompt[:200]
        assert "aggregation pipeline" in prompt
        assert "orders (30 rows)" in prompt
        assert "Never send SQL" in prompt
        print("ok  system prompt is the MongoDB one, with the real schema in it")

        # 5. A real question, the way the agent asks it.
        result = query(pipeline("orders", [
            {"$match": {"status": "paid"}},
            {"$group": {"_id": "$status", "revenue": {"$sum": "$total"}, "n": {"$sum": 1}}},
        ]))
        assert result["rows"] == [{"_id": "paid", "revenue": 2300.0, "n": 20}], result
        print(f"ok  grouped query returned {result['rows']}")

        # A $lookup across collections, with no foreign key to lean on.
        result = query(pipeline("orders", [
            {"$lookup": {"from": "customers", "localField": "customer_id",
                         "foreignField": "_id", "as": "customer"}},
            {"$unwind": "$customer"},
            {"$group": {"_id": "$customer.city", "orders": {"$sum": 1}}},
            {"$sort": {"_id": 1}},
        ]))
        assert result["rows"] == [{"_id": "Bengaluru", "orders": 20},
                                  {"_id": "Chennai", "orders": 10}], result
        print(f"ok  $lookup across collections returned {result['rows']}")

        # 6. Rows survive the trip: ObjectId and datetime become JSON.
        result = query(pipeline("orders", [{"$sort": {"placed_at": 1}}, {"$limit": 1}]))
        row = result["rows"][0]
        json.dumps(row)  # raises if any BSON value survived
        assert isinstance(row["_id"], str) and isinstance(row["customer_id"], str), row
        assert row["placed_at"].startswith("2026-01-01T"), row
        print("ok  ObjectId and datetime came back JSON-serialisable")

        # 7. The row cap, and the truncation flag the prompt relies on.
        result = query(pipeline("orders", [{"$sort": {"total": 1}}]))
        capped = tools.data_source().execute(
            pipeline("orders", [{"$sort": {"total": 1}}]), row_cap=5
        )
        assert result["truncated"] is False and result["row_count"] == 30
        assert capped["truncated"] is True and capped["row_count"] == 5, capped
        print("ok  row cap truncates and reports it")

        # 8. Writes are refused by the validator, before they reach Mongo.
        for stages, error_type in (
            ([{"$match": {}}, {"$out": "stolen"}], "safety"),
            ([{"$merge": {"into": "orders"}}], "safety"),
            ([{"$collStats": {}}], "permission"),
        ):
            rejected = query(pipeline("orders", stages))
            assert rejected["status"] == "validation_failed", rejected
            assert rejected["error_type"] == error_type, rejected
        print("ok  $out, $merge and unlisted stages are refused by the validator")

        rejected = query(pipeline("secrets", [{"$match": {}}]))
        assert rejected["error_type"] == "semantic", rejected
        # A join cannot reach past the snapshot either.
        rejected = query(pipeline("orders", [{"$lookup": {"from": "secrets", "as": "c"}}]))
        assert rejected["error_type"] == "semantic", rejected
        rejected = query("SELECT * FROM orders")
        assert rejected["error_type"] == "syntax", rejected
        print("ok  unknown collections and stray SQL are refused")

        # 9. The database role is the real gate, not the validator. Connect as
        #    the same read-only user and try to write behind the validator's back.
        reader = MongoClient(
            f"mongodb://{CONNECTION['username']}:{CONNECTION['password']}"
            f"@localhost:27017/shopdb",
            serverSelectionTimeoutMS=8000,
        )
        try:
            reader["shopdb"]["orders"].insert_one({"forged": True})
            raise AssertionError("the read-only user was allowed to write")
        except AssertionError:
            raise
        except Exception as error:
            assert "not allowed" in str(error).lower() or "unauthorized" in str(error).lower(), error
            print("ok  the read-only Mongo user cannot write, even bypassing the validator")
        finally:
            reader.close()

        print("\nall checks passed")

    finally:
        tools.reset_data_source()
        if previous:
            store.save(**previous, purpose=previous_purpose, permission="read_only")
            if previous_snapshot:
                previous_snapshot.pop("stored_at", None)
                store.save_snapshot(previous_snapshot)
            print(f"restored the previous connection: {previous['database']}")
        reset_prompt_cache()
        from src.db.connection import close_all

        close_all()


if __name__ == "__main__":
    main()
