"""Run with unittest; GRAPH_WEIGHT_INTEGRATION=1 also tests Cypher on Neo4j.

Integration fixtures and promotion writes are always rolled back.
"""
import ast
from contextlib import nullcontext
import logging
import os
from pathlib import Path
import sys
from typing import Any, Dict, List
import unittest
from unittest.mock import Mock
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError, field_validator

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from shared.weights import normalize_weight, normalize_entities, normalize_suggestions
from scripts.repair_relationship_weights import recover_weight, apply_repair


def load_definitions(filename, names, namespace):
    tree = ast.parse((BACKEND / filename).read_text(encoding="utf-8"))
    definitions = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
    for node in definitions:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
    exec(compile(ast.Module(body=definitions, type_ignores=[]), filename, "exec"), namespace)
    return namespace


def inbox_namespace():
    return load_definitions("app/routers/inbox.py", {
        "ApprovalPayload", "promote_inbox_to_graph", "filter_redundant_tags", "sanitize_rel_type"
    }, dict(globals(), ALLOWED_RELATIONSHIPS={"EVOKES", "MENTIONS"}, logger=logging.getLogger(__name__)))


class WeightValidationTests(unittest.TestCase):
    def test_valid_values_and_defaults(self):
        for value in (0, 1, 0.9, "0.9", "1.0", " 0.5 "):
            self.assertIsInstance(normalize_weight(value), float)
        self.assertEqual(normalize_suggestions([{}], 0.5), [{"confidence": 0.5}])

    def test_invalid_values_rejected(self):
        for value in (True, False, None, [], {}, "", "NaN", "Infinity", float("nan"),
                      float("inf"), -0.1, 1.1, "0.90.9", "1.01.0", "90%"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize_weight(value)

    def test_payload_normalizes_all_categories_without_mutation(self):
        payload = inbox_namespace()["ApprovalPayload"]
        entities = {kind: [{"name": "Example", "confidence": "0.9"}]
                    for kind in ("persons", "locations", "organizations", "events", "projects", "concepts")}
        parsed = payload(entities=entities, concepts=[{"name": "Idea", "confidence": "0.6"}])
        self.assertTrue(all(items[0]["confidence"] == 0.9 for items in parsed.entities.values()))
        self.assertEqual(parsed.concepts[0]["confidence"], 0.6)
        self.assertEqual(entities["persons"][0]["confidence"], "0.9")
        with self.assertRaises(ValidationError):
            payload(entities=entities, concepts=[{"confidence": "1.01.0"}])

    def test_entire_promotion_validated_before_opening_session(self):
        driver = Mock()
        with self.assertRaises(ValueError):
            inbox_namespace()["promote_inbox_to_graph"](
                driver, "asset", {"persons": [{"name": "Valid", "confidence": "0.9"}]},
                [{"name": "Invalid", "confidence": "NaN"}], [])
        driver.session.assert_not_called()

    def test_recovery_is_conservative(self):
        for raw in ("1.01.0", "1.01.01.01.0", "0.90.9"):
            self.assertEqual(recover_weight(raw, "EVOKES", ["Concept"])[0], 1.0)
        self.assertEqual(recover_weight("0.9", "MENTIONS", ["Person"])[0], 0.9)
        for raw, rel, labels in [("0.90.8", "EVOKES", ["Concept"]),
                                 ("1.01.0", "MENTIONS", ["Person"]),
                                 ("bad", "EVOKES", ["Concept"])]:
            self.assertIsNone(recover_weight(raw, rel, labels)[0])


@unittest.skipUnless(os.getenv("GRAPH_WEIGHT_INTEGRATION") == "1", "opt-in Neo4j rollback tests")
class WeightCypherTests(unittest.TestCase):
    def setUp(self):
        from config.settings import get_settings
        from neo4j import GraphDatabase
        s = get_settings()
        self.driver = GraphDatabase.driver(s.NEO4J_URI, auth=(s.NEO4J_USER, s.NEO4J_PASSWORD))
        self.session = self.driver.session()
        self.tx = self.session.begin_transaction()
        self.addCleanup(self.driver.close)
        self.addCleanup(self.session.close)
        self.addCleanup(self.tx.rollback)
        self.adapter = Mock(session=lambda: nullcontext(self.tx))
        self.analysis = load_definitions("app/routers/analysis.py", {
            "analyze_fog_of_war", "analyze_abstract_concepts", "analyze_weight_distribution"
        }, {"get_neo4j_driver": lambda: self.adapter})

    def test_real_queries_handle_legacy_strings_invalid_values_and_one(self):
        fog = self.analysis["analyze_fog_of_war"]
        before = fog()
        self.assertEqual(before["status"], "success")
        token = "weight-test-" + uuid4().hex
        self.tx.run("""CREATE (c:Concept {name: $name})
            WITH c UNWIND ['0.9', '1.0', '1.01.0', 'bad', null, '-0.1', '1.1'] AS weight
            CREATE (:DigitalAsset)-[:EVOKES {weight: weight}]->(c)""", name=token).consume()
        after = fog()
        self.assertEqual(after["status"], "success")
        self.assertEqual(after["mock_data"]["total_edges"] - before["mock_data"]["total_edges"], 2)
        self.assertEqual(after["mock_data"]["distribution"][9]["count"] - before["mock_data"]["distribution"][9]["count"], 2)
        # Restrict only the scatter fixture by adapting the actual query's MATCH.
        tx = self.tx
        class FixtureSession:
            def run(self, query):
                return tx.run(query.replace("(c:Concept)", "(c:Concept {name: $name})"), name=token)
        self.analysis["get_neo4j_driver"] = lambda: Mock(session=lambda: nullcontext(FixtureSession()))
        result = self.analysis["analyze_abstract_concepts"]()
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["mock_data"]["series"][0]["data"], [{"name": token, "x": 7, "y": 0.95}])

    def test_promotion_converts_and_adds_legacy_text_numerically(self):
        token = "weight-test-" + uuid4().hex
        self.tx.run("CREATE (:DigitalAsset {file_hash: $id})", id=token).consume()
        promote = inbox_namespace()["promote_inbox_to_graph"]
        promote(self.adapter, token, {}, [{"name": token, "confidence": "0.3"}], [])
        self.tx.run("MATCH (:DigitalAsset {file_hash: $id})-[r]->(:Concept) SET r.weight = '0.3'", id=token).consume()
        promote(self.adapter, token, {}, [{"name": token, "confidence": "0.3"}], [])
        result = self.tx.run("MATCH (:DigitalAsset {file_hash: $id})-[r]->(:Concept) RETURN r.weight AS weight", id=token).single()
        self.assertEqual(result["weight"], 0.6)
        promote(self.adapter, token, {}, [{"name": token, "confidence": "0.9"}], [])
        result = self.tx.run("MATCH (:DigitalAsset {file_hash: $id})-[r]->(:Concept) RETURN r.weight AS weight", id=token).single()
        self.assertEqual(result["weight"], 1.0)

    def test_repair_updates_only_audited_values(self):
        row = self.tx.run("CREATE ()-[r:EVOKES {weight: '0.90.9'}]->(:Concept) RETURN elementId(r) AS id").single()
        repairs = [{"id": row["id"], "original": "0.90.9", "replacement": 1.0}]
        self.assertEqual(apply_repair(self.tx, repairs), 1)
        with self.assertRaises(RuntimeError):
            apply_repair(self.tx, repairs)


if __name__ == "__main__":
    unittest.main()
