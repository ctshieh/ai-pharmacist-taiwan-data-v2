#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
DEFAULT_MANIFEST_PATH = DIST_DIR / "manifest.json"
DEFAULT_SQLITE_PATH = DIST_DIR / "safemed-mobile-safety-v2-test.sqlite3"
DEFAULT_GZIP_PATH = DIST_DIR / "safemed-mobile-safety-v2-test.sqlite3.gz"

STATUS_RANK = {"GREEN": 0, "BLUE": 1, "ORANGE": 2, "RED": 3}


@dataclass(frozen=True)
class LockedCase:
    label: str
    names: tuple[str, ...]
    expected_status: str
    required_hits: tuple[str, ...]


LOCKED_CASES = (
    LockedCase("Warfarin duplicate", ("Warfarin", "Coumadin"), "RED", ("duplicate_ingredient_int:101",)),
    LockedCase("Warfarin + NSAID", ("Warfarin", "Ibuprofen"), "RED", ("ANTICOAGULANT_NSAID",)),
    LockedCase("Digoxin + Amiodarone", ("Lanoxin", "Cordarone"), "ORANGE", ("DIGOXIN_PGP_INHIBITOR",)),
    LockedCase("Anticoagulant + antiplatelet", ("Warfarin", "Clopidogrel"), "RED", ("ANTICOAGULANT_ANTIPLATELET",)),
    LockedCase("Opioid + sedative", ("Tramadol", "Lorazepam"), "RED", ("OPIOID_SEDATIVE_RESPIRATORY_DEPRESSION",)),
    LockedCase("Methotrexate + TMP-SMX", ("Methotrexate", "TMP-SMX"), "RED", ("METHOTREXATE_TMP_SMX",)),
    LockedCase("Statin + strong CYP3A4 inhibitor", ("Simvastatin", "Clarithromycin"), "RED", ("STATIN_STRONG_CYP3A4_INHIBITOR",)),
    LockedCase("Lithium + ACEI", ("Lithium", "Lisinopril"), "RED", ("LITHIUM_ACE_ARB",)),
    LockedCase("Dual RAS blockade", ("Lisinopril", "Losartan"), "RED", ("DUAL_RAS_BLOCKADE",)),
    LockedCase("NSAID + ACEI/ARB + diuretic", ("Ibuprofen", "Lisinopril", "Furosemide"), "ORANGE", ("NSAID_ACE_ARB_DIURETIC_RENAL_RISK",)),
    LockedCase("QT-risk combination", ("Cordarone", "Clarithromycin"), "ORANGE", ("QT_RISK_COMBINATION",)),
    LockedCase("Green negative control", ("Metformin", "Acetaminophen"), "GREEN", ()),
)


def normalize(value: str) -> str:
    return re.sub(r"[\s　,，、。/／()（）\[\]「」『』\"'`.\-]", "", value.strip().lower())


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair_key(left: int, right: int) -> str:
    low, high = sorted((left, right))
    return f"{low}:{high}"


def load_json(text: str) -> Any:
    return json.loads(text or "[]")


def rule_lookup(db: sqlite3.Connection, table: str) -> dict[str, list[tuple[str, str]]]:
    rows = db.execute(
        f"""
        SELECT pair_rules.pair_key, rules.rule_code, rules.severity
        FROM {table} AS pair_rules
        JOIN rules ON rules.rule_id = pair_rules.rule_id;
        """
    ).fetchall()
    lookup: dict[str, list[tuple[str, str]]] = {}
    for row in rows:
        lookup.setdefault(row["pair_key"], []).append((row["rule_code"], row["severity"]))
    return lookup


def drug_for_name(db: sqlite3.Connection, name: str) -> dict[str, Any]:
    rows = db.execute(
        """
        SELECT drugs.drug_id, drugs.display_name, drugs.data_completeness
        FROM drug_aliases
        JOIN drugs ON drugs.drug_id = drug_aliases.drug_id
        WHERE drug_aliases.normalized_alias = ?
        ORDER BY
            CASE WHEN drug_aliases.normalized_alias = drugs.display_name COLLATE NOCASE THEN 0 ELSE 1 END,
            CASE WHEN drug_aliases.alias_type = 'DISPLAY_NAME' THEN 0 ELSE 1 END,
            drugs.drug_id;
        """,
        (normalize(name),),
    ).fetchall()
    if not rows:
        raise AssertionError(f"No drug alias found for {name}")

    row = rows[0]
    compact = db.execute(
        """
        SELECT ingredient_int_ids_json, class_int_ids_json
        FROM drug_compact_index
        WHERE drug_id = ?;
        """,
        (row["drug_id"],),
    ).fetchone()
    if compact is None:
        raise AssertionError(f"{row['drug_id']} lacks drug_compact_index")

    class_ids = [
        item["class_id"]
        for item in db.execute(
            "SELECT class_id FROM drug_class_memberships WHERE drug_id = ?;",
            (row["drug_id"],),
        ).fetchall()
    ]
    return {
        "drug_id": row["drug_id"],
        "display_name": row["display_name"],
        "data_completeness": row["data_completeness"],
        "ingredient_int_ids": load_json(compact["ingredient_int_ids_json"]),
        "class_int_ids": load_json(compact["class_int_ids_json"]),
        "class_ids": class_ids,
    }


def add_hit(hits: dict[str, str], hit_id: str, severity: str) -> None:
    if hit_id not in hits or STATUS_RANK[severity] > STATUS_RANK[hits[hit_id]]:
        hits[hit_id] = severity


def assess_case(db: sqlite3.Connection, names: tuple[str, ...]) -> tuple[str, set[str]]:
    records = [drug_for_name(db, name) for name in names]
    ingredient_rules = rule_lookup(db, "ingredient_pair_rules")
    class_rules = rule_lookup(db, "class_pair_rules")
    hits: dict[str, str] = {}

    ingredient_to_drugs: dict[int, set[str]] = {}
    for record in records:
        if record["data_completeness"] != "COMPLETE":
            add_hit(hits, f"DATA_GAP_{record['drug_id']}", "BLUE")
        for ingredient_int_id in record["ingredient_int_ids"]:
            ingredient_to_drugs.setdefault(int(ingredient_int_id), set()).add(record["drug_id"])
    for ingredient_int_id, drug_ids in ingredient_to_drugs.items():
        if len(drug_ids) > 1:
            add_hit(hits, f"duplicate_ingredient_int:{ingredient_int_id}", "RED")

    for left_index, left in enumerate(records):
        for right in records[left_index + 1 :]:
            for left_ingredient in left["ingredient_int_ids"]:
                for right_ingredient in right["ingredient_int_ids"]:
                    for code, severity in ingredient_rules.get(pair_key(int(left_ingredient), int(right_ingredient)), []):
                        add_hit(hits, code, severity)
            for left_class in left["class_int_ids"]:
                for right_class in right["class_int_ids"]:
                    for code, severity in class_rules.get(pair_key(int(left_class), int(right_class)), []):
                        add_hit(hits, code, severity)

    for row in db.execute(
        """
        SELECT multi_class_pattern_rules.required_class_ids_json,
               multi_class_pattern_rules.min_distinct_drugs,
               rules.rule_code,
               rules.severity
        FROM multi_class_pattern_rules
        JOIN rules ON rules.rule_id = multi_class_pattern_rules.rule_id;
        """
    ).fetchall():
        required_class_ids = set(load_json(row["required_class_ids_json"]))
        present_class_ids = {class_id for record in records for class_id in record["class_ids"]}
        if not required_class_ids.issubset(present_class_ids):
            continue
        distinct_drug_count = sum(
            1 for record in records if required_class_ids.intersection(record["class_ids"])
        )
        if distinct_drug_count >= int(row["min_distinct_drugs"]):
            add_hit(hits, row["rule_code"], row["severity"])

    status = "GREEN"
    for severity in hits.values():
        if STATUS_RANK[severity] > STATUS_RANK[status]:
            status = severity
    return status, set(hits)


def validate_manifest(manifest_path: Path, sqlite_path: Path, gzip_path: Path) -> None:
    manifest = json.loads(manifest_path.read_text())
    expected = {
        "schema_version": "safemed-mobile-safety-v2",
        "package_major_version": 2,
        "product_line": "safemed_pro",
        "package_format": "sqlite3+gzip",
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise AssertionError(f"manifest {key} expected {value}, got {manifest.get(key)}")
    if 2 not in manifest.get("compatible_app_major_versions", []):
        raise AssertionError("manifest compatible_app_major_versions must include 2")
    if manifest.get("gzip_sha256") != sha256_file(gzip_path):
        raise AssertionError("manifest gzip_sha256 does not match gzip asset")
    if manifest.get("sqlite_sha256") != sha256_file(sqlite_path):
        raise AssertionError("manifest sqlite_sha256 does not match sqlite asset")


def validate_database(db: sqlite3.Connection) -> None:
    db.row_factory = sqlite3.Row
    integrity = db.execute("PRAGMA integrity_check;").fetchone()[0]
    if str(integrity).lower() != "ok":
        raise AssertionError(f"SQLite integrity_check failed: {integrity}")

    package = db.execute("SELECT * FROM package_manifest LIMIT 1;").fetchone()
    if package["schema_version"] != "safemed-mobile-safety-v2":
        raise AssertionError("package_manifest schema_version mismatch")
    if package["package_major_version"] != "2":
        raise AssertionError("package_manifest package_major_version mismatch")

    quality_queries = {
        "drugs without active ingredient": """
            SELECT COUNT(*) FROM drugs
            WHERE drug_id NOT IN (SELECT drug_id FROM drug_ingredients WHERE role = 'ACTIVE')
        """,
        "drugs without class membership": """
            SELECT COUNT(*) FROM drugs
            WHERE drug_id NOT IN (SELECT drug_id FROM drug_class_memberships)
        """,
        "drugs without compact index": """
            SELECT COUNT(*) FROM drugs
            WHERE drug_id NOT IN (SELECT drug_id FROM drug_compact_index)
        """,
        "RED/ORANGE rules without sources": """
            SELECT COUNT(*) FROM rules
            WHERE severity IN ('RED', 'ORANGE')
              AND rule_id NOT IN (SELECT rule_id FROM rule_sources)
        """,
        "active herb-western candidates": """
            SELECT COUNT(*) FROM herb_western_candidate_rules
            WHERE candidate_status = 'ACTIVE'
        """,
    }
    for label, query in quality_queries.items():
        count = int(db.execute(query).fetchone()[0])
        if count:
            raise AssertionError(f"{label}: {count}")

    duplicate_rule_count = int(
        db.execute("SELECT COUNT(*) FROM therapeutic_duplicate_rules;").fetchone()[0]
    )
    if duplicate_rule_count < 1:
        raise AssertionError("expected at least one therapeutic_duplicate_rules row")

    tmp_smx_count = int(
        db.execute(
            """
            SELECT COUNT(*) FROM drug_ingredients
            WHERE drug_id = 'drug_tmp_smx' AND role = 'ACTIVE';
            """
        ).fetchone()[0]
    )
    if tmp_smx_count != 2:
        raise AssertionError(f"TMP-SMX expected 2 active ingredients, got {tmp_smx_count}")

    official_source_count = int(
        db.execute(
            """
            SELECT COUNT(*) FROM source_registry
            WHERE source_id IN (
                'mohw_herb_western_database_announcement',
                'mohw_docmap_cmthp_integrated_query',
                'mohw_nhia_medicloud_danshen_aspirin_notice'
            );
            """
        ).fetchone()[0]
    )
    if official_source_count != 3:
        raise AssertionError("expected all three official MOHW herb-western source entries")

    danshen_aspirin = db.execute(
        """
        SELECT suggested_runtime_status, candidate_status
        FROM herb_western_candidate_rules
        WHERE candidate_id = 'cand_danshen_aspirin';
        """
    ).fetchone()
    if danshen_aspirin is None:
        raise AssertionError("missing cand_danshen_aspirin candidate")
    if danshen_aspirin["suggested_runtime_status"] != "BLUE":
        raise AssertionError("cand_danshen_aspirin must remain BLUE")
    if danshen_aspirin["candidate_status"] == "ACTIVE":
        raise AssertionError("cand_danshen_aspirin must not be ACTIVE")

    for case in LOCKED_CASES:
        status, hits = assess_case(db, case.names)
        if status != case.expected_status:
            raise AssertionError(f"{case.label}: expected {case.expected_status}, got {status}, hits={sorted(hits)}")
        missing_hits = set(case.required_hits).difference(hits)
        if missing_hits:
            raise AssertionError(f"{case.label}: missing hits {sorted(missing_hits)}, got {sorted(hits)}")
        if case.expected_status == "GREEN" and any(hit.startswith("DATA_GAP_") for hit in hits):
            raise AssertionError(f"{case.label}: unexpected data gap hits {sorted(hits)}")


def with_sqlite_path(sqlite_path: Path, gzip_path: Path) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if sqlite_path.exists():
        return sqlite_path, None
    if not gzip_path.exists():
        raise FileNotFoundError(f"Neither {sqlite_path} nor {gzip_path} exists")
    temp_dir = tempfile.TemporaryDirectory()
    extracted_path = Path(temp_dir.name) / "package.sqlite3"
    with gzip.open(gzip_path, "rb") as source, extracted_path.open("wb") as target:
        shutil.copyfileobj(source, target)
    return extracted_path, temp_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the SafeMed V2 test package.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST_PATH)
    parser.add_argument("--sqlite", type=Path, default=DEFAULT_SQLITE_PATH)
    parser.add_argument("--gzip", type=Path, default=DEFAULT_GZIP_PATH)
    args = parser.parse_args()

    sqlite_path, temp_dir = with_sqlite_path(args.sqlite, args.gzip)
    try:
        validate_manifest(args.manifest, sqlite_path, args.gzip)
        db = sqlite3.connect(sqlite_path)
        db.row_factory = sqlite3.Row
        try:
            validate_database(db)
        finally:
            db.close()
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()

    print("SafeMed V2 test package validation passed.")


if __name__ == "__main__":
    main()
