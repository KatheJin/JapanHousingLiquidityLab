# Task 006 — 歴史的購入機会 / Historical opportunity analysis

## 日本語

55,652件の公開取引標本とTask005既存モデルを使用。再学習なし。原本・旧実験を上書きしない。
本機能は2026-11-08以後に利用可能と確認した現行版から過去を記述するもので、過去時点の意思決定を再現しない。
基準日が保守的取得日より前なら拒否。取引期間を狭くしてもモデルは2026Q2まで学習済みであり、過去当時のas-of比較にはならない。
参照は2026Q2、11月の即時相場ではない。2026Q2は標本不足・補録・修訂の可能性がある。

入力はexamples/listing.jsonと同形式。reference_date必須、history_start/history_end任意（例2024Q1/2025Q4）。
建築年または整数房齢を使用。年単位房齢のため誕生日・竣工月の精度はない。
フィルタは同市区町村・駅、指定時は町名一致、面積±20%、取引時点房齢と入力参照房齢の差±10年。
指定された間取り・構造も一致。本Taskではこの2条件を追加しておりTask005のカバー率とは直接比較不可。
距離はモデル特徴で、厳密一致条件ではない。各レコードは取引時点の属性を使う。重複候補は自動削除しない。

比較方法:
- raw_unit_price: 未調整の円/㎡。
- quality_all_history: y_i × exp(f_no_time(x_query) − f_no_time(x_i))。価格・面積・駅等に依存する既存モデルで入力属性へ正規化。
- quality_recent_sensitivity: 同じ式を直近学習の時間なしモデルで計算。
- quality_and_time: y_i × exp(f_time(x_query,2026Q2) − f_time(x_i,t_i))。
- time_only: 各取引の房齢・その他属性を固定して四半期だけ2026Q2へ移動した予測比。建築年を同じ年数ずらし房齢を維持。

これらは残差を保持するモデル補助の記述的変換で、価格指数・因果効果・独立予測性能ではない。
元取引が学習に含まれるため、残差を性能証明に使わない。未使用データで調整比の妥当性を独立検証していない。
Task005の開発誤差は参考情報のみで、調整結果の校正区間には転用しない。外挿的な調整倍率もフラグ付け。

『有利』の計算上の定義は、各方法の単価が入力挂牌単価を厳密に下回ること。等値は含めない。
10件未満では比率をnull、判定を「无法判断」。件数・分位点は記述用に残す。10件以上でも将来確率や高品質の保証ではない。
全体判断は「无法判断」を維持。楼階・装修・向き・管理など未観測品質を評価できず、成約価格と挂牌価格も異なる。
四半期0件は『取得済み標本内で該当なし』であり、市場0件ではない。未取得期はnullに区別。未公開期は要求を拒否。
最近は2025Q3–2026Q2、以前は2025Q2以前という固定区分で比較（指定窓との共通部分）。

実行結果: 6000万円・70㎡例は全期間で5件、2023Q2/Q3、2024Q2/Q4、2025Q2に各1件。
原単価中央値138.46万円/㎡、属性・時間調整159.04万円/㎡。少標本なので低価格比率は非表示。
3000万円・25㎡・1K例は40件。以下の方法差が大きく、単一の『機会割合』を選択すべきでない。

## English

Reuses 55,652 observed transactions and existing Task005 models without training. Old data/experiments remain unchanged.
This is a current-vintage retrospective description, not historical as-of decision reconstruction. Reference dates before conservative acquisition availability are rejected.
Restricting the historical window does not remove later data from the fitted model. The anchor is 2026Q2, not live November prices; the latest release may be revised.

Input follows examples/listing.json, with required reference_date and optional history_start/history_end. Year or integer age is supported.
Filters: same municipality/station, exact town if supplied, area ±20%, age-at-trade within ±10 years of the query's anchored age,
plus exact supplied layout and structure. Those last two conditions are stricter than Task005. Distance is a model feature, not an exact filter.
No duplicate deletion. Age is annual rather than month-exact.

Raw comparison uses unit prices. Quality adjustment multiplies observed unit price by exp(query log prediction minus historical-row log prediction)
using the no-time model. A recent-model variant measures method sensitivity. Combined adjustment uses the time-feature model at each row's observed quarter
and the query's 2026Q2 anchor. Time-only adjustment changes quarter while holding every other transformed feature, including age, fixed.
The construction year is shifted by the year difference solely to keep age fixed in that counterfactual.
These model-assisted descriptions retain observed residuals. They are not causal effects, a house-price index or independent prediction performance.
Rows may belong to model fitting data; their residuals are not validation evidence. Existing development errors do not calibrate adjustment-ratio uncertainty.

A lower-price record has a strictly lower raw/adjusted unit price than the asking unit price; ties do not count.
Below 10 records, the fraction is null and judgment is withheld. Counts/quantiles remain descriptive. Even above 10,
fractions are neither future purchase probabilities nor proof of better overall value. Current value judgment always abstains.
Floors, renovation, orientation and management are missing; asking and transaction prices differ.
Zero within a downloaded quarter means no matching observed records, not zero market sales. Missing acquired periods are null; unpublished periods are refused.
Recent means 2025Q3–2026Q2; earlier means through 2025Q2, intersected with the requested window.

The JPY60m/70m² example finds five records, one each in 2023Q2/Q3, 2024Q2/Q4 and 2025Q2. Raw median JPY1,384,615/m²;
combined adjusted median JPY1,590,361/m². Fractions withheld for low n. The JPY30m/25m²/1K example finds 40 records;
large method sensitivity below prevents selecting one convenient opportunity fraction.

## 25㎡例 / 25m² example

| Method | n | Median JPY/m² | Lower-price fraction |
|---|---:|---:|---:|
| raw_unit_price | 40 | 1250000 | 35.0% |
| quality_all_history | 40 | 1151341 | 70.0% |
| quality_recent_sensitivity | 40 | 1140372 | 72.5% |
| quality_and_time | 40 | 1360869 | 10.0% |
| time_only | 40 | 1453728 | 10.0% |

## 地域カバー診断 / Regional support diagnostics

日本語: 50市区町村について各最大10件、決定論的等間隔で抽出した歴史属性例492件を2026Q2へ置いて検査。
自分自身の行を除き、町名条件を省略。136例で他の厳密一致候補が10件以上。無作為標本ではなく、地域人口や現行市場のカバー率ではない。
地域別結果はreports/opportunity-006-coverage/regional_probes.csv。Task005の地域カバーは別ファイルで旧ルール・旧期間と明記。
改善は許諾データ蓄積と地理・駅ID整備、未使用標本で事前登録した調整法検証。篩選基準を緩めて信頼を水増ししない。

English: For 50 municipalities, inspect up to 10 evenly spaced historical archetypes each, anchored to 2026Q2, excluding their own row and omitting town.
Of 492 diagnostic probes, 136 have at least 10 other strict matches. This is deterministic support diagnosis, not random sampling or current-market coverage.
Regional results are in reports/opportunity-006-coverage/regional_probes.csv. Prior Task005 coverage is separately labeled with its different rules/period.
Next validation requires authorized richer data, station/geographic identifiers and preregistered adjustment evaluation on untouched observations—not relaxed filters.

## CLI

```powershell
python -m japan_housing_liquidity_lab.opportunity --input examples/listing.json --output reports/opportunity-new
python -m japan_housing_liquidity_lab.opportunity --input examples/opportunity-small-unit.json --output reports/opportunity-small-new
python -m unittest discover -s tests -v
```

JSON: analysis.json; individual retained record adjustments: comparable_records.csv; quarter counts: quarter_counts.csv.
Model artifact and input CSV hashes are recorded/checked. Only load trusted local joblib files. Outputs never overwrite directories.
28 automated tests pass, including strict filters, formula identity/scaling, tie handling and small-sample refusal. No failed fitting experiments: no fitting performed.
Failed comparisons are recorded through null fractions and refusal statuses. Existing time-gate tests also remain in the suite.
Raw data and generated outputs remain ignored by Git. No commit/push.
