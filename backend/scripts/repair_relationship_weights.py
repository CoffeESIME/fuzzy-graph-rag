"""Audit legacy text weights; use --apply --backup FILE for a backed-up repair.

Run from backend: python -m scripts.repair_relationship_weights
Only valid numeric strings and repeated identical decimal confidences produced
by the old capped-addition bug are recoverable. Other corruption is reported.
"""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from shared.weights import normalize_weight


def recover_weight(value, relation, target_labels):
    try:
        return normalize_weight(value), "numeric_string"
    except ValueError:
        # These concept relations use min(1, old + incoming) during promotion
        # or ontology merging. Do not guess how arbitrary text should split.
        repeated = re.fullmatch(r"(0\.\d+|1\.0+)\1+", value)
        if (repeated and "Concept" in target_labels
                and relation in {"EVOKES", "EVOKES_CONCEPT", "EXPLORES", "DEFINES"}):
            unit = repeated.group(1)
            return min(1.0, normalize_weight(unit) * (len(value) // len(unit))), "repeated_confidence_capped_sum"
        return None, "unresolved"


def audit(session):
    rows = session.run("""
        MATCH ()-[r]->(target)
        WHERE valueType(r.weight) = 'STRING NOT NULL'
        RETURN elementId(r) AS id, r.weight AS original,
               type(r) AS relation, labels(target) AS target_labels
    """).data()
    for row in rows:
        row["replacement"], row["reason"] = recover_weight(
            row["original"], row["relation"], row["target_labels"])
    return rows


def apply_repair(tx, rows):
    repairs = [row for row in rows if row["replacement"] is not None]
    result = tx.run("""
        UNWIND $rows AS row
        MATCH ()-[r]->() WHERE elementId(r) = row.id AND r.weight = row.original
        SET r.weight = row.replacement
        RETURN count(r) AS updated
    """, rows=repairs).single()["updated"]
    if result != len(repairs):
        raise RuntimeError("Graph changed after audit; transaction rolled back. Audit again.")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    if args.apply and not args.backup:
        parser.error("--apply requires --backup FILE (created before any writes)")

    from config.settings import get_settings
    from neo4j import GraphDatabase
    settings = get_settings()
    with GraphDatabase.driver(settings.NEO4J_URI,
                              auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD)) as driver:
        with driver.session() as session:
            rows = audit(session)
            summary = {"text_weights": len(rows),
                       "recoverable": sum(r["replacement"] is not None for r in rows),
                       "unresolved": sum(r["replacement"] is None for r in rows)}
            print(json.dumps(summary))
            if args.apply:
                args.backup.parent.mkdir(parents=True, exist_ok=True)
                with args.backup.open("x", encoding="utf-8") as backup:
                    json.dump({"timestamp": datetime.now(timezone.utc).isoformat(),
                               "relationships": rows}, backup, indent=2)
                print(json.dumps({"updated": session.execute_write(apply_repair, rows)}))


if __name__ == "__main__":
    main()
