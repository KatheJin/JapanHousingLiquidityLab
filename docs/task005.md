# Task 005 — 価格競争力 / Price competitiveness

## 日本語

[最終監査](task005-final-review.md)：学習期間・可比カバー・誤差範囲の確認。

手動JSONから挂牌価格、面積、市区町村、町名（任意）、駅、距離、建築年または房齢、間取り、構造、基準日を入力。
これは現在の掲載市場価格ではなく、2026Q2までの遅行取引参照。2026-11-08時点で期末から131日経過。
実際の公開日は不明。取得日を保守的な利用可能日として、それ以前の基準日は拒否。将来価格予測も11月への時間外挿もしない。
データはTask003の55,652件。原CSVハッシュを検証し、Task004を変更せず独立ディレクトリへ保存。

比較は固定Ridge alpha=10で、全履歴・時間なし、直近4四半期・時間なし、全履歴・時間あり。
開発評価では2023–2024学習（直近モデルは2024のみ）、2025評価。既に観測済みの開発集合であり独立テストではない。
現行参照は2023Q1–2026Q2全部で再学習、直近は2025Q3–2026Q2。2026の新規評価・チューニングなし。
全手法を併記し、検証されていない単一の現在価格へ統合しない。MAPEは精度率ではない。

可比取引は同一市区町村・駅、指定時は町名も一致、面積±20%、房齢±10年、直近4四半期。最低10件。
候補を増やすための自動緩和はしない。距離・間取り・構造はML特徴だが比較対象の厳密一致条件ではない。
可比中央値と四分位は未調整の過去分布で、現時点の価格とは呼ばない。町名を指定しない駅単位ルールで開発評価。開発評価の候補期間は全2025サンプルに対して2024Q1–Q4に固定し、ローリング更新ではない。現行入力の候補期間は2025Q3–2026Q2。
件数不足は分布だけを参考表示し、MLとの比較評価では予測を棄権。MLも同じ可比カバー部分で評価を併記。

全対象データは保持。2025の絶対log残差90百分位を経験的範囲として示すが、現行再学習モデルの被覆保証はない。
リアルタイム証拠と未使用検証がないため本版の競争力結論は「无法可靠判断」。5%差などで高安を断定しない。
町名はMLで未使用。同名駅、丸め、築年不明、低カバー、高価格帯、時間差には注意。
初回実行は列リスト共有の実装バグで停止。修正してv2に再実行し、失敗記録v1を保持。パラメータ変更なし。

## English

[Final review](task005-final-review.md): fitting periods, comparable coverage and uncertainty audit.

Manual JSON accepts asking price, area, municipality, optional town, station, walking-time value/range, construction year or age,
layout, structure and reference date. This is a lagged transaction reference through 2026Q2, not today's live listing market.
At 2026-11-08 the period-end lag is 131 days. Actual release dates are unknown; acquisition is the conservative availability date.
Earlier reference dates are rejected. No extrapolation to November or future appreciation forecast is produced.
Uses the 55,652 Task003 rows, verifies source CSV hashes, and preserves Task004 artifacts.

Three fixed Ridge alpha=10 methods: all history without time, recent four quarters without time, history with time.
Development fits 2023–2024 (recent: 2024) and evaluates 2025. This exposed development set is NOT independent test evidence.
Current references refit through 2026Q2 (recent: 2025Q3–2026Q2); no new 2026 evaluation or tuning.
All methods are shown without inventing a single validated current value. MAPE is not accuracy.

Comparables require identical municipality/station, town if supplied, area ±20%, age ±10 years and the latest four transaction quarters.
Minimum 10; no automatic relaxation. Distance, layout and structure are model features but not strict comparable filters.
Comparable medians/IQRs are explicitly unadjusted historical distributions. Development evaluates the station-level rule without town. Its candidate pool is fixed at 2024Q1–Q4 for every 2025 evaluation row; it is not a rolling window updated during 2025. Current-input comparables use 2025Q3–2026Q2.
Below threshold, comparable prediction abstains. ML comparison on the identical covered subset is also saved.

All records are retained. Empirical ranges use development 90th-percentile absolute log residuals and are not calibrated coverage guarantees for refitted models.
Without contemporaneous evidence and untouched validation, v1 always returns “无法可靠判断” for current competitiveness.
A 5% deviation is not a confident overpricing signal. Town is not an ML feature; same-name stations, rounding, missing age and drift limit reliability.
The first run failed due to shared feature-list mutation; fixed without tuning, rerun in v2, and the failed v1 record retained.

## 開発評価 / Development comparison

| Method | n | MAE JPY/m² | MAPE % | Coverage |
|---|---:|---:|---:|---:|
| all_history_no_time | 16915 | 272379 | 23.25 | 100.00% |
| recent_no_time | 16915 | 255890 | 22.77 | 100.00% |
| history_with_time | 16915 | 236603 | 22.18 | 100.00% |
| comparable | 4843 | 202845 | 18.70 | 28.63% |

Full metrics and matched-subset comparison: evaluation.json. Municipality, price-band and age-band errors/coverage: development_subgroups.csv.
Development predictions retain insufficient-comparable cases for auditing. No new independent test is claimed.

## 実行 / Run

```powershell
python -m japan_housing_liquidity_lab.competitiveness assess --artifact reports/competitiveness-005-v2/reference.joblib --input examples/listing.json --output reports/competitiveness-005-v2/listing-result.json
python -m unittest discover -s tests -v
```

Uses the existing Task004 model dependencies and Python environment. Only load trusted locally generated joblib artifacts.
Outputs include each model's unit/total reference, relative deviation, empirical range, comparable count/distribution/period,
data lag, model version and refusal reasons. Output files are never overwritten.

次段階: 許可された現行挂牌サンプルで現在性を確認し、可比ルールと不確実性を事前登録して未使用期間で検証。
Next: obtain authorized current listings and pre-register comparable rules and uncertainty evaluation on a future untouched period.
Do not turn this historical screen into a ranking before that validation.
