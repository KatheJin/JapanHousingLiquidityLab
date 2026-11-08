# Task 009 — 地域・駅アクセスと住宅価格 / Location, Access & Housing Prices

## 日本語

[歩行距離の逆転5組の補足研究](task009-walk-supplement.md)：町名・住宅構成差と高仕様住宅集積仮説の識別限界。モデル変更なし。

[最終監査](task009-final-review.md)：87テスト成功。過去終了期に対する開始期の既定値、同一上下限、交通方式の未知状態契約を修正。既存の予算例の研究数値は不変。

### 範囲と結論

2026-11-08、基準コミット `03eac49`。Task 008の2018Q1～2026Q2、東京都中古マンション等140,888行を再利用。新規モデル学習、MLIT再取得、旧モデルの置換、Commit/Pushは行っていない。

地域・駅別の記述統計、予算条件に合う歴史取引の住宅属性、駅アクセス時間帯の比較をCLI/JSON/CSVで実行した。**現在売出中の物件一覧、通勤時間に基づく推薦、確定的な割安順位は出さない。** 鉄道の合法的な候補データは見つかったが、実時刻表・駅ID対応・乗換グラフの検証は未実施。通勤条件は未検証として明示する。

### データ・統計方法

- 出典は [MLIT 不動産情報ライブラリ](https://www.reinfolib.mlit.go.jp/realEstatePrices/)。既存 `reports/task008-data/merged_retained.csv` と `quality.json` のSHA-256、行数、四半期を照合し、既存の数値解析・年齢・駅分数変換を再利用する。加工は本プロジェクトによる。母集団の全取引ではない。
- 50市区町村、875の既知「市区町村＋駅名」組合せ、駅名欠損群1つ。駅名のNFKC正規化だけを行い、`大森(東京)`等の識別文字は除去しない。同名駅を異なる行政区間で自動統合しない。これは住宅市場のラベルであり、鉄道駅ID・路線の検証済み対応ではない。
- 欠損／変換不能：駅1、面積1、取引時年齢3,322、間取り7,808、構造2,754、駅分数1、単価1。市区町村・総額は0。面積「2,000㎡以上」の元行、重複、価格異常値を保持。各集計に有効件数・欠損件数・異常確認フラグ件数を出す。未知の必要条件を満たした扱いにしない。
- 原総額、円/㎡、面積、取引時年齢の25/50/75パーセンタイル、間取り最頻値を表示。各値の有効数30件未満では分位値を出さない。間取り最頻値も既知間取り30件以上に限定。30件は表示の最低条件であり、精度保証ではない。IQRは標本の広がりであり、信頼区間ではない。
- 原総額の予算上限・下限、面積、取引時年齢、駅アクセス上限、間取り、構造、行政区をANDで選ぶ。これは歴史の名目成約価格で、現在の掲載価格・諸費用込み予算ではない。住宅条件だけの一致であり、鉄道通勤制約は適用していない。
- 30～60分の区間は30/60の境界を保持し、45分とは扱わない。上限45分には不適合、上限60分には適合。未知値は時間制約に適合させない。MLITの最寄駅時間距離を列車時間やドアツードア時間に置換しない。
- 年・四半期ごとにも集計。未取得四半期はゼロではなく指定を拒否。2026年はQ1/Q2のみで完全な年ではなく、Q2や過去年も追加・修訂され得る。ダウンロード版は当時の公開版ではなく、初回公開日不明。取得確認日2026-11-08より前の参照日は拒否する。

### 標本支持と予算例

全履歴で30件以上は48行政区、636駅地域。あきる野市17件、西多摩郡瑞穂町7件では分位値を出さない。駅地域では中央区・勝どき1,464件、墨田区・両国1,187件、江東区・豊洲1,159件、江東区・亀戸1,102件、豊島区・池袋914件など。ただし全履歴の支持が最近の条件付き支持を保証するわけではない。

例示入力：**6,000万円以下、40㎡以上、取引時築40年以下、駅アクセス15分以内、2025Q1～2026Q2**。間取り・構造の制限なし。期間内21,877行のうち3,842行が住宅条件に合い、30件以上は32行政区・8駅地域。45分通勤の入力は保存するが、未検証であり選定に使っていない。

| 地域 | 条件一致数 | 面積中央値 ㎡ | 取引時築年齢中央値 | 最頻間取り |
|---|---:|---:|---:|---|
| 新宿区 | 47 | 40 | 22 | 1LDK |
| 世田谷区 | 79 | 50 | 27 | 1LDK |
| 杉並区 | 95 | 50 | 26 | 2LDK |
| 板橋区 | 276 | 60 | 27 | 3LDK |
| 練馬区 | 207 | 60 | 27 | 3LDK |
| 府中市 | 119 | 65 | 26 | 3LDK |
| 調布市 | 74 | 65 | 26 | 3LDK |
| 八王子市 | 210 | 70 | 23 | 3LDK |

港区10件、渋谷区9件は比較統計を拒否する。「この予算では買えない」とは意味しない。支持のある8駅地域は北綾瀬59、八王子49、梅島40、府中(東京)39、南大沢34、お花茶屋33、両国32、東向島30件。駅地域別の年齢・面積もCSV/JSONに保存。これらは観測された過去の住宅条件の違いであり、同一品質・同一通勤時間での優劣ではない。

### 歩行・アクセスと価格

全履歴の原単価中央値は0～5分100万円/㎡（56,400件）、5分超～10分95万円（55,751）、10分超～15分70万円（20,437）、15分超～20分50万円（5,255）、20分超～29分36.25万円（2,076）。地域・年齢・面積・時期の構成が同時に違うため、距離の因果効果や「10分ごとの固定下落率」と解釈しない。

同じ行政区・駅・年の0～5分対10分超～15分で、双方30件以上ある組合せは14。うち5組では遠い側の原単価中央値が高い。勝どき2023年の遠い側／近い側は1.026、2024年は0.714。年内の四半期構成・住宅品質も残るため、駅の恒久的なプレミアムや逆転の原因は確定できない。属性調整まで支持条件を満たす対応比較は0組で、調整後の歩行効果は判断不能。非線形な価格関係を検証するには同じ駅・時期の十分な属性支持が必要。

### 属性調整と時期比較

任意の `--reference` で、保存済み `reports/competitiveness-005-v2/reference.joblib` 内の時間付きRidgeを使う。新しく学習しない。固定住宅像は50㎡、取引時築20年、2LDK、RC。市区町村・駅・駅分数・取引四半期は各原行のままにする。

```text
属性調整単価_i = 原単価_i × exp[f(固定住宅像, 元の場所・アクセス・期) − f(元住宅)]
```

適用はモデルの学習範囲2023Q1～2026Q2と既知の場所組合せ、解釈可能な属性に限定。2018～2022年をこのモデルで外挿せず、その属性調整値はnull。表示には調整可能行30件以上と、同じ集計内で面積±20%・築年齢±10年・同間取り構造の固定住宅像支持10件以上を要求する。これは集計単位の支持であり、各個票の反実仮想や駅ごとの十分な重なりを保証しない。

調整前後を公平に見るため、`standardized_subset_raw_unit_*` は**調整可能な同一行だけ**の原単価分布。全履歴の原中央値と2023年以降だけの調整中央値を直接比較しない。場所・歩行・時期は残すので、都市全体の共通立地や現在価格に換算した値でもない。

2025年の同一行比較では、港区603行の原中央値195万円/㎡→属性調整218.147万円、足立区622行は62.3611万円→71.5153万円。両者比は約3.127→3.050。一方、新宿区／江東区の比は約1.185→1.299となる。属性構成の補正はすべての地域差を一様に縮めない。残る差には場所・駅アクセス・年内時期・未観測品質・モデル誤差が含まれ、純粋な立地価値とは呼ばない。

原単価の時期差の例：港区2018年116万円/㎡→2025年196.75万円、足立区42.7922万円→62.5万円、世田谷区81.4286万円→112万円。これは異なる成約標本の名目中央値で、品質調整済み指数ではない。年別表と四半期表を併用し、2026年半期を過去の通年と無条件に比較しない。

Task 008で時間調整に敏感だったため、今回の属性補正は時間項を移動しない。モデルの学習行を含む事後的な属性感度診断であり、独立予測精度ではない。Task 004のテスト、Task 008のOOFを新しい検証成績として再利用しない。

### 多中心・鉄道データの調査

渋谷・新宿・東京・品川・池袋を別々の目的地として保持し、任意の目的地名も入力できる。単一中心距離、駅座標からの直線時間換算、仮の乗換分数は実装しない。将来は目的地別の到達時間ベクトル、路線・方向・乗換・出発時刻を保持する。一中心から離れて別中心に近づく可能性を、単一の距離係数に潰さない。

現在の「最寄駅が東京」の標本は中央区6件のみ、品川は港区411件／品川区14件、新宿も新宿区105件／渋谷区142件に分かれる。これだけでも駅名の単純統合や目的地周辺価格の一般化が危険なことが分かる。路線方向や中心間の交通優位性そのものはまだ検証していない。

2026-11-08に確認した公式候補：

| 提供者・形式 | ライセンス・利用条件 | 今回の到達点 |
|---|---|---|
| [東京都交通局 GTFS/GTFS-JP](https://ckan.odpt.org/dataset/train-toei)、[列車時刻表JSON](https://ckan.odpt.org/dataset/r_train_timetable-toei) | CC BY 4.0。東京都交通局・公共交通オープンデータ協議会をクレジット | 都営地下鉄等の候補を確認。全東京鉄道網ではない |
| [東京メトロ時刻表](https://ckan.odpt.org/dataset/r_train_timetable-tokyometro) | ODPT基本ライセンス。登録・キーと当該データ条件の確認が必要 | 公式カタログ確認のみ。キー利用なし |
| [JR東日本時刻表](https://ckan.odpt.org/en/dataset/jreast__r_train_timetable) | Challenge 2026限定ライセンスと個別条件 | 一部関東路線・列車の限定データ。恒久利用可能と仮定しない |

[ODPT基本ライセンス](https://developer.odpt.org/terms/data_basic_license.html)にはデータの再配布・再利用可能な派生データ公開に制約がある。事業者ごとに条件を確認し、都営のCC BYを他の鉄道に流用しない。[GTFS仕様](https://gtfs.org/documentation/schedule/reference/)は時刻・運行日・停留所・便等の構造を定義するが、形式がGTFSであることは網羅性・利用許諾・乗換時間の正確性を保証しない。

カタログの単一メタデータAPIを確認したが、HTTP 200のHTMLが返り、JSONとしては利用できなかった。これを時刻表取得成功と数えず、反復大量取得もしなかった。GTFS本体は今回は取得・検証していない。**合法的な候補は見つかったが、信頼できる通勤計算は未完成**という区別を維持する。

次の交通作業は公式リソースから都営の小さな版付きGTFSを取得し、取得日・ハッシュ・運行有効日・再利用条件を記録、便と停車時刻・曜日例外・24時超表記を検査すること。MLIT駅名とoperator/route/stop IDの対応を人手で点検し、公式時刻表の経路例と照合する。待ち時間、駅内徒歩、乗換、終着駅から目的地までの時間が未確認なら、総通勤時間を出さない。現行時刻表を2018年の交通条件として遡及適用しない。

### CLI・出力・検証

例示JSONは `examples/location-budget.json`。開始期省略時は指定終了期までの6四半期（データ開始期まで）。終了期も省略時はデータ内最新期を使う。`reference_date` と `budget_max_jpy` は必須。他のフィルタは任意、未知キーは拒否する。`transport_modes` は `public_transport`（既定）、`private_car`、`bicycle`、`mixed` を受け付けるが、各方式の時間・制約達成はnull、未対応と明示する。方式一覧は経路の組合せではない。`max_walk_minutes` は方式にかかわらず最寄駅アクセスという住宅条件のまま。通勤上限は保存するだけで、出力の `commute.constraints_applied=false`、`door_to_door_minutes=null` を必ず確認する。

```powershell
.venv/Scripts/python.exe -X utf8 -m japan_housing_liquidity_lab.location --query examples/location-budget.json --reference reports/competitiveness-005-v2/reference.joblib --output reports/location-009-rerun
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

`--reference` を省略すれば記述統計のみ。`--data` と `--quality` で別の監査済みTask 008データを指定できる。出力先が存在すれば拒否し、旧結果を上書きしない。

正式結果は `reports/location-009-v2/`：`analysis.json`、`budget_comparison.json`、`regions_*`、`stations_*`、`budget_*`、`walk_*`、`layout_distribution.csv`。v1は初期実行記録として保持し、同一行の原価格比較と間取り支持チェックを追加したv2を読む。全詳細ファイルはGit無視対象。CSVのnullは標本不足／属性調整不能を意味し、価格ゼロではない。

初期実装時は全テスト **80件成功（既存66、新規14）**。最終監査で7件追加し、現在は87件成功。単位、境界、区間の保守的選択、欠損、同名駅分離、小標本、同一行の属性比較、時期維持、公開版制限、原データ不変、ハッシュ拒否、通勤非適用、実CLI出力、上書き拒否を検証。最初の試験では合成予測器のSeries添字整列とWindows子プロセス出力エンコーディングの問題を検出し、予測配列の明示変換とUTF-8テスト実行で修正した。新しい研究モデルは作っていない。

開始時点の旧data/reports全236ファイルのSHA-256が一致。Task 004～008の原モデル・成果は不変。新規の実データ・詳細出力も既存Git無視規則で除外され、追跡済みのdata/reports/modelsファイルはない。検証記録は `reports/location-009-validation/`。提出候補はREADME、`docs/task009.md`、`docs/task009-final-review.md`、`examples/location-budget.json`、`japan_housing_liquidity_lab/location.py`、`tests/test_location.py` の6ファイルのみ。

## English

[Supplement on five reversed access-price contrasts](task009-walk-supplement.md): town/property composition and limits of the high-specification concentration hypothesis; models unchanged.

[Final review](task009-final-review.md): 87 tests passed. Corrected default historical start, equal inclusive bounds and explicit unsupported transport modes. Existing example statistics are unchanged.

### Scope and methods

Task 009 reuses 140,888 Tokyo used-condominium records, 2018Q1–2026Q2, from baseline commit `03eac49`. It adds offline CLI/JSON/CSV location and historical-budget analysis without new model fitting, MLIT downloads, production replacement, commit or push. It does not identify live listings or verify railway commute feasibility.

The input is checked against Task 008's SHA-256, counts and quarter inventory. Existing parsers preserve duplicate/outlier rows and bounded-area uncertainty. Missing/unparsed counts are station 1, area 1, age 3,322, layout 7,808, structure 2,754, station access 1 and unit price 1. Counts describe sampled records, not the market population.

Municipality plus normalized station name identifies a local market label; these are not verified railway IDs. There are 50 municipalities, 875 known municipality/station groups and one unknown group. Quantiles require 30 valid values per metric; layout modes require 30 known layouts. These are reporting thresholds, not confidence guarantees. IQRs describe sample dispersion, not prediction/confidence intervals. No independent-binomial assumptions are made for anonymous potentially repeated properties.

Budget filtering combines nominal historical total price, area, age at transaction, station-access upper bound, optional layout/structure and municipality restrictions. Unknown required attributes fail the filter. A 30–60 minute interval fails a 45-minute cap and passes a 60-minute cap; its midpoint is never an observed commute time. Unknown quarters are rejected, not filled with zeros. Original publication vintages are unknown, and 2026 contains only Q1/Q2 with possible incomplete/revised coverage.

### Findings

Forty-eight municipalities and 636 known station-market groups have at least 30 records across the full history. Akiruno (17) and Mizuho (7) fail this descriptive gate. Large groups include Chuo/Kachidoki (1,464), Sumida/Ryogoku (1,187), Koto/Toyosu (1,159), Koto/Kameido (1,102) and Toshima/Ikebukuro (914). Long-run sample size does not ensure recent conditional support.

For the example—up to ¥60m, at least 40 m², age up to 40 at transaction, access up to 15 minutes, 2025Q1–2026Q2—3,842 of 21,877 period records match housing filters. Thirty-two municipalities and eight station-market groups pass the 30-record gate. The Japanese table provides representative area/age/layout differences: Shinjuku's median area is 40 m², Setagaya/Suginami 50 m², Itabashi/Nerima 60 m², Fuchu/Chofu 65 m² and Hachioji 70 m². Minato (10) and Shibuya (9) are insufficient, not proven unaffordable. These are historical samples at different quality and accessibility, not equivalent homes currently available for purchase. The requested 45-minute commute remains unverified and was not applied.

Pooled access-band unit-price medians are ¥1.00m/m² for 0–5 minutes, ¥0.95m for >5–10, ¥0.70m for >10–15, ¥0.50m for >15–20 and ¥0.3625m for >20–29. Composition differs strongly. Only 14 municipality/station/year pairs support both near and farther bands with at least 30 records; five have a higher farther-band median. None meets the additional profile-support requirements for adjusted paired contrasts. Neither a universal ten-minute price penalty nor a reliable nonlinear response has been established.

Yearly raw medians also differ: Minato ¥1.16m/m² in 2018 versus ¥1.9675m in 2025; Adachi ¥0.427922m versus ¥0.625m; Setagaya ¥0.814286m versus ¥1.12m. These are composition-dependent nominal sample medians, not a quality-adjusted price index.

### Optional attribute sensitivity

The saved Task 005 v2 timed Ridge standardizes to 50 m², age 20 at transaction, 2LDK and RC while retaining each record's location, station access and trade quarter. The formula is observed unit price multiplied by the ratio of fixed-profile to observed-home model references. It does not move the time term or translate past prices into current prices. Application is limited to known locations/attributes in 2023Q1–2026Q2; earlier records remain unadjusted.

Displayed adjustment requires 30 computable records and ten profile-support records within the aggregation group: area ±20%, age ±10 years and exact layout/structure. This aggregate gate does not guarantee support for every counterfactual or station. The `standardized_subset_raw_unit_*` fields use exactly the same rows as adjusted statistics, preventing period/missingness composition from masquerading as an adjustment effect.

On identical 2025 subsets, Minato (603 rows) changes from ¥1.95m/m² raw to ¥2.18147m standardized; Adachi (622) changes from ¥0.623611m to ¥0.715153m. Their ratio moves from about 3.127 to 3.050. Shinjuku/Koto instead moves from about 1.185 to 1.299. Attribute adjustment does not uniformly shrink regional gaps; remaining differences include access, within-year timing, omitted quality and model error, not pure location value.

This is retrospective fitted sensitivity, including training observations, not independent predictive performance. It preserves the Task 008 warning about temporal stability and does not reuse Task 004 tests as fresh evaluation.

### Polycentric design and transport sources

Shibuya, Shinjuku, Tokyo, Shinagawa and Ikebukuro are separate candidate destinations, with custom names supported. Future research should retain destination-specific travel times, departure/service dates, lines, directions and transfers rather than assume one centre or convert straight-line distance into minutes. Even station-name price samples differ: Tokyo has only six Chuo records; Shinagawa and Shinjuku span multiple municipality labels. Their prices cannot validate travel-time rankings or railway identities.

The official source links in the Japanese table were checked on 2026-11-08. Toei publishes GTFS/GTFS-JP and timetable JSON under CC BY 4.0 with provider credit. Tokyo Metro uses the ODPT Basic License; JR East's listed partial network timetables use Challenge 2026 conditions. These licenses and coverage scopes must not be treated as interchangeable. ODPT Basic License redistribution conditions require particular care. GTFS defines timetable structure; it does not guarantee network completeness or verified transfers.

No timetable feed was acquired or validated in this task. The single catalog metadata endpoint examined returned HTML rather than usable JSON; this was recorded as a failed metadata attempt, not a download success. Legal candidates were found, but station mapping, schedules and transfer validation remain incomplete. No credentials, scraper, fabricated times or route planner were used.

Next, obtain one official versioned Toei feed, record hashes/license/service dates, validate trips/stop times/calendar exceptions/after-midnight times, manually resolve MLIT station labels, and compare sample journeys with official schedules. Waiting, interchange and destination access must be verified before producing door-to-door times. Current timetables must not be retroactively treated as 2018 transport conditions.

### Running and validation

Use `examples/location-budget.json` and the command above with a new output directory. Without `--reference`, only descriptive statistics are computed. The default start is six quarters through the requested end, bounded by the dataset start; only an omitted end uses the latest quarter. Supplied periods are checked for complete observed-quarter coverage. `transport_modes` accepts `public_transport` (default), `private_car`, `bicycle` and `mixed`; each remains unsupported with null time and limit-satisfaction fields. The list does not combine route legs. The JSON always reports `commute.constraints_applied=false` and null door-to-door minutes. Results are historical housing-filter matches only.

Final detailed outputs are in `reports/location-009-v2/`, including JSON summaries and regional/station/year/quarter/budget/access tables. V1 is retained as an initial run; v2 adds identical-row raw comparisons and the known-layout denominator gate. Both are Git-ignored. Null statistics are not zero prices.

The initial implementation passed **80 tests: 66 existing and 14 new**. Final review adds seven regression tests, for 87 passing tests. Coverage includes units, interval bounds, missingness, station-name collisions, sample gates, paired adjustment/time preservation, vintage rejection, hash integrity, actual CLI behavior, commute abstention and overwrite protection. Initial test-harness issues with Series alignment and Windows subprocess encoding were resolved. No new research model was trained.

All 236 pre-existing data/report files retain their SHA-256 hashes, including Task 004–008 models/results. Raw data and detailed generated outputs remain ignored, with no tracked files under data/reports/models. Local verification is in `reports/location-009-validation/`. Only README, this document, the final-review document, the example JSON, location module and its synthetic tests are candidates for submission. No commit or push was performed.
