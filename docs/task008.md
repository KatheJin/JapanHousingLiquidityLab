# Task 008 — 歴史データ拡張と時間検証 / Historical Expansion & Temporal Validation

## 日本語

[最終監査（2026-11-08）](task008-final-review.md)：実験値は不変。今後のJSONキーは `forward_oof_historical_relative_comparisons` とし、旧出力の `independent_historical_relative_comparisons` は独立テストを意味しない。旧成果ファイルは保存する。

### 結論と実験範囲

2026-11-08実施、開始コミット `0cb1ed3`。2018Q1～2022Q4の東京都中古マンション等の不動産取引価格情報85,236件を追加し、既存55,652件と合わせて140,888件、2018Q1～2026Q2の34四半期となった。モデル・既存結果は置換していない。

固定Ridgeによる今回の探索的検証では、履歴を長くすると厳密な比較標本の支持は増えたが、価格予測誤差は改善しなかった。例示住宅の歴史比率も学習期間に敏感で、**価格競争力の結論は「无法判断」**を維持する。過去の低価格割合は将来の購入確率ではない。

### 1. Task 004～006の実装監査

Task 004は市区町村中央値、Ridge、HGBを2023～2024年で学習し、2025年で選択、2026Q1/Q2を一度評価した記録。Task 005/006が使う現在参考モデルはHGBではなく、Task 004のPipelineを再利用したRidge alpha=10である。Task 005の開発評価と現在用再学習を混同しない。

Task 006の原計算は、単価を `y_i`、モデルの対数単価参考を `f(x,t)`、現在例示住宅を `q`、基準期を `T=2026Q2` として：

```text
調整単価_i = y_i × exp(f(q,T) − f(x_i,t_i))
調整単価_i < 掲載単価
  ⇔ y_i / exp(f(x_i,t_i)) < 掲載単価 / exp(f(q,T))
```

したがって、時間入りモデルは**数学的には各取引期のモデル参考に対する比率**を比較している。しかしそのモデルは2023Q1～2026Q2全体で学習しており、未来の取引と評価する当該行も含む。これは現在版の事後的な当てはめ比率であり、各時点以前だけの学習による独立した市場競争力ではない。対象40行は全履歴モデルの学習に全て含まれ、最近モデルには6行が含まれる。学習残差を独立予測精度として使わない。

時間なしモデルは年齢・地域・駅・面積等を調整するが、歴史価格を明示的に最近へ換算していない。時間入りRidgeは全期間共通の線形四半期係数を使用する。両者の差には係数の再推定と時間移動の両方があり、単なる「同じ属性補正＋時間追加」と決めつけられない。Task 006の時間のみ反実仮想では、取引年と建築年を同じ年数だけ動かし、取引時年齢を固定している。実際の原建築年は変更していない。

2026Q2は2026年11月の即時市場ではない。また現在の掲載価格と歴史の実成約価格の間に、検証済みの交渉値引き補正はない。

### 2. 35%・70%・10%の数値分解

入力：世田谷区・三軒茶屋、25㎡、2005年築、徒歩10分、1K、RC、町名指定なし、掲載3,000万円＝120万円/㎡。厳密条件は同市区町村・駅、面積±20%、取引時年齢±10年、指定間取り・構造完全一致。元の40行と計算値を数値許容差1e-10で再現した。

| 方法 | 掲載単価未満の件数 | 割合 |
|---|---:|---:|
| 原単価 | 14/40 | 35% |
| 時間なしモデルによる属性調整 | 28/40 | 70% |
| 時間入りモデルの属性成分だけ | 29/40 | 72.5% |
| 同じ時間入りモデルの属性＋時間 | 4/40 | 10% |
| 時間のみ | 4/40 | 10% |

係数再推定で1行増えた後、時間成分で25行が閾値を上回った。従って70%→10%の主要因はこのケースでは時間成分である。全行の係数・予測基準・判定は `reports/task008-method-audit/decomposition.csv` に保存。

代表行：`Tokyo_20231_20231.csv` のCSV行1908。2023Q1、25㎡、2010年築、駅3分、原単価132万円/㎡。

```text
比較住宅の年齢: 2023−2010=13年、入力住宅: 2026−2005=21年
時間入りモデルの属性log補正:
  面積 0 + 年齢 −0.155321 + 駅分数 −0.125089 + その他 0 = −0.280410
132万円 × exp(−0.280410) = 99.7226万円/㎡
2023Q1→2026Q2: 13四半期、時間log補正 0.279375
時間倍率 exp(0.279375)=1.322303
99.7226万円 × 1.322303 = 131.8635万円/㎡ > 掲載120万円/㎡
```

時間なしモデルの同じ行は100.0021万円/㎡。原住宅が入力住宅より若く駅近なので属性換算で安くなるが、推定時間上昇を加えると閾値を超える。これはモデルの仮定の説明であり、実際の同一品質住宅が32.23%値上がりしたと実証したものではない。時間係数は約0.02149 log/四半期、期間・地区を通じて共通である。入力住宅自体の参考単価は時間なし121.8631万円、時間入り142.6591万円。

### 3. 追加データ・品質

出典：[国土交通省 不動産情報ライブラリ](https://www.reinfolib.mlit.go.jp/)。公式「不動産価格情報の検索・ダウンロード」画面で東京都、中古マンション等、**不動産取引価格情報のみ**を選択し、20四半期を逐次ダウンロード。成約価格情報は含めない。2018Q2～Q4一括11,654件はファイル作成待ちとなったため、同じ大きな要求を繰り返さず四半期へ分割。全20件のCSV行数を画面件数と照合した。クローラー、未承認API、NIIは使用していない。

利用条件は当日公式画面で確認したPDL1.0とサイト規約。出典と加工主体の明記が必要で、国が作成・保証した研究結果として表示しない。統計値はアンケート収集により後日追加・修訂され得る。原資料・全個票・大型成果はGitに含めない。

| 年 | Q1 | Q2 | Q3 | Q4 |
|---|---:|---:|---:|---:|
| 2018 | 4,074 | 3,905 | 3,805 | 3,944 |
| 2019 | 4,039 | 4,054 | 3,987 | 3,903 |
| 2020 | 4,805 | 3,290 | 4,709 | 5,029 |
| 2021 | 4,706 | 4,652 | 4,332 | 4,558 |
| 2022 | 4,406 | 4,319 | 4,388 | 4,331 |

全20CSVはCP932、既存と同じ21列。各バッチのZIP/CSV SHA-256、元フィールド、取引四半期、取得時刻を `data/raw/task008/YYYYQn/manifest.json` に保持。取得時刻はダウンロードZIPの保存時刻を引き継ぎ、日本時間で保存。**公式公開日は不明でnull**、取得日を公開日と呼ばない。現在ダウンロードできた過去データは当年の公表版ではない。CLIは今回の固定実験として2026-11-08より前の基準日を拒否し、価格・面積の非正値／非有限値も拒否する。

追加四半期ごとの空欄率の最小～最大：

| フィールド | 空欄率 |
|---|---:|
| 市区町村・町名・面積・価格・時期 | 0% |
| 駅名・駅距離 | 0～0.0248%（2019Q1の1件） |
| 建築年 | 1.7808～3.0699% |
| 間取り | 3.6754～6.4188% |
| 建物構造 | 1.4547～2.5773% |
| 取引時年齢の変換不能率 | 1.9313～3.1611% |

列が存在すること、空欄でないこと、変換可能なことは別。既存Featuresの西暦年・駅分数／区間処理を再利用し、解釈できない値は欠損のまま学習期間内で補完する。建築年が固定なら年齢は取引年とともに増加する（2005年築は2018年13歳、2026年21歳）。匿名データでは建物IDがないため同一建物の再売買を確実にリンクできない。

追加85,236行のうち1,067行が全元フィールド一致の重複群に属し、4,805行が完全一致群以外の同属性・時期を除く一致フラグに属する。全140,888行ではそれぞれ1,647行、7,534行。これは削除件数・住宅数ではない。丸め値が一致する別取引の可能性があり、全行保持した。IQR等の確認フラグ付き追加行は4,528行、フラグは異常の証明ではない。

2021Q4の1行は面積 `2,000㎡以上`、総額16億円で正確な単価を作れない。上限・下限を勝手に2000と置換せず、原行を残し `uncomputable_targets_retained.csv` に記録、対数ターゲット学習からのみ外した。モデル入力は140,887行。旧EDAに固定されていた2023年開始条件は変更せず、汎用検査・数値変換・特徴変換を新しい独立導入モジュールから再利用した。

### 4. 時間検証設計と結果

四半期ごとに直前の完全な3年／5年／8年を学習し、直後1四半期を評価。欠けた学習四半期があれば短縮して実行せず記録して拒否する。未来の行・検証期の行を学習、補完、カテゴリ符号化に入れない。価格ターゲットはlog円/㎡、PipelineとRidge alpha=10は固定、パラメータ探索・モデル選択なし。比較基準は同じ学習窓の市区町村単価中央値、未知地域は全体中央値。今回はHGBの窓長比較までは行っておらず、結論は固定Ridgeに限定される。

3年は2021Q1～2026Q2の22起点、5年は2023Q1～2026Q2の14起点、8年は2026Q1/Q2の2起点。三者共通の評価4,962行は2026Q1（3,404）とQ2（1,558）だけ。2026Q1の学習窓は2023Q1～2025Q4、2021Q1～2025Q4、2018Q1～2025Q4。2026Q2では各窓を1期進める。

**この2026年標本はTask 004で既に見たデータであり、本結果は探索的比較。新しい独立テストではない。** Q2起点はQ1を学習へ入れる通常のrolling-originだが、Task 004の元テスト記録は不変。真の新規テストは未取得の将来公開四半期を事前に留保する必要がある。公開版不明のため、取引時期で分離した現在版検証であって厳密な歴史公開時点回測ではない。

| 学習窓 | Ridge MAE 円/㎡ | MAPE | 中央値基準 MAE 円/㎡ | 平均符号付き誤差 円/㎡ | 厳密比較10件以上の支持率 |
|---|---:|---:|---:|---:|---:|
| 3年 | 238,345 | 21.08% | 389,874 | -88,111 | 17.03% |
| 5年 | 248,993 | 21.22% | 410,374 | -117,628 | 28.21% |
| 8年 | 262,831 | 21.77% | 439,534 | -134,295 | 39.16% |

支持率は評価住宅の条件（町名も提供されている場合は一致）に対し、その窓内の記録が10件以上ある割合。**これは比較候補プールを広げた記述的効果であり、Aのモデル学習だけの効果とは区別する。** Task 005の28.63%とは期間・条件が違うので直接比較しない。

Ridgeは基準より誤差が小さい一方、長い履歴による改善は見られない。3年でも高単価帯（150万円/㎡超、1,178行）はMAE492,294円/㎡、平均符号付き誤差-407,043円/㎡と過小推定が大きい。低単価帯（50万円以下、460行）では平均+113,373円/㎡の過大推定。全体平均が小さいから各価格帯で中立とはいえない。

行政区・価格帯・年齢帯・面積帯・間取り別のMAE、MAPE、符号付き誤差、支持率をCSVへ出力。例：3年窓で港区MAE711,171円、世田谷区244,090円、八王子市125,078円/㎡だが、八王子市MAPEは53.74%。絶対誤差だけでは地域の信頼性を比較できない。支持率は世田谷区9.23%→28.72%、八王子市2.88%→20.19%（3年→8年）と依然低い。

直前4期の前向きOOF絶対log残差90パーセンタイルを移した経験範囲の共通期被覆は3年90.77%、5年90.29%。8年には直前4期の完全8年窓OOFがなく、範囲を出さない。学習内残差は使用しないが、時間分布の変化・再利用した探索標本があるため**信頼できる校正済み予測区間ではない**。MAPEを「精度＝100−MAPE」に変換しない。

### 5. A/B/C/Dと相対価格の頑健性

旧モデルを置換せず、2026Q1以前だけで学習した2026Q2用モデルを用いる独立実験。

- **A 学習窓のみ**：同じ2023年以降40行・同じ時間付き調整式・同じ評価時点を固定。3/5/8年で事後比率は7.5%、17.5%、22.5%。34/40/40行がそれぞれ学習に含まれるので、これは当てはめ感度の診断であり独立性能ではない。Aの独立予測性能は上の共通前向き評価で検証する。
- **B 比較窓のみ**：3年モデルを固定し、比較開始2023/2021/2018で40/68/106行、調整後記述比率7.5%/5.88%/7.55%。全体の原単価比率は44/106=41.51%。古い比較行を直近モデルで後ろ向きに評価する部分は外挿かつ事後診断であり、当時の競争力とは呼ばない。
- **C/D 同じ係数で2×2**：同じ40行で属性なし・時間なし35%、属性のみ72.5%、時間のみ7.5%、属性＋時間7.5%。これにより属性成分と時間成分を切り分ける。時間方法は「移動なし」と「固定線形時間項」の比較、属性方法は「厳密一致条件だけ」と「その上で同じモデルによる属性比率補正」の比較に限定。複雑な新指数は導入していない。旧10%との差は旧モデルと今回の学習窓・締切が異なるためであり、同じ実験として混ぜない。

修正案として、各歴史行 `i` の参考価格を**その行の取引四半期より前だけ**で学習したモデルで予測し、`r_i = y_i / prediction_before_i` を計算。現在掲載住宅は2026Q1以前のモデルで2026Q2属性を予測し `r_q = asking / prediction_q` とする。`r_i < r_q` を比較し、支持不足は割合を出さない。ランダム交差検証や未来の学習行は使用しない。

| 前向きモデル | 歴史比較対象 | 評価可能 | 相対比率が小さい記録 | 注意 |
|---|---|---:|---:|---|
| 3年 | 2023年以降40行 | 40 | 4/40=10% | 同一対象で5年と比較可能 |
| 5年 | 同じ40行 | 40 | 9/40=22.5% | 5行の分類が変化 |
| 3年 | 2018年以降106行 | 68 | 6/68=8.82% | 38行評価不能、106行全体割合はnull |
| 8年 | 2018年以降106行 | 1 | 割合を出さない | 完全な先行8年学習がほぼ存在しない |

同じ40行の3年・5年参考による相対比率の絶対変化は中央値0.01350、最大0.04702で、現在住宅の参考比率も変わり、5行が閾値を横断した。三窓すべてでOOF評価可能な共通例示取引は1行だけで、三者の歴史比率比較は拒否。直近2025Q3以降も厳密比較は6行で割合を拒否。閾値近辺の分類変化を確定的なお買い得順位と解釈しない。

OOFは自分自身の学習残差という問題を減らすが、残差にはモデル誤差・観測できない階数、改装、向き、管理状態・取引事情が残る。匿名記録の相関や同一建物を除外できないため、独立二項標本を仮定した信頼区間は作っていない。歴史住宅を「より高い総合価値」と断定しない。公表時点・掲載から成約への差・モデル感度を含む信頼性はまだ未検証。

### 6. 再現・テスト・保存

既存Python 3.12環境と `[model]` 依存を使用。ネットワーク取得はCLIに含めない。入力ZIPは公式UIから取得した20ファイル。再実行には新しい出力先・新しいraw先を指定する。

```powershell
python -m japan_housing_liquidity_lab.expansion audit --output reports/task008-audit-rerun
python -m japan_housing_liquidity_lab.expansion import --downloads C:/Users/53141/Downloads --raw data/raw/task008-rerun --output reports/task008-data-rerun
python -m japan_housing_liquidity_lab.temporal --data reports/task008-data/merged_retained.csv --output reports/task008-temporal-rerun
python -m unittest discover -s tests -v
```

データ品質は `reports/task008-data/`、旧方法の行別分解は `reports/task008-method-audit/`、38回の学習窓・四半期組合せの前向き検証と因子別比較は `reports/task008-temporal-v1/`、追加照合・失敗記録・テストログは `reports/task008-validation/`。予測CSVは約50MBでGit対象外。各期間の全入力がない場合に黙って短い窓としない。

自動テスト66件成功（既存50、新規16）。四半期境界、未来行による学習集合の不変性、年齢進行、反実仮想で年齢固定、厳密一致、調整式恒等性、小標本拒否、重複・面積区間の保持、公開日null、上書き拒否を検証。実データ上でも303,914予測行（中央値基準を含む）の学習終了期が評価期より前で、3/5/8年の共通評価IDが同じ4,962行であることを確認。

開始前のdata/reports全146ファイルのSHA-256は一致し、Task 004～007のモデル・成果・研究記録を保全した。旧タスクのソースも変更しない。Commit/Pushなし。

次の優先は、固定した3年モデルと明示的な代替時間仕様を未使用の後続公開期で評価し、地域・価格帯の系統誤差と相対比率の安定性を事前定義した基準で確認すること。今回の結果だけでTask 005/006のモデルを置換しない。古い年を増やす効果をHGB等へ一般化する検証、初回公開版の取得、掲載価格と成約価格の差の検証は未実施。

## English

[Final review (2026-11-08)](task008-final-review.md): numerical results are unchanged. New JSON output uses `forward_oof_historical_relative_comparisons`; the legacy key `independent_historical_relative_comparisons` does not mean an independent test. Original output files remain preserved.

### Outcome and scope

On 2026-11-08, starting from commit `0cb1ed3`, 85,236 official Tokyo used-condominium transaction-price records from 2018Q1–2022Q4 were added to the existing 55,652 records. The retained dataset has 140,888 rows across 34 quarters through 2026Q2. Existing models and results were not replaced. Longer history increased strict-comparable support but did not improve the fixed Ridge model's errors in this exploratory experiment. Current price competitiveness remains **unable to determine**; no historical fraction is a future purchasing probability.

### Existing-method audit and reproducible decomposition

Task 004 compared municipality medians, Ridge and HGB using 2023–2024 training, 2025 validation and an already-viewed 2026 test. Task 005/006 current references use Ridge pipelines, not the selected HGB. Development validation and subsequent current-reference fitting are different fits.

The Task 006 adjustment is `actual_i * exp(log_reference_query - log_reference_i)`. Comparing it with the asking unit price is algebraically equivalent to comparing `actual_i/reference_i` against `asking/reference_query`. The timed model does therefore use a reference at each trade's own period, **but it is retrospectively fitted over all periods, including the historical rows being scored and their future observations**. All 40 comparable records are in the all-history fits; six are in the recent fit. These are fitted residual descriptions, not independent contemporaneous performance. The no-time model does not explicitly bring past prices to a recent date. The timed model assumes a common linear log-price trend across quarters.

The ¥30 million, 25 m² example has an asking unit price of ¥1.2 million/m², Setagaya/Sangenjaya, built 2005, ten minutes from the station, 1K/RC, no exact town restriction. All 40 original outputs were reproduced to numerical tolerance. Raw prices give 14/40=35%; no-time quality adjustment 28/40=70%; the timed model's **attribute component alone** gives 29/40=72.5%; adding its time component leaves 4/40=10%. Refitting the coefficients changes one classification, whereas time adjustment moves 25 records above the threshold.

CSV line 1908 of `Tokyo_20231_20231.csv` illustrates this. Its 2023Q1 price is ¥1.32m/m² for a 25 m² home built in 2010, three minutes from the station. Compared with the query's age 21 and ten-minute distance, its age 13 and better station access produce log adjustments -0.155321 and -0.125089. Attribute adjustment gives ¥997,226/m². Moving 13 quarters with log time factor 0.279375 multiplies this by 1.322303, yielding ¥1,318,635/m²—above the ¥1.2m asking threshold. This explains the fitted calculation; it does not establish actual constant-quality appreciation of 32.23%. Per-record references, factors and classifications are saved in the audit CSV. November's asking price is still compared against a lagged 2026Q2 transaction reference, with no validated asking-to-sale discount adjustment.

### Acquisition and quality

Source: [MLIT Real Estate Information Library](https://www.reinfolib.mlit.go.jp/). The official UI was used for 20 sequential quarterly downloads, selecting Tokyo, used condominiums and transaction-price information only. All CSV counts matched the UI counts in the Japanese table above. A combined 2018Q2–Q4 request returned an official file-preparation notice; it was replaced with smaller quarterly requests rather than repeatedly submitted. No crawler, unapproved API or NII source was used.

The official PDL1.0/site terms were inspected: credit the source and processing author, do not imply government authorship or endorsement. Data can be supplemented or revised. Every raw ZIP/CSV has a SHA-256, acquisition timestamp, period and original schema manifest. Publication dates are unknown/null; the current historical download is not the version published at the time. The frozen-experiment CLI rejects reference dates before 2026-11-08 and nonpositive/nonfinite asking prices or areas.

All 20 new files are CP932 with the same 21 fields as the existing data. Quarterly missing rates range from 1.78–3.07% for construction year, 3.68–6.42% for layout and 1.45–2.58% for structure. One 2019Q1 row lacks station/distance; city, town, area, total price and period have no blanks. Parsed age is unavailable for 1.93–3.16%, demonstrating that nonblank does not mean interpretable. The existing transformer computes age as transaction year minus construction year; a 2005 building ages from 13 in 2018 to 21 in 2026. Anonymous records do not support reliable building linkage.

Among added rows, 1,067 belong to exact-duplicate groups and 4,805 have the separate non-exact, same-attributes-excluding-period flag. Across the full dataset these are 1,647 and 7,534 rows. They are flags, not proven duplicate transactions or counts to remove. All remain retained. IQR/other review flags affect 4,528 added rows and are not proof of error. One 2021Q4 row reports area “2,000 m² or above” with total price ¥1.6bn; it is retained but has no exact unit target and is excluded only from log-target fitting. Model-eligible rows total 140,887. Unknown fields are not forcibly imputed from future data; pipeline imputers and encoders fit only on each training window.

### Forward validation

The frozen Ridge alpha=10 pipeline uses log unit prices and a linear quarter feature. Each origin trains on exactly the preceding complete 3/5/8 years and evaluates the next quarter; unavailable windows are recorded and never silently shortened. A municipality unit-price median is the simple baseline. No hyperparameters were tuned or model selected. This phase does not test HGB training-window effects.

There are 22 three-year origins, 14 five-year origins and two eight-year origins, totaling 38 fits. The shared three-window evaluation is only 2026Q1/Q2, with identical 4,962 records. These records were already seen in Task 004: **all Task 008 comparisons are exploratory, not new independent tests**. The Q2 origin can train on Q1, as ordinary rolling-origin validation, without changing Task 004 artifacts. Unknown original release vintages prevent a strict historical-publication-as-of backtest.

Three/five/eight-year Ridge MAEs are respectively ¥238,345 / ¥248,993 / ¥262,831 per m², with MAPEs 21.08% / 21.22% / 21.77%. Median-baseline MAEs are ¥389,874 / ¥410,374 / ¥439,534. Mean signed errors are -¥88,111 / -¥117,628 / -¥134,295: longer histories increase underprediction in this sample. MAPE is not converted into “accuracy.”

Strict-comparable support of at least ten records increases from 17.03% to 28.21% to 39.16%. This is a descriptive **candidate-pool expansion effect**, distinct from training-data-only factor A. Matching includes exact supplied town/layout/structure and does not weaken Task 006 rules. These rates are not directly comparable with Task 005's different-scope 28.63%.

Errors and support are output by municipality, fixed unit-price band, age, area and layout. With three-year training, the >¥1.5m/m² group has MAE ¥492,294 and signed bias -¥407,043, while the ≤¥0.5m group has signed bias +¥113,373. Minato's MAE is ¥711,171 versus Setagaya ¥244,090 and Hachioji ¥125,078, but Hachioji MAPE is 53.74%. Low absolute errors need not imply reliable relative pricing. Geographic support remains uneven.

Empirical ranges use the 90th percentile absolute log error from four strictly preceding OOF quarters, never training residuals. Shared-period coverage is 90.77% and 90.29% for three/five years. Eight-year ranges are unavailable because four earlier complete-window OOF quarters do not exist. These transferred empirical ranges are not reliably calibrated prediction intervals, particularly on reused exploratory observations.

### Separate factors and historical-relative-price robustness

All new experiments remain separate from production references. Factor A changes only training-window length while holding the 40 comparison rows, formula and reference quarter fixed: fitted descriptive fractions are 7.5%, 17.5%, 22.5%. Training overlaps of 34/40/40 are recorded explicitly; these fitted fractions are not independent performance. Forward held-out errors provide A's predictive evaluation.

Factor B fixes the three-year model and extends comparison history from 2023 to 2021 to 2018: 40/68/106 comparable rows and descriptive adjusted fractions 7.5%/5.88%/7.55%. The full raw fraction is 44/106=41.51%. Applying a recent model backwards is a retrospective diagnostic, not contemporaneous historical competitiveness.

Factors C/D form a fixed-coefficient, fixed-record 2×2 comparison: no adjustment 35%, attributes only 72.5%, time only 7.5%, both 7.5%. This separates enabling the linear time adjustment from enabling model-based attribute adjustment, without introducing a new index. The new 7.5% is not the old model's 10%: training cutoffs/windows differ and are documented separately.

The proposed improvement predicts each historical trade using only quarters strictly before its trade quarter, forming `actual / prior-trained reference`. The query ratio uses a model trained through 2026Q1 to reference 2026Q2. No random cross-fitting or later training observations enter a historical prediction. On the same 40 post-2023 comparables, three-year OOF ratios give 4/40=10%, and five-year ratios 9/40=22.5%, with five classifications changing. Median absolute ratio movement is 0.01350, maximum 0.04702; the query reference also changes.

For the full 106 historical comparables, only 68 have a three-year prior training history, of which six (8.82%) have a lower relative ratio. The full-history fraction remains null because 38 early records are unevaluable. The eight-year method has only one OOF comparable, and recent history since 2025Q3 has only six strict records: fractions are refused. Only one record is common to all three OOF windows, so a three-way historical-fraction conclusion is unsupported.

Forward prediction removes direct self-fitting but residuals still contain model error, omitted floors/renovation/orientation/management, transaction circumstances and reporting effects. Anonymous repeats create dependence, so no independent-binomial confidence interval is asserted. Neither historical bargain status nor future opportunities are established. Production replacement is not justified.

### Reproduction and remaining work

Use the existing Python 3.12 `[model]` environment and the three CLI commands above with fresh output directories. CLI import is offline and expects the 20 official ZIPs. Outputs are in `reports/task008-data`, `task008-method-audit`, `task008-temporal-v1`, and `task008-validation`; the prediction table is approximately 50 MB and Git-ignored. Raw manifests are under `data/raw/task008`.

All **66 tests passed** (50 existing, 16 added), covering forward boundaries, future-row exclusion, age progression/counterfactual invariance, strict matching, ratio identities, small-sample refusal, duplicate/bounded-area retention, unknown publication dates and overwrite protection. All 303,914 exported prediction rows (including baseline rows) have training end before evaluation quarter; all three windows share identical 4,962 validation IDs. All 146 pre-existing data/report files retain their hashes. Task 004–007 source/models/results are preserved; no commit/push, web application or appreciation forecast was introduced.

Next, freeze a short-window reference and explicit alternative time specifications before obtaining an unused later quarter, then assess regional bias and relative-ratio stability against predeclared criteria. HGB window comparisons, original first-release vintages and validated asking-to-sale differences remain untested. The current evidence does not justify replacing Task 005/006 references.
