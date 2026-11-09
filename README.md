# JapanHousingLiquidityLab

日本の住宅市場における価格動向・掲載期間・掲載終了リスクを分析し、データに基づく住宅購入の意思決定支援を目指す研究プロジェクト。 | A data-driven research project analyzing housing prices, listing duration, and delisting risk in Japan.

## 日本語

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
