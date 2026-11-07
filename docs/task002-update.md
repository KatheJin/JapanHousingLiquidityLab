# Task 002 更新 / Update

## 日本語

対象は2023Q1から最新公開四半期まで。2026-11-08に公式画面で最新2026Q2を確認。
今回取得したのは東京都・中古マンション等・取引価格のみの2023Q1一批だけ。
公式 ZIP と CSV は data/raw/2023Q1/ に保存。manifest.json に出典、取引期間、取得日、件数、両ファイルのSHA-256と品質を記録。
公開日は不明として null を保持し、初回確認日時とは区別する。過去時点予測にこの最新版を遡及利用しない。
実 CSV の取引時期を既存内部列の取引時点へ対応付け。分析結果は reports/tokyo-2023Q1-real/。
他年の列・文字コード・欠損の比較は未実施。未取得四半期はゼロではない。未公開の2026Q3以降は対象外。
跨ファイル監査は全項目一致、候補キー一致、ファイルハッシュ一致を分けて報告する。
候補と完全一致は重複し得る。匿名化・丸めにより別取引でも一致し得るため、自動削除も自動結合もしない。
新四半期計画は公開済み一覧と取得済み一覧の差分を使う。APIの取得・公開一覧の自動取得は未実装で、キーは不使用。
次は公式画面で残りを四半期単位で取得し、各バッチの manifest と監査を確認する。

## English

Scope starts at 2023Q1 and ends at the latest published quarter; the official UI showed 2026Q2 on 2026-11-08.
Only one Tokyo used-condominium transaction-price batch, 2023Q1, has been acquired.
The official ZIP/CSV and manifest are local under data/raw/2023Q1; the manifest records source, trade period,
download date, record count, SHA-256 hashes and quality. Publication date remains unknown (null), distinct from first observed availability.
Do not backdate this current vintage for historical as-of forecasting. CSV 取引時期 is mapped to internal 取引時点.
Outputs are under reports/tokyo-2023Q1-real. Cross-year schema/encoding/missingness comparison is pending.
Missing batches are not zero transactions; unpublished quarters are excluded.
Pre-merge audit distinguishes file identity, full-record equality and candidate matches; categories overlap.
Rounded anonymous records may represent distinct trades. No automatic deletion or merging occurs.
The update planner computes published minus acquired quarters without fixed years. Automatic publication discovery and API fetching remain unimplemented.
Next acquire remaining quarters through the official UI and review each manifest and pre-merge audit.

```powershell
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab.transactions data/raw/2023Q1/Tokyo_20231_20231.csv --latest-quarter 2026Q2 --output reports/new-run
```
