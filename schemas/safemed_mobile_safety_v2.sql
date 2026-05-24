PRAGMA foreign_keys = ON;

CREATE TABLE package_manifest (
    package_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    package_major_version TEXT NOT NULL,
    product_line TEXT NOT NULL,
    license_tier TEXT NOT NULL,
    requires_entitlement INTEGER NOT NULL,
    compatible_app_major_versions TEXT NOT NULL,
    data_version TEXT NOT NULL,
    rules_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    package_format TEXT NOT NULL,
    source_snapshots TEXT NOT NULL DEFAULT '[]',
    quality_gate_result TEXT NOT NULL,
    locked_regression_result TEXT NOT NULL
);

CREATE TABLE ingredients (
    ingredient_id TEXT PRIMARY KEY,
    ingredient_int_id INTEGER NOT NULL UNIQUE,
    canonical_name TEXT NOT NULL,
    normalized_name TEXT NOT NULL,
    rxnorm_ingredient_rxcui TEXT,
    atc_seed_codes_json TEXT NOT NULL DEFAULT '[]',
    synonyms_json TEXT NOT NULL DEFAULT '[]',
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    evidence_quality TEXT NOT NULL
);

CREATE TABLE drugs (
    drug_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    generic_name TEXT NOT NULL,
    chinese_name TEXT,
    english_name TEXT,
    nhi_code TEXT,
    tfda_license_no TEXT,
    rxnorm_rxcui TEXT,
    atc_codes_json TEXT NOT NULL DEFAULT '[]',
    ahfs_codes_json TEXT NOT NULL DEFAULT '[]',
    dosage_form TEXT,
    route TEXT,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    evidence_quality TEXT NOT NULL,
    data_completeness TEXT NOT NULL,
    is_combination INTEGER NOT NULL,
    active_ingredient_count INTEGER NOT NULL,
    safety_classes_json TEXT NOT NULL DEFAULT '[]',
    therapeutic_classes_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE drug_ingredients (
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    ingredient_int_id INTEGER NOT NULL,
    ingredient_name_as_listed TEXT NOT NULL,
    ingredient_code_as_listed TEXT,
    strength_text TEXT,
    strength_value REAL,
    strength_unit TEXT,
    role TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    confidence REAL NOT NULL,
    PRIMARY KEY (drug_id, ingredient_id)
);

CREATE TABLE drug_aliases (
    alias_id TEXT PRIMARY KEY,
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_type TEXT NOT NULL,
    language TEXT NOT NULL,
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    confidence REAL NOT NULL,
    ambiguity_group_id TEXT
);

CREATE TABLE normalization_conflicts (
    conflict_id TEXT PRIMARY KEY,
    normalized_alias TEXT NOT NULL,
    drug_ids_json TEXT NOT NULL,
    ingredient_signatures_json TEXT NOT NULL,
    resolution_status TEXT NOT NULL,
    recommended_user_action TEXT NOT NULL
);

CREATE TABLE classes (
    class_id TEXT PRIMARY KEY,
    class_int_id INTEGER NOT NULL UNIQUE,
    class_name TEXT NOT NULL,
    class_type TEXT NOT NULL,
    parent_class_id TEXT,
    description TEXT NOT NULL
);

CREATE TABLE drug_class_memberships (
    drug_id TEXT NOT NULL REFERENCES drugs(drug_id),
    class_id TEXT NOT NULL REFERENCES classes(class_id),
    source TEXT NOT NULL,
    source_version TEXT NOT NULL,
    evidence_quality TEXT NOT NULL,
    mapping_method TEXT NOT NULL,
    review_status TEXT NOT NULL,
    PRIMARY KEY (drug_id, class_id)
);

CREATE TABLE drug_compact_index (
    drug_id TEXT PRIMARY KEY REFERENCES drugs(drug_id),
    ingredient_int_ids_json TEXT NOT NULL,
    class_int_ids_json TEXT NOT NULL
);

CREATE TABLE rules (
    rule_id TEXT PRIMARY KEY,
    rule_int_id INTEGER NOT NULL UNIQUE,
    rule_code TEXT NOT NULL UNIQUE,
    rule_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    minimum_status TEXT NOT NULL,
    title TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    clinical_concern TEXT NOT NULL,
    patient_plain_text TEXT NOT NULL,
    action_text TEXT NOT NULL,
    watch_for_json TEXT NOT NULL DEFAULT '[]',
    evidence_quality TEXT NOT NULL,
    review_status TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE ingredient_pair_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    left_ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    right_ingredient_id TEXT NOT NULL REFERENCES ingredients(ingredient_id),
    pair_key TEXT NOT NULL,
    PRIMARY KEY (rule_id, pair_key)
);

CREATE TABLE class_pair_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    left_class_id TEXT NOT NULL REFERENCES classes(class_id),
    right_class_id TEXT NOT NULL REFERENCES classes(class_id),
    pair_key TEXT NOT NULL,
    PRIMARY KEY (rule_id, pair_key)
);

CREATE TABLE therapeutic_duplicate_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    duplicate_group_class_id TEXT NOT NULL REFERENCES classes(class_id),
    severity_if_same_ingredient TEXT NOT NULL,
    severity_if_same_class TEXT NOT NULL,
    PRIMARY KEY (rule_id, duplicate_group_class_id)
);

CREATE TABLE multi_class_pattern_rules (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    required_class_ids_json TEXT NOT NULL,
    optional_context_class_ids_json TEXT NOT NULL DEFAULT '[]',
    min_distinct_drugs INTEGER NOT NULL,
    severity TEXT NOT NULL,
    PRIMARY KEY (rule_id)
);

CREATE TABLE source_registry (
    source_id TEXT PRIMARY KEY,
    source_name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    version_label TEXT NOT NULL,
    license_note TEXT NOT NULL,
    source_type TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    checksum TEXT
);

CREATE TABLE rule_sources (
    rule_id TEXT NOT NULL REFERENCES rules(rule_id),
    source_id TEXT NOT NULL REFERENCES source_registry(source_id),
    evidence_note TEXT NOT NULL,
    PRIMARY KEY (rule_id, source_id)
);

CREATE TABLE herbs (
    herb_id TEXT PRIMARY KEY,
    herb_int_id INTEGER NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    pinyin_name TEXT,
    normalized_name TEXT NOT NULL,
    synonyms_json TEXT NOT NULL DEFAULT '[]',
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_quality TEXT NOT NULL,
    data_completeness TEXT NOT NULL
);

CREATE TABLE herb_western_candidate_rules (
    candidate_id TEXT PRIMARY KEY,
    herb_id TEXT NOT NULL REFERENCES herbs(herb_id),
    western_target_type TEXT NOT NULL,
    western_target_id TEXT NOT NULL,
    concern TEXT NOT NULL,
    mechanism TEXT NOT NULL,
    suggested_runtime_status TEXT NOT NULL,
    candidate_status TEXT NOT NULL,
    activation_gate TEXT NOT NULL,
    patient_plain_text_draft TEXT NOT NULL,
    action_text_draft TEXT NOT NULL,
    source_ids_json TEXT NOT NULL DEFAULT '[]',
    evidence_quality TEXT NOT NULL,
    review_notes TEXT NOT NULL
);

CREATE INDEX idx_drug_aliases_normalized ON drug_aliases(normalized_alias);
CREATE INDEX idx_drug_ingredients_drug ON drug_ingredients(drug_id);
CREATE INDEX idx_drug_class_memberships_drug ON drug_class_memberships(drug_id);
CREATE INDEX idx_ingredient_pair_rules_pair ON ingredient_pair_rules(pair_key);
CREATE INDEX idx_class_pair_rules_pair ON class_pair_rules(pair_key);
