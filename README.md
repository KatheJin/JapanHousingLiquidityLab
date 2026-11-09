# JapanHousingLiquidityLab

Housing Historical Comparison & Alternative Discovery — 過去の取引、現在の類似掲載、価格水準の近い地域を比較する住宅研究プロジェクト。 | Research on historical transactions, comparable current listings and alternative areas at similar price levels.

## 日本語

### 一度の住宅入力で三つの比較

1. **歴史的な類似成約**：実取引の件数・明細・原価格を確認する。
2. **同じ地域の現在掲載**：明示操作でSUUMOの限定検索を行い、厳格一致と近似候補を分ける。
3. **価格水準の近い地域**：Hedonic Pricing Modelで同じ住宅属性を比較し、研究候補のモデル一致・不一致・標本不足を表示する。候補を選ぶと元の住宅情報を再入力せずに当地掲載を検索できる。

**正式な地域価格順位・歴史調整価格は利用不可。** モデルの一致も市場価格の同等性を保証しない。実成約の分布とモデル診断を別表示し、初回分析ではネット収集しない。現在のMVPはローカル私的利用の試験版で、公開サービスではない。[最終MVP機能確認・残課題](docs/mvp-final-review.md)。

[Phase 4限定SUUMO検索・Phase 5境界](docs/phase4-demand-and-phase5-contract.md)：共有住宅入力から既定10一覧・最大12詳細（設定上限20/30）を確認。許可された一覧カードで予備選別し、厳格一致・近似候補・旧観測を分離。[実検索検証](docs/phase4-search-validation.md)。Phase 4は最終確認・Push済み（`e984566`）。[最終確認](docs/phase4-final-review.md)。

[Phase 3 歴史成約分析](docs/phase3-history.md)：実データの件数・展開明細・原単価。正式調整はunavailable。ローカル実データが既定、合成Demoは開発者の明示設定のみ。

### 新版MVPとHedonic Pricing Model

新版の中心は **Hedonic Pricing Model（住宅属性を考慮した価格モデル）**。歴史的な相対価格水準、現在の類似掲載のオンデマンド検索、価格水準の近い地域の発見を支援する。7日／30日消失予測と長期収集は独立研究として保持し、新版MVPの必須条件にはしない。

[Phase 1・2監査と実験](docs/hedonic-phase1-2.md)で既存Ridge／HGBと実データを再利用し、属性・市場時間・建物老化を分けて診断する。正式な歴史時間調整は利用不可を維持。

[Phase 5・統合住宅比較](docs/phase5-area-comparison.md)をローカル実装：一度の住宅入力から歴史成約明細、同地域の限定SUUMO検索、統一属性での研究用地域候補へ進む。候補地域を選んで検索ボタンを押すまでネット取得しない。地区間価格差・順位は未検証で、正式な推薦や現在の査定は提供しない。本版をローカル研究型MVPの安定チェックポイントとする。旧ページ・研究結果は保持する。

[Task 012公開前確認](docs/task012-release-review.md)：最終186テスト成功。稼働中collectorを保持し、公開対象と私有データを分離。

[PostgreSQL移行・HOME'S再調査](docs/postgres-homes.md)：実移行・増分・復元検証済み。Web管理UIは今後。
[最終監査・コミット対象一覧](docs/postgres-final-review.md)：移行監査時点は実SUUMO 33 ID、成功観測35件。現在の件数は継続収集のstatusで確認します。元SQLiteの31 IDは移行前の凍結記録です。
[HOME'S 403詳細調査](docs/homes-http-investigation.md)：CloudFront拒否を確認、実取得0件。検索表示は入庫しません。
[東京都の継続収集](docs/tokyo-listing-expansion.md)：既存PGを保持し、狛江を再開後23区を順次収集。3,000成功出所IDを目標に、実際の進捗を報告します。

Task 012 Extension: [実掲載SQLiteパイプライン](docs/task012-real-pipeline.md)。実SUUMO31掲載ID、ローカル私的利用のみ。出所別制限あり。

Task 012: [HTTP収集・掲載追跡](docs/task012.md)。公式XIT001は[01／02実接続検証](docs/mlit-live-verification.md)済み。

Task 011: [住まいの判断ノート](docs/task011.md)。Streamlitローカル原型・合成デモ。実分析は管理者の明示設定が必要です。


Task 010: [掲載観測・複数媒体追跡](docs/task010.md)。許可されたローカル入力と合成例。非観測は成約日ではありません。

Task 009: [地域・駅アクセスと住宅価格](docs/task009.md)。歴史予算比較CLI。鉄道通勤は未検証、現在の割安順位ではありません。

Task 008: [歴史データ拡張・時間検証](docs/task008.md)。2018Q1～2026Q2、140,888件。探索的検証であり、旧モデルは置換しません。 [最終監査](docs/task008-final-review.md)。

Task 007: [REINS市場活動・季節性・価格帯](docs/task007.md)。2023年1月～2026年9月、MLITとは独立した市場背景。

Task 006: [歴史的購入機会の記述分析](docs/task006.md)。将来確率ではありません。

Task 005: [時差を明示する価格競争力参考](docs/task005.md)。

Task 004: [価格基準モデル・時間検証](docs/task004.md)。

Task 003: 2023Q1〜2026Q2の14四半期、55,652件を取得。[履歴分析](docs/task003.md)。

Task 002: [取引価格CSVの探索分析](docs/task002.md)。2023Q1の実CSVを取得・検証済み。範囲は最新公開四半期まで。[更新状況](docs/task002-update.md)。

開発初期の個人研究プロジェクトです。現時点では、実市場の予測サービスではありません。
NII データは必須ではなく、ネットワーク接続なしで合成データによる基準モデルを実行できます。

### API資格情報とAI補助開発

APIキーは会話へ貼り付けず、環境変数 `JHLL_REINFOLIB_API_KEY` またはrootのGit無視ファイル `.env.mlit-local` から実行時に読みます。環境変数を優先し、ファイルを使う場合はGit無視・未追跡をコードでも確認します。値はHTTPS認証headerにだけ渡し、URL・request log・結果報告・Gitには保存しません。私有ファイルの値を子process用環境へ自動exportしません。

この経路でXIT001の01／02が実際にHTTP 200となり、生成物と公開候補へのキー非混入を検査しました。これはAI補助開発で会話への転記とGit混入を避ける実装であり、平文ローカル設定の暗号化や実行processからの秘密隔離を保証するものではありません。[検証範囲・結果](docs/mlit-live-verification.md)。

### APIと既存CSVのフィールド差

千代田区2023Q1の実API応答（01／02）は同じ29フィールドでした。既存CSVの21列（CP932、日本語列名）と異なり、APIはUTF-8 JSONで `TradePrice`、`Area`、`BuildingYear`、`Period`、`PriceCategory` 等を返します。既存CSVの `最寄駅：名称`・`最寄駅：距離（分）` に相当する駅フィールドは、このAPI応答にはありません。01は不動産取引価格情報、02は成約価格情報で、どちらも現在の売出価格ではありません。欠損や分類を維持し、自動結合・駅情報の推定補完・既存訓練データへの投入は行いません。取得日時は取引四半期・実際の公表日と別です。詳細と比較範囲は[実接続報告](docs/mlit-live-verification.md)を参照してください。

### 最初の実行（Windows PowerShell / Python 3.12）

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ".[reins,public-listings,postgres]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab demo
```

すでに `.venv` がある場合、作成コマンドは不要です。合成データ入門には追加パッケージや環境の有効化は不要です。REINS解析には `pip install -e ".[reins]"` を使用します。
PyCharm のプロジェクトインタープリターには `.venv\Scripts\python.exe` を指定してください。
再実行時は `demo --output reports/run-002` のように新しい出力先を指定します。既存の結果は上書きしません。

### 現在できること

- 再現可能な合成データ、右打ち切りを扱う Kaplan–Meier 基準モデル、7日・30日の集団リスク出力。
- ローカル CSV の文字コード（UTF-8 / CP932）、列名、欠損数、行数、不正な列数、SHA-256 の検査。
- 合成データ入門は標準ライブラリで実行できます。価格参考モデルはTask 004～006を参照。因果推論は未実装です。

```powershell
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab inspect-mlit data/raw/your_mlit.csv
```

CSV は利用者が利用権限を確認して配置します。このinspect-mlitコマンドはネットワーク取得を行いません。実掲載収集はTask 012の別コマンド・アクセス制限に従います。
MLIT の取引価格データだけから掲載期間や下架イベントを推定しません。掲載終了は成約と同義ではありません。

Docker は初期段階では不要です。PostgreSQL、FastAPI、定期同期、デプロイを導入する段階で検討します。

構成: `japan_housing_liquidity_lab/`（実装）、`tests/`（テスト）、`docs/`（研究設計）、
`data/raw/`（ローカル入力）、`reports/`（生成結果）。データと生成結果は Git の対象外です。

詳細: [研究計画](docs/research-plan.md) · [データ取扱い](docs/data-guide.md)

## English

### Three comparisons from one property input

1. **Similar historical transactions**: inspect real counts, records and original prices.
2. **Current listings in the same area**: explicitly start bounded SUUMO search, keeping strict and approximate results separate.
3. **Areas at similar price levels**: use the Hedonic Pricing Model with identical property attributes; distinguish descriptive model agreement, disagreement and sparse samples. Search a chosen area's listings without re-entering the property.

**Formal regional rankings and historical adjusted prices remain unavailable.** Agreement does not establish equivalent market prices. Raw transaction distributions and model diagnostics are separate; initial analysis does not crawl the web. This is a local private-use MVP, not a deployed public service. [Final MVP acceptance and remaining work](docs/mvp-final-review.md).

[Phase 4 bounded SUUMO search / Phase 5 contract](docs/phase4-demand-and-phase5-contract.md): shared property input, default 10 lists/12 details (caps 20/30), permitted list-card screening, separate strict/approximate/old observations. [Live search validation](docs/phase4-search-validation.md). Phase 4 passed final review and was pushed (`e984566`). [Final review](docs/phase4-final-review.md).

[Phase 3 historical transactions](docs/phase3-history.md): real counts, expandable records and raw unit prices. Formal adjustments remain unavailable. Real data is the default; synthetic demo requires developer opt-in.

### New MVP and Hedonic Pricing Model

The core method is a **Hedonic Pricing Model**, comparing housing prices while accounting for observed attributes. The product direction is historical relative-price comparison, on-demand comparable listings and discovery of areas at similar price levels. Seven/thirty-day disappearance prediction and long-running collection remain separate research, outside required MVP scope.

[Phase 1/2 audit and experiments](docs/hedonic-phase1-2.md) reuse existing Ridge/HGB and verified data, separating attributes, market time and physical aging. Formal historical time adjustment remains unavailable.

[Phase 5 unified housing comparison](docs/phase5-area-comparison.md) is implemented locally: one property input connects historical records, bounded same-area SUUMO search and standardized research-only area candidates. Network collection starts only after an explicit search click, including a selected candidate. Cross-market contrasts and rankings remain unvalidated; no formal recommendation or current appraisal is supplied. This version is the stable checkpoint for the local research MVP. Existing pages and studies are retained.

[Task 012 release review](docs/task012-release-review.md): final 186-test suite passed; active collection preserved and private data excluded.

[PostgreSQL migration and HOME'S review](docs/postgres-homes.md): actual migration, incremental writes and restore verified; admin Web UI remains future work.
[Final audit and commit manifest](docs/postgres-final-review.md): the migration-audit checkpoint had 33 real SUUMO IDs and 35 successful observations; use the continuous collector status for current counts. The original 31-ID SQLite file is the frozen pre-migration record.
[HOME'S 403 investigation](docs/homes-http-investigation.md): CloudFront rejection confirmed, zero acquisitions; search-service text was not imported.
[Tokyo continuous collection](docs/tokyo-listing-expansion.md): retain existing PG history, resume Komae and traverse 23 wards; report actual progress toward 3,000 successful source IDs.

Task 012 Extension: [Real listing SQLite pipeline](docs/task012-real-pipeline.md). 31 real SUUMO IDs; local/private use with source-specific restrictions.

Task 012: [Network collection and tracking](docs/task012.md). Official XIT001 [01/02 live connections verified](docs/mlit-live-verification.md).

Task 011: [Housing Decision Assistant](docs/task011.md). Local Streamlit prototype with synthetic demo; real analysis requires explicit operator setup.


Task 010: [Listing observation and multi-source tracking](docs/task010.md). Authorized local input and synthetic examples; disappearance is not a sale date.

Task 009: [Location, station access and housing prices](docs/task009.md). Historical budget comparison CLI; railway commutes remain unverified, with no current-value ranking.

Task 008: [Historical expansion and temporal validation](docs/task008.md). 140,888 retained records, 2018Q1–2026Q2; exploratory experiments, existing models preserved. [Final review](docs/task008-final-review.md).

Task 007: [REINS activity, seasonality and price bands](docs/task007.md), January 2023–September 2026, independent of MLIT records.

Task 006: [Historical opportunity descriptions](docs/task006.md), not future probabilities.

Task 005: [Lag-aware price competitiveness reference](docs/task005.md).

Task 004: [Price benchmark and temporal evaluation](docs/task004.md).

Task 003: 14 quarters, 2023Q1–2026Q2, with 55,652 transactions acquired. [Historical analysis](docs/task003.md).

Task 002: [Transaction CSV EDA](docs/task002.md). Real 2023Q1 CSV acquired and validated. Scope extends to the latest published quarter. [Update](docs/task002-update.md).

An early-stage independent research project, not a live market prediction service.
NII is optional. The synthetic baseline runs offline with Python 3.12 and no third-party dependencies.

### API credentials in AI-assisted development

Supply API credentials through `JHLL_REINFOLIB_API_KEY` or the Git-ignored root `.env.mlit-local` file, rather than pasting keys into conversations. Environment configuration takes priority; private-file loading also verifies that the file is ignored and untracked. Credentials are sent only in the HTTPS authentication header, never in URLs, request logs, result reports or Git. File credentials are not automatically exported into child-process environments.

This path actually produced HTTP 200 for XIT001 classifications 01 and 02; generated files and public candidates were checked for key leakage. These controls avoid conversational transcription and Git inclusion; they do not encrypt the local file or isolate the credential from the executing process. See [verification scope and results](docs/mlit-live-verification.md).

### API versus existing CSV fields

The live Chiyoda 2023Q1 responses for 01/02 share 29 fields. Unlike the existing 21-column CP932 CSVs with Japanese headers, the API returns UTF-8 JSON with fields such as `TradePrice`, `Area`, `BuildingYear`, `Period` and `PriceCategory`. These responses have no equivalent of CSV `最寄駅：名称` or `最寄駅：距離（分）`. Classification 01 is transaction-price information and 02 is contract-price information; neither is a current asking price. Missing values and source classifications are preserved; there is no automatic merge, imputed station data or insertion into existing training sets. Retrieval time is separate from the transaction quarter and actual publication date. See the [live report](docs/mlit-live-verification.md) for scope and quality details.

### Quick start (Windows PowerShell)

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install -e ".[reins,public-listings,postgres]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab demo
```

Skip environment creation if `.venv` already exists. The synthetic starter needs no activation or extra packages. REINS analysis requires `pip install -e ".[reins]"`.
Select `.venv\Scripts\python.exe` as the project interpreter in PyCharm.
For subsequent runs, use a fresh directory, such as `demo --output reports/run-002`; existing results are never overwritten.

### Available now

- Seeded synthetic data, a right-censored Kaplan–Meier baseline, and population risks at 7 and 30 days.
- Local CSV inspection: UTF-8 / CP932, headers, missing counts, row counts, malformed widths, and SHA-256.
- The synthetic starter uses the standard library. Price-reference models are documented in Tasks 004–006; causal inference is not implemented.

```powershell
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab inspect-mlit data/raw/your_mlit.csv
```

Supply a local CSV only after checking your permission to use it. This inspect-mlit command performs no network acquisition. Live listing collection uses the separate Task 012 commands and access restrictions.
Transaction-price records alone are not listing-duration or delisting labels. Delisting does not imply a completed sale.

Docker is unnecessary initially. Consider it later for PostgreSQL, FastAPI, scheduled synchronization, or deployment.

Layout: `japan_housing_liquidity_lab/` (code), `tests/`, `docs/`, `data/raw/` (local inputs), and `reports/` (generated outputs).
Data and generated results are ignored by Git.

Details: [Research plan](docs/research-plan.md) · [Data guide](docs/data-guide.md)
