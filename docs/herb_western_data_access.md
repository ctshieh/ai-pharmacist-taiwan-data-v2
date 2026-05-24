# 中西藥資料授權與 API 評估

狀態日期：2026-05-25

本文件記錄 SafeMed Box V2 對中西藥交互作用資料的資料源、授權與 API 可行性判斷。結論先行：目前可找到官方公開查詢入口與健保雲端主動提示 API 說明，但尚未找到可直接供消費型 App 商業離線資料包使用的完整公開資料集或公開 API。因此，中西藥列目前只能保留在 `herb_western_candidate_rules`，不得升級為正式 `ACTIVE` 規則。

## 目前判斷

- 可保留中西藥候選資料，用於 schema、資料品質檢查、藥師審查流程與未來授權接軌。
- 不可把候選列當成 runtime safety rule 使用。
- 不可把候選列設為 `candidate_status = ACTIVE`。
- 不可用未授權的查詢結果爬取或重建完整商業離線資料包。
- 若 App 對中西藥資料不足，應顯示 BLUE 或資料不足狀態，不得顯示 GREEN。

## 已確認的官方公開資訊

### 衛福部中西藥併用諮詢資料庫

衛福部公開說明提到已建置中西藥併用諮詢資料庫，並列出資料量級：中西藥併用研究資料 3085 筆、中西藥併用配對 556 筆、中醫典籍配伍禁忌 475 筆。

來源：

- https://www.mohw.gov.tw/cp-2704-43040-1.html

工程判斷：

- 這代表官方確有結構化資料庫與配對資料。
- 但該頁是新聞/說明頁，不等於授權完整 row-level dataset 可被商業 App 下載、改作、快取或離線再散布。

### 臺灣中藥典及中西藥併用查詢系統

中醫藥司公開頁面說明，臺灣中藥典暨圖鑑查詢系統與中西藥併用諮詢資料庫資料已整合於「臺灣中藥典及中西藥併用查詢系統」。

來源：

- https://dep.mohw.gov.tw/DOCMAP/cp-759-54182-108.html
- https://www.cmthp.mohw.gov.tw/

工程判斷：

- 這是可作為人工查證與正式授權洽詢的官方入口。
- 目前未確認其提供完整公開 API、批次匯出、商業離線資料包授權，或 App 端可重散布授權。

### 衛福部網站資料開放宣告

衛福部全球資訊網有政府網站資料開放宣告，網站刊載資料與素材採政府資料開放授權條款第 1 版，使用時應註明出處；宣告也明確提醒，其範圍僅及於著作權保護範圍，部分資料或其他權利事項可能不在宣告範圍內。

來源：

- https://www.mohw.gov.tw/cp-81-155-1.html

工程判斷：

- 可以引用公開網頁作為來源與人工審查依據。
- 不應直接推論「後端查詢系統的完整互動資料表」也可被商業 App 離線再散布。

### 健保醫療資訊雲端查詢系統與主動提示 API

健保署公開頁面說明，健保醫療資訊雲端查詢系統提供特約醫事服務機構與醫事人員於臨床診療、調劑或用藥諮詢使用；公開頁面也說明自 107 年起提供電腦主動提示功能 API，並包含西西藥與中西藥交互作用等提示功能。

來源：

- https://www.nhi.gov.tw/ch/cp-7623-96531-2727-1.html
- https://www.nhi.gov.tw/ch/cp-5662-509c0-2724-1.html
- https://www.nhi.gov.tw/ch/cp-5661-9ca08-2723-1.html

工程判斷：

- 健保雲端主動提示 API 可能是醫療院所/HIS 場景的 API，不等同於開放給一般消費型 App 使用。
- 該系統涉及病人用藥紀錄、醫事人員查詢資格、院所流程與個資保護；不適合作為 V2 consumer app 的直接資料來源，除非取得明確資格、契約與技術文件。

## 正式啟用前必須取得的確認

向衛福部中醫藥司、健保署或指定窗口確認以下事項後，才可將中西藥資料納入正式規則：

- 是否提供完整中西藥交互作用資料集、資料字典、版本紀錄與更新頻率。
- 是否允許商業 App 使用、改作、快取、離線封裝與再散布。
- 是否允許 iOS/Android 共用 mobile data package 發布，並透過 GitHub Release 或其他 CDN 傳遞。
- 是否要求特定署名格式、來源顯示、免責聲明或使用限制。
- 是否有公開 API、授權 API、批次下載或合作介接方式。
- 若使用健保雲端 API，是否限特約醫事服務機構、醫事人員卡、健保卡/SAM 卡或 HIS 系統。
- 是否能取得 severity、mechanism、evidence level、clinical recommendation 等欄位，或只能取得提示文字。
- 是否允許將官方內容轉換為 SafeMed RED/ORANGE/BLUE/GREEN 規則。

## 洽詢信重點

可用以下問題作為正式函詢或 email 草稿的骨架：

```text
主旨：詢問中西藥交互作用資料授權、API 與行動 App 離線資料包使用可行性

您好：

我們正在開發 SafeMed Box / 安心藥盒 V2，用於民眾整理藥品資訊與提示可能用藥疑慮。App 採本機離線優先設計，會以版本化資料包提供藥品成分、分類與交互作用規則，並保守提醒使用者諮詢醫師或藥師，不會建議自行停藥、減藥或換藥。

想請教：

1. 中西藥交互作用資料是否有完整資料集、資料字典、版本紀錄或更新機制可申請？
2. 是否允許商業行動 App 將資料轉換後封裝於 iOS/Android 離線資料包？
3. 是否允許重新散布、快取、改作與衍生規則分類，例如轉換為 RED/ORANGE/BLUE/GREEN 風險等級？
4. 是否有正式 API、批次下載、授權契約或合作介接流程？
5. 若使用健保醫療資訊雲端查詢系統主動提示 API，申請資格是否限特約醫事服務機構或 HIS 廠商？一般消費型 App 是否可申請？
6. 若可使用，署名、免責聲明、患者端文案、資料更新頻率與審查流程有何要求？

敬請提供可洽詢窗口、申請表單或技術文件。
```

## V2 工程閘門

在取得授權與專業審查前，資料包與 App 必須維持以下閘門：

- Builder 拒絕 `herb_western_candidate_rules.candidate_status = ACTIVE`。
- Validator 拒絕 `herb_western_candidate_rules.candidate_status = ACTIVE`。
- iOS package validation 拒絕 `herb_western_candidate_rules.candidate_status = ACTIVE`。
- Android parity 實作時也必須加入同等檢查。
- 中西藥候選資料不得影響 RED/ORANGE/GREEN 判斷。
- 若未來啟用正式規則，應新增正式 rule table 或明確 promotion migration，不應直接讓 candidate table 成為 runtime rule source。

## 建議下一步

1. 送出正式函詢，取得授權/API/技術文件回覆。
2. 在 `source_registry` 補上正式授權文件或回覆紀錄的 source id。
3. 設計 `herb_western_pair_rules` 或等價正式規則表。
4. 加入 Android/iOS 共用 locked regressions。
5. 由藥師審查患者端文案，確認不含自行停藥、減藥、換藥建議。
