# JapanHousingLiquidityLab

日本の住宅市場における価格動向・掲載期間・掲載終了リスクを分析し、データに基づく住宅購入の意思決定支援を目指す研究プロジェクト。 | A data-driven research project analyzing housing prices, listing duration, and delisting risk in Japan.

## 日本語

開発初期の個人研究プロジェクトです。現時点では、実市場の予測サービスではありません。
NII データは必須ではなく、ネットワーク接続なしで合成データによる基準モデルを実行できます。

### 最初の実行（Windows PowerShell / Python 3.12）

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab demo
```

すでに `.venv` がある場合、作成コマンドは不要です。追加パッケージのインストールや環境の有効化は不要です。
PyCharm のプロジェクトインタープリターには `.venv\Scripts\python.exe` を指定してください。
再実行時は `demo --output reports/run-002` のように新しい出力先を指定します。既存の結果は上書きしません。

### 現在できること

- 再現可能な合成データ、右打ち切りを扱う Kaplan–Meier 基準モデル、7日・30日の集団リスク出力。
- ローカル CSV の文字コード（UTF-8 / CP932）、列名、欠損数、行数、不正な列数、SHA-256 の検査。
- 標準ライブラリのみのテスト。価格に応じた個別予測や因果推論は未実装です。

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

An early-stage independent research project, not a live market prediction service.
NII is optional. The synthetic baseline runs offline with Python 3.12 and no third-party dependencies.

### Quick start (Windows PowerShell)

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab demo
```

Skip environment creation if `.venv` already exists. No activation or package installation is required.
Select `.venv\Scripts\python.exe` as the project interpreter in PyCharm.
For subsequent runs, use a fresh directory, such as `demo --output reports/run-002`; existing results are never overwritten.

### Available now

- Seeded synthetic data, a right-censored Kaplan–Meier baseline, and population risks at 7 and 30 days.
- Local CSV inspection: UTF-8 / CP932, headers, missing counts, row counts, malformed widths, and SHA-256.
- Standard-library tests. Individual price-based prediction and causal inference are not implemented.

```powershell
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab inspect-mlit data/raw/your_mlit.csv
```

Supply a local CSV only after checking your permission to use it. There is no downloader or scraper.
Transaction-price records alone are not listing-duration or delisting labels. Delisting does not imply a completed sale.

Docker is unnecessary initially. Consider it later for PostgreSQL, FastAPI, scheduled synchronization, or deployment.

Layout: `japan_housing_liquidity_lab/` (code), `tests/`, `docs/`, `data/raw/` (local inputs), and `reports/` (generated outputs).
Data and generated results are ignored by Git.

Details: [Research plan](docs/research-plan.md) · [Data guide](docs/data-guide.md)
