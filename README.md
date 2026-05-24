# SafeMed Box V2 Data Packages

這個 repository 是 SafeMed Box V2.x 專業 / 商業版資料包發布通道。

V2.x 與 V1.x 完全區隔：

- V1.x 免費 / 公益線資料包：`ctshieh/ai-pharmacist-taiwan-data`
- V2.x 專業 / 商業線資料包：`ctshieh/ai-pharmacist-taiwan-data-v2`

V2.x App 預設讀取：

```text
https://github.com/ctshieh/ai-pharmacist-taiwan-data-v2/releases/latest/download/manifest.json
```

資料包 manifest 必須標示：

```text
schema_version: safemed-mobile-safety-v2
package_major_version: 2
product_line: safemed_pro
compatible_app_major_versions: [2]
```

本 repo 只發布公開藥品安全資料包與來源聲明，不應包含任何使用者資料、病人資料、處方照片、OCR 原文或 PHI。

## 目前內容

這一版先建立可供 iOS V2 rule engine 測試的最小資料包：

- V2 SQLite schema：`schemas/safemed_mobile_safety_v2.sql`
- 測試種子資料：`seed/test_seed_v2.json`
- 可重現 builder：`scripts/build_test_package.py`
- 產物：`dist/manifest.json` 與 `dist/safemed-mobile-safety-v2-test.sqlite3.gz`

測試資料已涵蓋：

- Warfarin 重複成分
- Warfarin therapeutic duplicate rule row
- Warfarin + NSAID
- Digoxin / Lanoxin / 隆我心 + Amiodarone / Cordarone / 臟得樂
- Anticoagulant + antiplatelet
- Opioid + sedative
- Methotrexate + TMP-SMX
- Statin + strong CYP3A4 inhibitor
- Lithium + ACEI/ARB
- Dual RAS blockade
- NSAID + ACEI/ARB + diuretic
- QT-risk combination
- Green negative control 所需的 Metformin、Acetaminophen

## 中西藥資料狀態

本 repo 已加入中西藥資料的 V2 結構與候選 seed：

- `herbs`
- `herb_western_candidate_rules`
- `source_registry`

目前中西藥候選資料只用於可行性與資料結構測試，不會啟用為正式 RED / ORANGE 規則。所有候選列的 `candidate_status` 都必須保持非 `ACTIVE`，且 `activation_gate` 必須要求授權、來源、藥師審查通過後才能啟用。

這個限制是刻意的：中西藥資料通常牽涉資料庫授權、單筆內容再散布權限、證據品質分層與患者端文案審查。在審查完成前，App 端應維持保守 fallback，最多作為 BLUE / 資料不足或未啟用候選。

目前登錄的公開來源入口：

- 衛生福利部中西藥併用諮詢資料庫公開說明
- 衛生福利部中醫藥司臺灣中藥典及中西藥併用查詢系統入口
- 衛生福利部健保醫療雲端查詢系統中西藥交互作用提示公開說明
- 中西藥交互作用資訊網
- 奇美藥劑部中西藥交互作用查詢系統

## 建置測試資料包

```bash
python3 scripts/build_test_package.py --keep-sqlite
```

輸出：

```text
dist/manifest.json
dist/safemed-mobile-safety-v2-test.sqlite3
dist/safemed-mobile-safety-v2-test.sqlite3.gz
```

## 驗證測試資料包

```bash
python3 scripts/validate_test_package.py
```

Validator 會檢查：

- manifest schema、major version、package format、checksum
- SQLite integrity
- drug ingredient、class membership、compact index 是否缺漏
- RED / ORANGE rule 是否有來源
- therapeutic duplicate rule 是否存在
- TMP-SMX 是否展開成 Trimethoprim + Sulfamethoxazole
- 衛福部中西藥來源入口是否存在
- 中西藥候選是否維持非 ACTIVE
- locked regression cases 是否得到預期顏色與 rule hit

`dist/` 不進 git。正式測試時，請把 `manifest.json` 與 gzip SQLite 上傳到 GitHub Release，讓 iOS 透過 releases/latest URL 下載。

## Builder 品質檢查

Builder 會拒絕產生不合格資料包：

- drug 沒有 active ingredient
- drug 沒有 class membership
- active_ingredient_count 與 `drug_ingredients` 不一致
- 複方藥沒有展開為多個 active ingredients
- RED / ORANGE rule 沒有 source ids
- RED / ORANGE rule 沒有 `rule_sources`
- 中西藥候選資料被設成 `ACTIVE`
- SQLite `PRAGMA integrity_check` 失敗

## 發布測試 Release

V2 iOS 預設 manifest URL 使用 GitHub `releases/latest`。若要讓 App 直接抓測試資料包，測試 release 需要是 latest 可見的 release。

```bash
gh release create v2-test-20260524.3 \
  dist/manifest.json \
  dist/safemed-mobile-safety-v2-test.sqlite3.gz \
  --title "SafeMed V2 test data package v2-test-20260524.3" \
  --notes "V2 test package for locked safety regression and iOS package integration."
```
