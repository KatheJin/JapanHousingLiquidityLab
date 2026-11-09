# Hedonic Pricing Model — Phase 1・2 / Audit and Robustness

## 日本語

2026-11-10。基準commit 30a3a87。旧Task003～012のコード・モデル・結果を保持し、追加モジュールだけで探索する。UI、オンデマンドcrawler、モデルの自動置換は対象外。

### Phase 1 再利用監査

|実装|実際の入力・再利用・注意点|
|---|---|
|benchmark.py|Task004は55,652件。2023～24学習、2025選択、2026Q1/Q2は既閲覧。保存された選択モデルはHGB。Features/Pipeline/指標を再利用。|
|competitiveness.py|Task005の現在参考は3本ともRidge alpha=10。全履歴・時間付きは2023Q1～2026Q2、recentは2025Q3～2026Q2。開発評価は2023～24学習（recentのみ2024）、2025評価。55,652件用。|
|opportunity.py|Task006は同じ55,652件とTask005 v2 bundle。2018～22を暗黙に使わない。属性・時間調整は学習内記録を含む記述診断。|
|expansion.py|2018～22の85,236件を追加して140,888件を保存するimport。auditの既定入力はなお55,652件。keep_age_atは年齢固定の仮想特徴用に建築年を一時的に動かす。実住宅の建築年変更ではない。|
|temporal.py|Task008の140,888件を指定して実施したrolling検証。split_masks・scoreを再利用。新しい独立テストではない。|
|location.py|既定は140,888件。予算・地区・駅の記述比較。任意のTask005参考モデルは55,652件学習の診断であり、拡張データで再学習しない。|
|web_adapter.py / streamlit_app.py|実価格・歴史ページは55,652件＋Task005 v2。地域ページだけ140,888件。合成demoは別経路。掲載追跡はTask010 journalであり、この成交集合とは別。変更なし。|

実ファイルはそれぞれ2023Q1～2026Q2の55,652件と2018Q1～2026Q2の140,888件で確認。ハッシュは独立実験protocolに保存。

Ridge入力は面積、取引年－建築年の整数房齢、駅徒歩分／区間幅、線形quarter_index、および市区町村・駅・距離種別・間取り・構造。中央値補完、標準化、one-hotを学習fold内だけでfitする。建築年そのものや町名は回帰説明変数ではない。時間なしモデルはquarter_indexだけを除く。HGBも同じFeaturesを利用する。Ridgeに時期項があることだけでは、信頼できる歴史補正を保証しない。

### Phase 2 方法

検証quarterは2026Q1とQ2。2018開始では完全な8年学習が可能なのはこの2foldだけで、3/5/8年を同じ全評価記録で比較する。Q1学習末は2025Q4、Q2学習末は2026Q1。前foldの評価記録が次foldの過去学習に入るのはrollingの定義であり、同一foldの未来値は使わない。2026は既閲覧のため全比較は探索的。公表日の過去版は不明で、historical as-of backtestではない。2026Q2は収録・修訂制限がある。

48組 = 2fold × 3window × 2model × 4設定。raw、学習単価の上側99%点縮尾、99.5%点縮尾、robustを固定比較。下側は変更しない。RidgeのrobustはHuber(epsilon=1.35, alpha=.01, max_iter=500)、HGBは同じ設定のabsolute_error。Huber未収束は失敗候補として記録し、推奨対象にしない。原評価値・外れ値・匿名重複は全て維持。評価価格帯は固定の50/100/150万円/㎡境界。MAE、MAPE、符号付き誤差は円/㎡・%で報告。

Q2の経験誤差範囲だけは、同じ設定の前fold Q1のOOF絶対log残差90%点を利用。Q1には範囲なし。これは校正済み予測区間ではなく、2foldでは安定性を証明できない。予測はexp(log予測)であり、円単価の条件付き平均へのsmearing補正は行わない。

### 調整の計算と利用不可の契約

`hedonic_adjustment.feature_states`は次の順序を明示する：

1. 元住宅・元quarterの特徴。
2. 指定された参照住宅の属性を元quarterで評価（属性差には建築cohortによるその時点の房齢差も含む）。
3. その房齢を保持してquarterだけ動かす仮想特徴。
4. 建築年を固定したまま経過年を房齢へ加える実老化。

`Δ属性=f2−f1`、`Δ時間=f3−f2`、`Δ老化=f4−f3`。合計は必ず`f4−f1`となり、診断単価は`実単価×exp(合計)`。HGBの相互作用では順序依存。仮想的な年齢固定状態はfeature frame上だけで表現し、原建築年を書き換えない。参照住宅を省略すれば属性差は0で同一住宅の経年経路となる。房齢は既存Featuresと同じ年差で、月・quarter内の精密な老化ではない。

単体試験の**合成数値例**：2000年築、2023Q1で23年、2025Q1で25年。仮のf=log(100万円)+.01×面積−.02×房齢+.03×quarter_index、参照住宅80㎡・2005年築、元70㎡なら、属性+.20、時間+.24、老化−.04、合計+.40。100万円/㎡は診断149.18万円/㎡となる。実市場推定ではない。実Pipelineでも直接の終点／始点予測比と一致する回帰テストを実施。

**価格利用可とは判定しない。** 年齢・時期・建築cohortは識別が難しく、時間係数は構成差や未観測品質も含む。HGBは学習時間外のトレンド外挿を保証しない。今回のrolling誤差は純粋な時間・老化補正の真値を検証していない。`status=unavailable`、`adjusted_unit_price=null`を維持する。診断値は別の`diagnostic`に置く。未知建築年は補完せず拒否。比較期が学習支持外なら理由を追加する。公表時点の情報を確認できないため、過去の利用可能価格として返さない。

### Phase 3 接続境界

`decompose(pipeline, record, target_quarter, actual_unit_price, reference=None, train_period=None)`はJPY/㎡を受け取りJSON互換dictを返す。recordは既存CSV形式の日本語属性とYYYYQn。利用者画面はstatus/reasonsを先に表示し、nullを0やraw価格で補わない。diagnosticは高度研究表示専用。予測値を過去の安値確率や将来確率へ変換しない。信頼するローカルfit済みPipelineを渡し、利用者uploadのpickleは受け取らない。

実験CLI：

```powershell
.venv/Scripts/python.exe -X utf8 -m japan_housing_liquidity_lab.hedonic_experiment --output reports/hedonic-phase2-new-run
```

出力先は毎回新規にする。protocol、folds、失敗／未収束、価格帯・自治体・房齢・面積・間取り・quarterの指標、全OOF予測、調整診断はGit無視directoryへ保存する。既存モデルは置換しない。

### 実測結果 / Measured results

全設定で同じ4,962評価行（Q1:3,404、Q2:1,558）。高価格帯は**150万円/㎡以上（境界を含む）1,236行**。単位は万円/㎡。符号付きbiasは予測－実値で、負は低推定。Huberの6fitは全て未収束（†）。48fitの例外は0だが、未収束を成功候補に数えない。

|年 / years|model|training|MAE|MAPE %|high MAE|high bias|
|---:|---|---|---:|---:|---:|---:|
|3|hgb|raw|21.47|19.32|42.42|-36.14|
|3|hgb|robust|21.53|19.73|42.88|-37.11|
|3|hgb|upper99|22.31|19.50|45.76|-41.47|
|3|hgb|upper995|21.88|19.39|43.91|-38.86|
|3|ridge|raw|23.83|21.08|47.93|-39.58|
|3|ridge|robust †|23.36|21.24|46.31|-37.86|
|3|ridge|upper99|24.23|21.08|49.88|-42.59|
|3|ridge|upper995|24.06|21.08|49.00|-41.17|
|5|hgb|raw|21.65|19.34|42.78|-36.61|
|5|hgb|robust|21.92|19.82|44.21|-38.97|
|5|hgb|upper99|22.91|19.60|48.21|-44.76|
|5|hgb|upper995|22.33|19.44|45.80|-41.59|
|5|ridge|raw|24.90|21.22|53.25|-47.65|
|5|ridge|robust †|24.84|21.54|53.45|-48.25|
|5|ridge|upper99|25.36|21.26|55.35|-50.71|
|5|ridge|upper995|25.15|21.23|54.37|-49.26|
|8|hgb|raw|21.92|19.55|43.37|-37.78|
|8|hgb|robust|22.18|19.90|45.28|-41.02|
|8|hgb|upper99|23.50|19.83|50.24|-47.68|
|8|hgb|upper995|22.84|19.66|47.28|-43.64|
|8|ridge|raw|26.28|21.77|57.78|-52.71|
|8|ridge|robust †|26.50|22.20|58.97|-54.59|
|8|ridge|upper99|26.77|21.84|59.92|-55.76|
|8|ridge|upper995|26.54|21.80|58.92|-54.33|

上端縮尾は全て同じmodel/windowのrawよりMAEを悪化させ、高価格帯の低推定も拡大。長期データ追加も予測誤差を改善しなかった。推奨は**3年raw HGBを次段階の候補**、Ridgeを説明・感度診断の基準とする。既存参考modelを自動置換しない。HGBの価格精度は時間／老化補正の妥当性の証明ではない。

3年raw HGBの地域例（記述的な部分群評価、独立の地域テストではない）：

|region|n|MAE 万円/㎡|MAPE %|bias 万円/㎡|
|---|---:|---:|---:|---:|
|中央区|218|33.22|21.48|-14.12|
|千代田区|50|69.71|27.88|-32.68|
|大田区|391|13.38|13.49|-5.07|
|新宿区|318|27.94|17.80|-12.74|
|港区|202|50.56|18.97|-26.17|

HGB rawのQ2経験範囲被覆は3/5/8年で90.50/90.82/91.46%（各n=1,558）。1つの移動quarterでの結果であり、信頼できる90%予測区間を意味しない。Q1範囲は未算出。全期間にはlog目標を計算できない2021Q4の1行があり、原データと別CSVへ保持して学習からだけ外した。2026評価行の除去は0。

実験調整診断はfold/windowごとの学習中央行を決定的に選び、record_idとsource_quarterを保存する。異なるwindowで同じ住宅を診断した結果ではないため、これを時間調整の安定性比較に使わない。固定住宅の恒等式検証は単体／Pipeline回帰試験による。

全地域・価格帯・房齢・面積・間取り・四半期の表は `reports/hedonic-phase2-v1/metrics_*.csv`。訓練期間・件数・縮尾閾値・未収束・warningsはfolds.json/csv。OOF全行はpredictions.csv.gz。既存成果は不変。

### 検証と運用境界

完全suiteは196件、185成功・11skip（35.528秒）。新規10件は合成単位・境界・既存Ridge/HGBとの整合性テスト。55432にlistenerがなく、実PG試験は接続できなかったためskipとし、成功扱いしない。収集器・PostgreSQLの起動停止や再初期化は実施していない。現在の収集進捗はDBへ接続できず未確認。既存303成果と元SQLiteのhash一致を検査し、既存Python/UIの変更は0。新しい成果・全予測・実行logはGit無視。Commit/Pushは行っていない。

## English

Phase 1 confirms that Task004–006 and the real price/history Web pages use the 55,652-row 2023Q1–2026Q2 dataset. The saved Task004 winner is HGB; Task005 current references are Ridge alpha=10 (all-history and linear-time: 2023Q1–2026Q2; recent: 2025Q3–2026Q2). Their 2025 development evaluation uses only 2023–24 training, or 2024 for the recent model. Location and the real budget page use the expanded 140,888 rows from 2018Q1. Expansion imports those records, while its old audit default still targets 55,652. No existing algorithm, UI or model artifact was changed.

Features are area, integer trade-year minus construction-year age, station walking minutes/interval width, linear quarter index and city/station/distance-category/layout/structure. Imputation and encoding fit only training rows. Construction year and town are not explicit regression predictors. Existing age-preserving time diagnostics temporarily shift a counterfactual construction year; the new module instead uses explicit synthetic feature states and preserves actual years.

The fixed exploratory protocol compares 3/5/8-year complete windows on the same 2026Q1 and Q2 holdouts, the only two origins with eight years available. Training ends at the previous quarter. All 48 settings retain every valid evaluation record including the ≥JPY1.5m/m² tail; only training upper targets are capped at 99% or 99.5%, before log transformation. Robust alternatives are Huber for Ridge and absolute-error HGB. Nonconverged Huber fits are reported, not recommended. All 2026 data was previously viewed; this is neither an independent test nor a historical publication-vintage backtest. Q2 may be incomplete/revised.

Q2 empirical error coverage uses only prior Q1 out-of-sample residuals; Q1 has no range. These are not calibrated prediction intervals. Exp(log prediction) is used without a mean-price smearing correction. Output includes MAE/MAPE/signed bias by price band, municipality, period, age, area and layout; full predictions/failures remain ignored locally.

The adjustment path is historical subject -> reference attributes at historical age -> time with age held -> physical aging with construction year fixed. Log effects telescope exactly, so aging is applied once. HGB effects depend on path order. A synthetic test has attribute +.20, time +.24 and aging −.04, total +.40; JPY1m/m² becomes a fitted diagnostic JPY1.4918m/m². This is illustrative arithmetic, not market evidence. Existing Ridge/HGB Pipelines also match direct endpoint prediction ratios in regression tests.

Age, period and cohort are confounded; forward predictive performance does not identify causal depreciation or a pure market index. Therefore `decompose` returns `status=unavailable`, `adjusted_unit_price=null`, reasons and separately labeled diagnostics. Unknown construction years are refused; periods outside fitted support are flagged. Phase 3 must display the refusal first and must not substitute zero/raw prices or turn historical fractions into future probabilities. Accept only trusted local fitted Pipelines, not uploaded pickles. The function signature and CLI above define the interface; no Phase 3 UI is implemented.

Measured results in the table above use identical 4,962 holdout rows (3,404 Q1, 1,558 Q2) and an inclusive ≥JPY1.5m/m² tail of 1,236 rows. MAE and signed bias in the table are JPY10,000/m². The 3-year raw HGB has MAE JPY214,737/m² and MAPE 19.32%, but tail MAE JPY424,216/m² and mean underprediction JPY361,377/m². Capping worsens every matching raw model/window MAE; longer windows do not improve it. All six Huber fits hit the convergence limit and remain failed candidates despite recorded predictions. Recommend 3-year raw HGB only as the next exploratory candidate, with Ridge for explanation; do not replace production references yet.

The regional examples show large variation: Chiyoda n=50 has MAE about JPY697,080/m², versus Ota n=391 at JPY133,799/m². HGB Q2 empirical coverage is 90.50/90.82/91.46% for 3/5/8 years, but one quarter cannot validate calibration. A single uncomputable 2021Q4 target is retained separately and excluded from fitting; no 2026 evaluation row is removed. Training-midpoint diagnostic properties differ across fold/windows and carry record/quarter provenance; they must not be interpreted as matched-property temporal stability evidence.

Verification: the complete suite discovered 196 tests, with 185 passing and 11 PostgreSQL tests skipped (35.528 seconds). No listener was present on 55432; those integrations are not claimed as passed. No collector or database start/stop/reset was performed. Current collection progress could not be checked through the unavailable DB. All 303 prior artifact hashes and the frozen SQLite hash match; existing Python/UI files are unchanged. No commit or push. New full predictions, reports and logs remain ignored locally.
