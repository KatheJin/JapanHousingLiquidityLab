# JapanHousingLiquidityLab

日本の住宅市場における価格動向・掲載期間・掲載終了リスクを分析し、データに基づく住宅購入の意思決定支援を目指す研究プロジェクト。 | A data-driven research project analyzing housing prices, listing duration, and delisting risk in Japan.

## 日本語

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

### 最初の実行（Windows PowerShell / Python 3.12）

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
py -3.12 -m venv .venv
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

CSV は利用者が利用権限を確認して配置します。データの取得・スクレイピングは実行しません。
MLIT の取引価格データだけから掲載期間や下架イベントを推定しません。掲載終了は成約と同義ではありません。

Docker は初期段階では不要です。PostgreSQL、FastAPI、定期同期、デプロイを導入する段階で検討します。

構成: `japan_housing_liquidity_lab/`（実装）、`tests/`（テスト）、`docs/`（研究設計）、
`data/raw/`（ローカル入力）、`reports/`（生成結果）。データと生成結果は Git の対象外です。

詳細: [研究計画](docs/research-plan.md) · [データ取扱い](docs/data-guide.md)

## English

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

### Quick start (Windows PowerShell)

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
py -3.12 -m venv .venv
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

Supply a local CSV only after checking your permission to use it. There is no downloader or scraper.
Transaction-price records alone are not listing-duration or delisting labels. Delisting does not imply a completed sale.

Docker is unnecessary initially. Consider it later for PostgreSQL, FastAPI, scheduled synchronization, or deployment.

Layout: `japan_housing_liquidity_lab/` (code), `tests/`, `docs/`, `data/raw/` (local inputs), and `reports/` (generated outputs).
Data and generated results are ignored by Git.

Details: [Research plan](docs/research-plan.md) · [Data guide](docs/data-guide.md)
