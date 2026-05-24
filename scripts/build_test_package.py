#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMA_PATH = ROOT / "schemas" / "safemed_mobile_safety_v2.sql"
SEED_PATH = ROOT / "seed" / "test_seed_v2.json"
DIST_DIR = ROOT / "dist"


def normalize(value: str) -> str:
    return re.sub(r"[\s　,，、。/／()（）\[\]「」『』\"'`.\-]", "", value.strip().lower())


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def pair_key(left: int, right: int) -> str:
    low, high = sorted((left, right))
    return f"{low}:{high}"


def insert_package_manifest(db: sqlite3.Connection, seed: dict[str, Any], created_at: str) -> None:
    package = seed["package"]
    source_snapshots = [
        {
            "source_id": item["source_id"],
            "version_label": item["version_label"],
            "source_url": item["source_url"],
        }
        for item in seed["source_registry"]
    ]
    db.execute(
        """
        INSERT INTO package_manifest (
            package_id, schema_version, package_major_version, product_line, license_tier,
            requires_entitlement, compatible_app_major_versions, data_version, rules_version,
            created_at, package_format, source_snapshots, quality_gate_result,
            locked_regression_result
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (
            package["package_id"],
            package["schema_version"],
            package["package_major_version"],
            package["product_line"],
            package["license_tier"],
            1 if package["requires_entitlement"] else 0,
            json_text(package["compatible_app_major_versions"]),
            package["data_version"],
            package["rules_version"],
            created_at,
            package["package_format"],
            json_text(source_snapshots),
            "PASS",
            "PASS",
        ),
    )


def insert_sources(db: sqlite3.Connection, seed: dict[str, Any], created_at: str) -> None:
    for item in seed["source_registry"]:
        db.execute(
            """
            INSERT INTO source_registry (
                source_id, source_name, source_url, version_label, license_note,
                source_type, retrieved_at, checksum
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                item["source_id"],
                item["source_name"],
                item["source_url"],
                item["version_label"],
                item["license_note"],
                item["source_type"],
                created_at,
                item.get("checksum"),
            ),
        )


def insert_ingredients(db: sqlite3.Connection, seed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    ingredients = {item["ingredient_id"]: item for item in seed["ingredients"]}
    for item in seed["ingredients"]:
        db.execute(
            """
            INSERT INTO ingredients (
                ingredient_id, ingredient_int_id, canonical_name, normalized_name,
                rxnorm_ingredient_rxcui, atc_seed_codes_json, synonyms_json,
                source, source_version, evidence_quality
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                item["ingredient_id"],
                item["ingredient_int_id"],
                item["canonical_name"],
                normalize(item["canonical_name"]),
                item.get("rxnorm_ingredient_rxcui"),
                json_text(item.get("atc_seed_codes", [])),
                json_text(item.get("synonyms", [])),
                "V2_TEST_SEED",
                "2026-05-24",
                "TEST_FIXTURE",
            ),
        )
    return ingredients


def insert_classes(db: sqlite3.Connection, seed: dict[str, Any]) -> dict[str, dict[str, Any]]:
    classes = {item["class_id"]: item for item in seed["classes"]}
    for item in seed["classes"]:
        db.execute(
            """
            INSERT INTO classes (
                class_id, class_int_id, class_name, class_type, parent_class_id, description
            ) VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                item["class_id"],
                item["class_int_id"],
                item["class_name"],
                item["class_type"],
                item.get("parent_class_id"),
                item["description"],
            ),
        )
    return classes


def insert_drugs(
    db: sqlite3.Connection,
    seed: dict[str, Any],
    ingredients: dict[str, dict[str, Any]],
    classes: dict[str, dict[str, Any]],
) -> None:
    for drug in seed["drugs"]:
        ingredient_ids = drug["ingredients"]
        class_ids = drug["classes"]
        active_count = len(ingredient_ids)
        is_combination = active_count > 1
        safety_class_names = [classes[class_id]["class_name"] for class_id in class_ids]
        db.execute(
            """
            INSERT INTO drugs (
                drug_id, display_name, generic_name, chinese_name, english_name, nhi_code,
                tfda_license_no, rxnorm_rxcui, atc_codes_json, ahfs_codes_json, dosage_form,
                route, source, source_version, evidence_quality, data_completeness,
                is_combination, active_ingredient_count, safety_classes_json,
                therapeutic_classes_json, metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                drug["drug_id"],
                drug["display_name"],
                drug["generic_name"],
                drug.get("chinese_name"),
                drug.get("english_name"),
                drug.get("nhi_code"),
                drug.get("tfda_license_no"),
                drug.get("rxnorm_rxcui"),
                json_text(drug.get("atc_codes", [])),
                json_text(drug.get("ahfs_codes", [])),
                drug.get("dosage_form"),
                drug.get("route"),
                "V2_TEST_SEED",
                "2026-05-24",
                "TEST_FIXTURE",
                "COMPLETE",
                1 if is_combination else 0,
                active_count,
                json_text(safety_class_names),
                json_text([]),
                json_text({"seed_note": "engineering test package"}),
            ),
        )

        for ingredient_id in ingredient_ids:
            ingredient = ingredients[ingredient_id]
            db.execute(
                """
                INSERT INTO drug_ingredients (
                    drug_id, ingredient_id, ingredient_int_id, ingredient_name_as_listed,
                    ingredient_code_as_listed, strength_text, strength_value, strength_unit,
                    role, source, source_version, confidence
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    drug["drug_id"],
                    ingredient_id,
                    ingredient["ingredient_int_id"],
                    ingredient["canonical_name"],
                    None,
                    None,
                    None,
                    None,
                    "ACTIVE",
                    "V2_TEST_SEED",
                    "2026-05-24",
                    1.0,
                ),
            )

        for class_id in class_ids:
            db.execute(
                """
                INSERT INTO drug_class_memberships (
                    drug_id, class_id, source, source_version, evidence_quality,
                    mapping_method, review_status
                ) VALUES (?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    drug["drug_id"],
                    class_id,
                    "V2_TEST_SEED",
                    "2026-05-24",
                    "TEST_FIXTURE",
                    "PHARMACIST_REVIEW",
                    "APPROVED_FOR_V2",
                ),
            )

        compact_ingredients = sorted(ingredients[item]["ingredient_int_id"] for item in ingredient_ids)
        compact_classes = sorted(classes[item]["class_int_id"] for item in class_ids)
        db.execute(
            """
            INSERT INTO drug_compact_index (
                drug_id, ingredient_int_ids_json, class_int_ids_json
            ) VALUES (?, ?, ?);
            """,
            (drug["drug_id"], json_text(compact_ingredients), json_text(compact_classes)),
        )

        aliases = set(drug.get("aliases", []))
        aliases.add(drug["display_name"])
        aliases.add(drug["generic_name"])
        if drug.get("english_name"):
            aliases.add(drug["english_name"])
        for index, alias in enumerate(sorted(aliases, key=lambda value: (normalize(value), value))):
            db.execute(
                """
                INSERT INTO drug_aliases (
                    alias_id, drug_id, alias, normalized_alias, alias_type, language,
                    source, source_version, confidence, ambiguity_group_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    f"{drug['drug_id']}_alias_{index + 1}",
                    drug["drug_id"],
                    alias,
                    normalize(alias),
                    "DISPLAY_NAME" if alias == drug["display_name"] else "INGREDIENT",
                    "zh-Hant" if any("\u4e00" <= char <= "\u9fff" for char in alias) else "en",
                    "V2_TEST_SEED",
                    "2026-05-24",
                    1.0,
                    None,
                ),
            )


def insert_rules(
    db: sqlite3.Connection,
    seed: dict[str, Any],
    ingredients: dict[str, dict[str, Any]],
    classes: dict[str, dict[str, Any]],
    created_at: str,
) -> None:
    for rule in seed["rules"]:
        watch_for = rule.get("watch_for", [])
        patient_text = f"{rule['title']}：這是 V2 測試資料包內的鎖定規則，用於確認 App 能正確讀取 compact rules。"
        action_text = "請帶藥袋詢問藥師或醫師，請勿自行停藥、減藥或換藥。"
        db.execute(
            """
            INSERT INTO rules (
                rule_id, rule_int_id, rule_code, rule_type, severity, minimum_status,
                title, mechanism, clinical_concern, patient_plain_text, action_text,
                watch_for_json, evidence_quality, review_status, source_ids_json,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                rule["rule_id"],
                rule["rule_int_id"],
                rule["rule_code"],
                rule["rule_type"],
                rule["severity"],
                rule["severity"],
                rule["title"],
                "TEST_FIXTURE_MECHANISM",
                rule["title"],
                patient_text,
                action_text,
                json_text(watch_for),
                "TEST_FIXTURE",
                "APPROVED_FOR_V2",
                json_text(["safemed_seed_locked_regression"]),
                created_at,
                created_at,
            ),
        )
        db.execute(
            """
            INSERT INTO rule_sources (rule_id, source_id, evidence_note)
            VALUES (?, ?, ?);
            """,
            (rule["rule_id"], "safemed_seed_locked_regression", "Engineering regression seed."),
        )

        for left_id, right_id in ingredient_rule_pairs(rule):
            left_int = ingredients[left_id]["ingredient_int_id"]
            right_int = ingredients[right_id]["ingredient_int_id"]
            db.execute(
                """
                INSERT INTO ingredient_pair_rules (
                    rule_id, left_ingredient_id, right_ingredient_id, pair_key
                ) VALUES (?, ?, ?, ?);
                """,
                (rule["rule_id"], left_id, right_id, pair_key(left_int, right_int)),
            )

        for left_id, right_id in class_rule_pairs(rule):
            left_int = classes[left_id]["class_int_id"]
            right_int = classes[right_id]["class_int_id"]
            db.execute(
                """
                INSERT INTO class_pair_rules (
                    rule_id, left_class_id, right_class_id, pair_key
                ) VALUES (?, ?, ?, ?);
                """,
                (rule["rule_id"], left_id, right_id, pair_key(left_int, right_int)),
            )

        if rule["rule_type"] == "MULTI_CLASS_PATTERN":
            db.execute(
                """
                INSERT INTO multi_class_pattern_rules (
                    rule_id, required_class_ids_json, optional_context_class_ids_json,
                    min_distinct_drugs, severity
                ) VALUES (?, ?, ?, ?, ?);
                """,
                (
                    rule["rule_id"],
                    json_text(rule["required_class_ids"]),
                    json_text(rule.get("optional_context_class_ids", [])),
                    int(rule.get("min_distinct_drugs", len(rule["required_class_ids"]))),
                    rule["severity"],
                ),
            )


def ingredient_rule_pairs(rule: dict[str, Any]) -> list[tuple[str, str]]:
    if "left_ingredient_id" not in rule:
        return []
    right_ids = rule.get("right_ingredient_ids") or [rule.get("right_ingredient_id")]
    return [(rule["left_ingredient_id"], right_id) for right_id in right_ids if right_id]


def class_rule_pairs(rule: dict[str, Any]) -> list[tuple[str, str]]:
    if "left_class_id" not in rule:
        return []
    right_ids = rule.get("right_class_ids") or [rule.get("right_class_id")]
    return [(rule["left_class_id"], right_id) for right_id in right_ids if right_id]


def insert_herb_candidates(db: sqlite3.Connection, seed: dict[str, Any]) -> None:
    for herb in seed["herbs"]:
        db.execute(
            """
            INSERT INTO herbs (
                herb_id, herb_int_id, display_name, pinyin_name, normalized_name,
                synonyms_json, source_ids_json, evidence_quality, data_completeness
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                herb["herb_id"],
                herb["herb_int_id"],
                herb["display_name"],
                herb.get("pinyin_name"),
                normalize(herb["display_name"]),
                json_text(herb.get("synonyms", [])),
                json_text([
                    "mohw_herb_western_database_announcement",
                    "cmuh_dhi_info",
                    "chimei_cdi_system",
                ]),
                "SOURCE_REGISTRY_ONLY",
                "PARTIAL",
            ),
        )

    for candidate in seed["herb_western_candidate_rules"]:
        db.execute(
            """
            INSERT INTO herb_western_candidate_rules (
                candidate_id, herb_id, western_target_type, western_target_id, concern,
                mechanism, suggested_runtime_status, candidate_status, activation_gate,
                patient_plain_text_draft, action_text_draft, source_ids_json,
                evidence_quality, review_notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                candidate["candidate_id"],
                candidate["herb_id"],
                candidate["western_target_type"],
                candidate["western_target_id"],
                candidate["concern"],
                candidate["mechanism"],
                candidate["suggested_runtime_status"],
                candidate["candidate_status"],
                "DO_NOT_ACTIVATE_UNTIL_LICENSE_SOURCE_AND_PHARMACIST_REVIEW_PASS",
                "此為中西藥候選資料，尚未啟用為正式提醒。",
                "請保留中藥與西藥藥袋，詢問醫師或藥師確認；請勿自行停藥。",
                json_text([
                    "mohw_herb_western_database_announcement",
                    "cmuh_dhi_info",
                    "chimei_cdi_system",
                ]),
                "CANDIDATE_ONLY",
                "Seeded for feasibility testing only; not used by mobile runtime.",
            ),
        )


def run_quality_gates(db: sqlite3.Connection, seed: dict[str, Any]) -> None:
    failures: list[str] = []
    for drug_id, display_name, active_count in db.execute(
        "SELECT drug_id, display_name, active_ingredient_count FROM drugs;"
    ):
        ingredient_count = db.execute(
            "SELECT COUNT(*) FROM drug_ingredients WHERE drug_id = ? AND role = 'ACTIVE';",
            (drug_id,),
        ).fetchone()[0]
        class_count = db.execute(
            "SELECT COUNT(*) FROM drug_class_memberships WHERE drug_id = ?;",
            (drug_id,),
        ).fetchone()[0]
        if ingredient_count == 0:
            failures.append(f"{display_name} has no active ingredient")
        if class_count == 0:
            failures.append(f"{display_name} has no classes")
        if active_count != ingredient_count:
            failures.append(f"{display_name} active_ingredient_count mismatch")
        if active_count > 1 and ingredient_count < 2:
            failures.append(f"{display_name} combination decomposition failed")

    for rule_id, rule_code, review_status, source_ids_json in db.execute(
        "SELECT rule_id, rule_code, review_status, source_ids_json FROM rules WHERE severity IN ('RED', 'ORANGE');"
    ):
        source_ids = json.loads(source_ids_json)
        if not source_ids:
            failures.append(f"{rule_code} lacks source_ids")
        if review_status not in {"APPROVED_FOR_V2", "APPROVED_FOR_MVP_SEEDED_RULE"}:
            failures.append(f"{rule_code} review_status is not approved")
        if not db.execute("SELECT 1 FROM rule_sources WHERE rule_id = ?;", (rule_id,)).fetchone():
            failures.append(f"{rule_code} lacks rule_sources row")

    active_herb_candidates = db.execute(
        "SELECT COUNT(*) FROM herb_western_candidate_rules WHERE candidate_status = 'ACTIVE';"
    ).fetchone()[0]
    if active_herb_candidates:
        failures.append("Herb-western candidates must not be ACTIVE in the test package")

    if failures:
        raise RuntimeError("Quality gate failed:\n- " + "\n- ".join(failures))


def write_manifest(sqlite_path: Path, gzip_path: Path, seed: dict[str, Any], created_at: str) -> Path:
    sqlite_hash = sha256_file(sqlite_path)
    gzip_hash = sha256_file(gzip_path)
    manifest = {
        "schema_version": seed["package"]["schema_version"],
        "package_major_version": int(seed["package"]["package_major_version"]),
        "product_line": seed["package"]["product_line"],
        "license_tier": seed["package"]["license_tier"],
        "requires_entitlement": seed["package"]["requires_entitlement"],
        "compatible_app_major_versions": seed["package"]["compatible_app_major_versions"],
        "version": seed["package"]["data_version"],
        "created_at": created_at,
        "package_url": gzip_path.name,
        "package_format": seed["package"]["package_format"],
        "gzip_bytes": gzip_path.stat().st_size,
        "sqlite_bytes": sqlite_path.stat().st_size,
        "sha256": gzip_hash,
        "gzip_sha256": gzip_hash,
        "sqlite_sha256": sqlite_hash,
        "signature": None,
        "signature_algorithm": None,
        "signature_payload_prefix": None,
    }
    manifest_path = DIST_DIR / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return manifest_path


def build_package(keep_sqlite: bool) -> tuple[Path, Path, Path]:
    seed = json.loads(SEED_PATH.read_text())
    created_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    DIST_DIR.mkdir(parents=True, exist_ok=True)

    sqlite_path = DIST_DIR / "safemed-mobile-safety-v2-test.sqlite3"
    gzip_path = DIST_DIR / "safemed-mobile-safety-v2-test.sqlite3.gz"
    for path in (sqlite_path, gzip_path, DIST_DIR / "manifest.json"):
        path.unlink(missing_ok=True)

    db = sqlite3.connect(sqlite_path)
    try:
        db.executescript(SCHEMA_PATH.read_text())
        insert_package_manifest(db, seed, created_at)
        insert_sources(db, seed, created_at)
        ingredients = insert_ingredients(db, seed)
        classes = insert_classes(db, seed)
        insert_drugs(db, seed, ingredients, classes)
        insert_rules(db, seed, ingredients, classes, created_at)
        insert_herb_candidates(db, seed)
        run_quality_gates(db, seed)
        db.execute("PRAGMA user_version = 2;")
        db.execute("PRAGMA application_id = 0x534D5632;")
        db.commit()
        integrity = db.execute("PRAGMA integrity_check;").fetchone()[0]
        if str(integrity).lower() != "ok":
            raise RuntimeError(f"SQLite integrity_check failed: {integrity}")
    finally:
        db.close()

    with sqlite_path.open("rb") as source, gzip_path.open("wb") as raw_target:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_target, compresslevel=9, mtime=0) as target:
            shutil.copyfileobj(source, target)
    manifest_path = write_manifest(sqlite_path, gzip_path, seed, created_at)
    if not keep_sqlite:
        sqlite_path.unlink()
    return sqlite_path, gzip_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the SafeMed V2 test mobile data package.")
    parser.add_argument("--keep-sqlite", action="store_true", help="Keep the uncompressed sqlite file in dist/.")
    args = parser.parse_args()

    sqlite_path, gzip_path, manifest_path = build_package(keep_sqlite=args.keep_sqlite)
    print(f"Built {gzip_path}")
    if sqlite_path.exists():
        print(f"Kept {sqlite_path}")
    print(f"Wrote {manifest_path}")


if __name__ == "__main__":
    main()
