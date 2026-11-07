# Task 003 — 履歴データ / Historical data

## 日本語

2026-11-08取得。2023Q1〜2026Q2の14四半期、東京都中古マンション等の取引価格55,652件を取得・分析。
未取得四半期なし。ただし公開標本は全市場を網羅せず、最新期は補録・修訂され得る。2026Q2は1,558件であり、取引量急減とは結論しない。
全バッチはCP932、同一21列。2023Q2のZIPには成約価格情報4,731件も含まれたため、原本を保管して分析対象から区別。
3回の誤種類ダウンロードはdata/excludedへ隔離し、公式画面から再取得・照合。制限回避やクローラーは使用していない。
各バッチのhistorical_manifest.jsonに出典、取得時刻、四半期、ZIP/CSVハッシュ、件数、原列を記録。
公開日は不明でnull。取得時刻と取引四半期を混同せず、現在版を過去時点で利用可能だったと仮定しない。

全対象行をmerged_retained.csvに保持。計算不能な価格・面積は単価を空欄にしてフラグ付けし、対象行自体は削除しない。
四半期内の1.5 IQRで総額3,698件、面積287件、単価2,005件を標記。これらは異常の証明ではなく確認候補で、相互重複あり。
全項目（取引四半期含む）の跨ファイル完全一致は0件。匿名化・丸めにより同値の別取引があり得るため自動重複削除なし。
市区町村、町名、駅名、駅距離、面積、価格、四半期は空欄0。ただし駅距離の範囲・文字列は数値分と同一視しない。
面積列は公表面積の丸め値であり、未丸め専有面積と同等の精度を仮定しない。

単価中央値は94.0から114.29万円/㎡へ推移。構成変化を含む観測標本の統計であり、住宅価格指数ではない。
次は地域・駅・面積・築年・間取り・構造による対数価格基準モデル。欠損フラグ、駅距離区間の処理、時系列分割、
外れ値を保持した結果と頑健推定の比較を行う。取引後に記録された特徴の利用可能時点も点検する。

## English

Acquired on 2026-11-08: all 14 quarters from 2023Q1 through 2026Q2, totaling 55,652 Tokyo used-condominium transaction records.
No target quarters are missing. Survey data is not a census; latest releases may be revised. The 1,558 observations in 2026Q2 do not establish a market-volume collapse.
All batches use CP932 and the same 21 columns. The 2023Q2 archive also contained 4,731 contract-price records, kept in the original but excluded by category.
Three wrong-property downloads were quarantined under data/excluded and replaced through the official UI. No crawler or restriction bypass was used.
Per-batch historical_manifest.json records provenance, acquisition time, quarter, ZIP/CSV hashes, counts and original headers.
Publication dates remain null. The current vintage must not be assumed available at historical prediction dates.

All target rows are retained in merged_retained.csv. Uncomputable unit prices remain null with flags; no target row is deleted.
Within-quarter 1.5-IQR flags mark 3,698 prices, 287 areas and 2,005 unit prices, with overlapping categories; flags are review candidates, not proven errors.
There are zero cross-file exact full-record matches including the transaction quarter. Rounded anonymous values do not establish transaction identity; no automatic deduplication is applied.
Municipality, district, station, distance, area, price and quarter have zero blank cells. Nonblank station-distance ranges/text require dedicated parsing.
Published rounded areas must not be treated as precise unrounded exclusive floor areas.

Median unit price moves from JPY 940,000 to 1,142,857 per m². This composition-sensitive series is NOT a house price index.
Next: a log-price baseline with geography, station, area, age, layout and structure; missing indicators, interval-aware distance handling,
temporal holdout, robust-estimation sensitivity and feature-availability checks.

## 四半期集計 / Quarterly statistics

単価は万円/㎡ / Unit prices in JPY 10,000 per m².

| Quarter | n | P25 | Median | P75 |
|---|---:|---:|---:|---:|
| 2023Q1 | 4036 | 65.25 | 94.00 | 120.00 |
| 2023Q2 | 4168 | 66.67 | 96.00 | 120.00 |
| 2023Q3 | 4346 | 66.67 | 96.00 | 120.00 |
| 2023Q4 | 4227 | 66.67 | 97.50 | 122.86 |
| 2024Q1 | 4243 | 68.57 | 100.00 | 127.69 |
| 2024Q2 | 4448 | 69.23 | 100.00 | 128.00 |
| 2024Q3 | 4230 | 71.19 | 102.36 | 128.89 |
| 2024Q4 | 4077 | 70.00 | 101.82 | 131.43 |
| 2025Q1 | 4166 | 71.75 | 104.00 | 135.00 |
| 2025Q2 | 4118 | 72.31 | 105.80 | 136.00 |
| 2025Q3 | 4493 | 75.00 | 108.57 | 140.00 |
| 2025Q4 | 4138 | 75.79 | 110.00 | 143.64 |
| 2026Q1 | 3404 | 80.00 | 114.29 | 150.00 |
| 2026Q2 | 1558 | 81.93 | 114.29 | 145.86 |

## 特徴欠損率 / Feature missingness

| Field | Min missing % | Max missing % |
|---|---:|---:|
| 市区町村名 | 0.00 | 0.00 |
| 地区名 | 0.00 | 0.00 |
| 最寄駅：名称 | 0.00 | 0.00 |
| 最寄駅：距離（分） | 0.00 | 0.00 |
| 面積（㎡） | 0.00 | 0.00 |
| 建築年 | 1.63 | 3.27 |
| 間取り | 5.57 | 11.49 |
| 建物の構造 | 1.23 | 3.15 |
| 取引価格（総額） | 0.00 | 0.00 |
| 取引時期 | 0.00 | 0.00 |

## 再実行 / Reproduction

```powershell
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab.history --output reports/history-new --latest-quarter 2026Q2
python -m japan_housing_liquidity_lab.history --output reports/history-new --plot-only
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

集計は標準ライブラリのみ。図の再作成にはMatplotlibが必要（今回ローカル既存環境で実行）。
Aggregation uses the standard library; plotting requires Matplotlib (run here in the existing local Python installation).
Outputs: batch_comparison.csv, feature_availability.csv (per-quarter blank rates and value-type counts), quarterly.csv,
municipality.csv, quarter_municipality.csv, merged_retained.csv, summary.json, quarterly_prices.png.
All raw data, manifests and outputs stay ignored by Git. No commit/push.

Source: https://www.reinfolib.mlit.go.jp/realEstatePrices/
