# Task 004 — 価格基準モデル / Price benchmark

## 日本語

対象は東京都中古マンション等、Task 003の55,652件。原本は変更・削除せず、価格と面積が正で計算可能な単価を対象。
2023–2024を学習、2025を検証、2026Q1–Q2を一度だけテスト。現時点の公開版を用いた遡及的時間分割であり、
当時の公開日が不明なため厳密なas-ofバックテストではない。2026Q2は補録・修訂の可能性がある。

Pipeline内で特徴変換、学習データのみの中央値補完・欠損指標、カテゴリ補完・符号化、モデル学習を実施。
市区町村、駅、距離、面積、房齢、間取り、構造、四半期を使用。NFKC正規化。
距離は数値分をそのまま、30–60分/60–90分/90–120分を中点と区間幅で表し、120分以上は下限120と専用カテゴリ。
不明値は欠損。建築年は西暦のみ抽出し、取引年との差を房齢にする。戦前・未来年・150年超は欠損。
面積は公表丸め値であり精密な専有面積ではない。四半期は2023Q1からの整数時間で、Ridgeは外挿、木モデルは端点外挿が不得意。
駅は同名異駅があり得る。町名は今回候補に含めず、駅と市区町村を別特徴として使用。

目的変数はlog(円/㎡)。逆変換はexpのみで、期待算術平均を保証しない。
基準は市区町村別log単価中央値（未知地域は全体中央値）。Ridge alpha=10、one-hotの最小頻度10。
HGBは200反復、15葉、学習率0.07、最小葉30、L2=10、早期停止なし。カテゴリは最大200、未知=-1で欠損相当、
カテゴリとして分岐するため駅番号に数値順序を仮定しない。乱数42。ハイパーパラメータ探索はしていない。
主3モデルの2025 MAEで選択し、選択を保存後に2026を評価。テストによる再調整・再学習なし。
感度分析はHGBの学習log目標のみ1–99百分位へ縮尾。閾値は学習のみから算出し、検証・テストは一切縮尾しない。
原本・異常値・重複候補を削除しない。同一匿名記録が異なる取引を表す可能性があり、同一物件の時点間重複は識別不能。

予測範囲は検証絶対log残差90百分位による経験的範囲。個別物件の保証区間・因果効果・価格指数ではない。
価格帯別評価の境界も学習単価四分位から固定。小標本行政区の誤差は不安定。
protocol.json、selection.json、metrics.json、audit.json、failures.jsonと価格帯/地域/四半期別誤差を保存。

## English

Uses 55,652 Task 003 Tokyo used-condominium records. Originals remain untouched; the target requires a positive computable unit price.
Train 2023–2024, validate 2025, test once on 2026Q1–Q2. This is a retrospective temporal holdout on the current vintage,
NOT a historical as-of backtest: release dates are unknown and the latest quarter may be revised.

All feature conversion, training-only imputation, encoding and fitting are in sklearn Pipelines.
Features: municipality, station, distance, area, age, layout, structure and integer quarter trend.
NFKC normalization; bounded distances use midpoints and width plus a category, open-ended 120+ minutes uses the lower bound and a category.
Unknown distances are missing. Age is transaction year minus Gregorian construction year; prewar, future and implausible years become missing.
Published area is rounded. Same-name stations may differ. Ridge extrapolates time linearly; HGB cannot reliably extrapolate beyond training times.

Target is log JPY/m², inverted with exp without mean-bias correction. Baseline: municipality median log price, global fallback.
Ridge alpha=10 with one-hot/min-frequency 10. HGB: 200 iterations, 15 leaves, learning rate .07, min leaf 30, L2=10,
no early stopping, seed 42. Categorical features have at most 200 encoded values and are explicitly treated as categorical.
No hyperparameter search. Select among three primary models by 2025 MAE, persist selection, then evaluate 2026 once.
The predeclared sensitivity model clips only training log targets to training 1st/99th percentiles; evaluation targets remain unchanged.
No raw rows or duplicate candidates are deleted. Anonymous records prevent reliable property-level grouping across time.

The empirical range uses the validation 90th percentile absolute log residual; it has no property-specific or temporal coverage guarantee.
Price-band thresholds are training quartiles. District errors with small n are unstable. This model is not a causal estimate or house-price index.
Settings, selection, metrics, audit, failed experiments and subgroup metrics are persisted alongside the trusted local model artifact.

## 実測評価 / Observed evaluation

MAE unit: JPY/m².

| Model | Validation MAE | Test MAE | Test MAPE % | Test median APE % | Test WAPE % |
|---|---:|---:|---:|---:|---:|
| median | 365852 | 402722 | 34.07 | 25.93 | 32.48 |
| ridge | 236603 | 256930 | 21.46 | 16.08 | 20.72 |
| hgb | 228515 | 283651 | 22.39 | 18.65 | 22.88 |
| hgb_winsor | 234636 | 289164 | 22.40 | 18.59 | 23.32 |

Split sizes: train 33775, validation 16915, test 4962.
Empirical 90% range test coverage: 84.54%.

## CLI

This run used the installed Python 3.12 environment with sklearn 1.6.1, numpy 1.26.4, pandas 2.2.3, scipy 1.14.1.
Install the optional model dependencies into your virtual environment for future runs: `python -m pip install -e ".[model]"`.

```powershell
python -m japan_housing_liquidity_lab.benchmark predict --artifact reports/benchmark-004-v1/benchmark.joblib --input examples/home.json
python -m unittest discover -s tests -v
```

Only load trusted locally generated joblib files. Quarter must be within evaluated scope 2023Q1–2026Q2; city must be in Tokyo.
The CLI returns unit price, area-based total, empirical error range, version and scope. Unseen categories and missing attributes reduce confidence.
Reproducing the fixed experiment is allowed; using test results to tune another v1 run is not.

Official definitions: https://www.reinfolib.mlit.go.jp/realEstatePrices/about/

## 結果の解釈 / Interpretation

日本語: 2025検証で選択されたHGBを保持。2026ではRidgeが良かったが、テストを見て選択を変更しない。
HGBのMAEは単純基準より29.6%低い。学習目標縮尾では改善しなかった。最高価格帯MAE約48.93万円/㎡、
港区約69.38万円/㎡（202件）で、高価格領域は要改善。経験的90%範囲のテスト被覆率は84.54%で保証に不足。
306件の完全一致候補を保持し、単価計算不能は0件。全17テスト合格。
学習実験の失敗なし。CLI初回表示はWindows文字コードで失敗し、JSONエスケープ出力に修正。学習や選択は変更していない。
次段階の研究には進む価値があるが、自動査定・購入判断の単独根拠には未成熟。時系列ローリング検証を事前登録し、
次の未使用公開期で評価する。2026テストは今後開発データとして扱い、新たな独立テストとは呼ばない。

English: Keep the HGB selected by 2025 validation. Ridge performs better in 2026, but selection is not changed after test inspection.
HGB improves MAE by 29.6% over the group baseline. Target winsorization did not improve MAE.
Highest price-band MAE is about JPY 489,263/m²; Minato MAE is JPY 693,790/m² (202 rows).
The nominal empirical 90% range covers only 84.54% of test outcomes. 306 exact duplicate candidates are retained; no targets are uncomputable.
All 17 tests pass. No training experiment failed. The first CLI print failed due to Windows encoding; JSON escaping fixed display without retraining.
Further research is justified, but this is not ready as a stand-alone valuation or purchase decision tool.
Pre-register rolling temporal validation and evaluate on a future untouched release; 2026 is now exposed and cannot be reused as an independent test.
