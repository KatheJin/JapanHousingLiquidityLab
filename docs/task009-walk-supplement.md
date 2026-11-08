# Task 009 補足：遠駅側が高い5比較 / Five Reversed Station-Access Contrasts

## 日本語

### 要旨・対象

**現在の証拠は住宅・町名・取引時期の構成差を示す。「高級住宅の集積が駅徒歩距離への価格感応度を弱める」という条件付き効果は未検証である。** 高価格、RC、タワー、ブランド名のいずれかだけで高級住宅とは定義しない。

2026-11-08実施。元の14組（同市区町村・駅・年、近側0～5分、遠側10分超～15分、両側30件以上）の中央値比を全て再現し、遠側が高い5組・462行に限定して記述分析した。事後的に結果を見て選んだケース研究であり、5/14を東京全体の発生確率としない。4組は同じ勝どきの異なる年であり、5つの独立した地域証拠ではない。モデル学習・旧モデル変更・個票の建物照合・交通時間推定は行わない。

### 1. 単価・面積・年齢

価格は実成約総額÷面積、単価表の単位は万円/㎡。矢印は**近側→遠側**。年齢は取引年－建築年。年齢欠損は勝どき2020・2023の近側で各2件、他は0件。年齢中央値は既知行だけで計算した。

| 駅・年 | 件数 近／遠 | 単価中央値 近→遠 | 遠側の差 | 面積中央値 ㎡ 近→遠 | 年齢中央値 年 近→遠 |
|---|---:|---:|---:|---:|---:|
| 勝どき2019 | 38／64 | 92.40→104.38 | +12.96% | 50→55 | 17→4 |
| 勝どき2020 | 44／48 | 85.83→106.90 | +24.55% | 35→65 | 22→5 |
| 勝どき2021 | 46／64 | 106.50→114.61 | +7.61% | 42.5→62.5 | 18→6 |
| 勝どき2023 | 46／47 | 127.64→130.91 | +2.56% | 50→65 | 14→8 |
| 亀戸2021 | 33／32 | 94.44→97.50 | +3.24% | 25→25 | 12→11 |

単価IQR（近／遠、万円/㎡）は順に72.98–104.66／94.05–114.00、64.75–100.00／99.71–117.05、81.75–126.50／107.92–121.54、105.63–165.92／123.25–140.66、73.33–100.00／68.30–112.00。全5組で重なり、中央値の大小が個々の住宅の順位を決めるわけではない。IQRは信頼区間ではない。

勝どきの遠側は一貫して若く大きい。したがって同じ年・駅であるだけでは同じ住宅品質を比較できていない。亀戸では逆に総額中央値が近側2,500万円、遠側2,350万円で、**遠側の単価が高いことと総額が高いことは別**である。

### 2. 町名・間取り・構造

| 組 | 遠側の町名 | 近側の町名 | 2LDK＋3LDK件数 近／遠 | RC件数 近／遠 |
|---|---|---|---:|---:|
| 勝どき2019 | 晴海64 | 勝どき35、月島3 | 15/38／50/64 | 27/38／52/64 |
| 勝どき2020 | 晴海48 | 勝どき35、月島9 | 11/44／34/48 | 23/44／43/48 |
| 勝どき2021 | 晴海64 | 勝どき40、月島6 | 16/46／51/64 | 29/46／53/64 |
| 勝どき2023 | 晴海47 | 勝どき43、月島3 | 20/46／40/47 | 36/46／41/47 |
| 亀戸2021 | 亀戸30、大島2 | 亀戸33 | 12/33／3/32 | 18/33／25/32 |

件数の分母には欠損も含む。構造の残りは主にSRCで、勝どき2020近側はSRC18・鉄骨1・欠損2、2021近側はSRC16・鉄骨1、2023近側はSRC8・欠損2。亀戸は近側SRC14・鉄骨1、遠側SRC7。RC/SRCは構造分類であり、内装・管理・サービス等の格付けではない。

勝どきでは遠側2LDK/3LDK比率70.8～85.1%、近側25.0～43.5%。遠側の建築年は全件2009・2013・2015・2016年の4種類に集中する。2015年だけで各年31/64、18/48、35/64、19/47行。これは一定の建築年代の供給が多いという証拠であり、4種類の年＝4棟、あるいは特定ブランドの取引という証拠ではない。

**勝どき4組では近遠に共通する町名がゼロ。** 現データでは距離帯と町名が完全に分かれ、町名を固定した徒歩効果は推定できない。大規模な新しい住宅、地域環境、眺望、再開発、未観測の部屋品質が混在する。観測された差の何%が築年齢、何%がブランドという数値分解は行えない。

亀戸は双方1Kが17件だが、遠側は40㎡以下28/32（87.5%）、近側21/33（63.6%）。遠側に築5年以下9/32があり、近側にはない。平均的な年齢差が小さくても分布は違う。間取り欠損は近2／遠3。町名を亀戸だけに限定すると近33・遠30行で閾値を維持し、遠側単価中央値104万円、近94.44万円、差+10.12%。大島2行を除くと結論の大きさが変わるため、元の+3.24%を安定した徒歩効果と解釈しない。

「町名×年齢帯（0–5/6–10/11–20/21–30/31+）×面積帯（≤40/>40–60/>60–80/>80）×間取り×構造」の共同セルは、勝どき4組で0、亀戸でも2セル・近14／遠4行のみ。両側30件以上の共同セルは0。条件を緩めて調整済み効果を無理に出していない。小セルの件数は重なり不足を示す監査値で、価格効果の推定値ではない。

### 3. 年内構成・反例・不確実性

同年でも四半期構成は異なる。勝どき2019のQ3は遠29/64（45.3%）、近12/38（31.6%）。2020のQ4は遠9/48（18.8%）、近16/44（36.4%）。2021のQ4は遠5/64（7.8%）、近13/46（28.3%）。2023のQ4は遠13/47（27.7%）、近15/46（32.6%）。亀戸2021のQ2は遠17/32（53.1%）、近10/33（30.3%）。各組で近遠双方30件以上の同四半期セルは0なので、年内の時期差も除去できない。

残り9組も背景として保存した。勝どき2024は近71・遠33、遠／近単価比0.714、年齢中央値近1年／遠11年に逆転する。近側71行のうち38行は2023年築。亀戸2022・2023も遠側の方が安い（比0.914、0.940）。したがって勝どきや亀戸に永続的な「遠駅プレミアム」があるとはいえない。

完全一致群フラグを持つ行は勝どき2019遠6、2021遠8、2023近2・遠2、亀戸2021遠3。全行を保持した。同じ丸め値の異なる売買や同一建物の複数住戸を区別できないので、462行を462個の独立住宅と仮定せず、独立ブートストラップや有意差の主張をしない。既存87テストの全面再実行もしていない。本補足では元14比の再現と10側別分布・80カテゴリ集計の整合性確認だけを行った。

### 4. 価格以外の建築資料による小範囲確認

公開公式資料を手動で限定確認した。以下は**地域に該当する供給が存在する／計画されたことの確認であり、匿名MLIT行との照合ではない**。広告上の「高級」等の形容詞や売出価格は判定材料から除いた。

- 三菱地所レジデンスは晴海タワーズの竣工をクロノ2013年11月、ティアロ2016年4月と記載。[事業実績](https://www.mec-r.com/service/asset/land-readjustment.html)
- 三菱地所の2025年資料は同物件の免震方式と長期優良住宅認定を記載。これらは価格以外の検証可能な属性だが、認定だけで高級と決めない。また2025年資料を2019年当時の公表情報として扱わない。[公式資料](https://www.mec.co.jp/group_news/detail/2025/02/04_mecg250204_harumibousai)
- 住友不動産の2016-02-25資料（1・4・6頁）はドゥ・トゥールの共用スパ・ラウンジ等、2015年9月竣工と当時の勝どき駅徒歩約9分を記載。**9分は今回の遠側帯外**。町名と建築年だけで遠側2015年築の行をこの建物へ割り当ててはならない。設備・交通条件も時点ごとの確認が必要。[公式竣工資料](https://www.sumitomo-rd.co.jp/uploads/20160225_release_deux_tours.pdf)
- 三井不動産レジデンシャルの2020年発表は駅直結型のパークタワー勝どき計画を示す。発表時点では2023年竣工予定であり、この資料だけで引渡し完了を確認したとはしない。高仕様供給は遠駅側だけにあるという前提も置けない。[公式発表](https://www.mfr.co.jp/company/news/2020/0721_01/)

現CSVには建物名・建物ID・丁目番地・階数・眺望・サービス・共用面積等がない。町名と建築年の一致を個票同定として使用せず、今回の建物リンク件数は0。

### 5. 仮説の判定と指標の実現可能性

区別すべき仮説は二つある。

1. **構成差**：遠側に若い／サービスの豊富な住宅が多ければ、全体の遠近価格差が縮小・逆転し得る。勝どきのデータは若さ・面積・町名の構成差を直接示し、公式資料は地域の設備付き供給の存在を示す。ただし各行の高仕様判定や集積率までは分からない。
2. **感応度の変化**：同等住宅・同等地域条件でも、高仕様住宅の集積が高いほど徒歩距離に対する価格曲線が緩くなる。これには集積の高低それぞれで近遠の住宅が必要。今回の町名の分離、小セル、建物ID欠如では識別できない。構成差があることは、この相互作用があることの証明ではない。

小規模な将来台帳は実現可能だが、現140,888行へ高級度を付与する段階ではない。仮称を**「非価格属性で定義した高仕様・サービス住宅のストック集積」**とし、以下を先に設計する。

| 要素 | 提案 | 避けること |
|---|---|---|
| 建物属性 | 竣工・住宅戸数・サービス運用・共用設備・住宅性能等を公式原資料で確認。ブランドは独立した記述項目 | 高成約価格、残差、高層、RC、大手ブランド単独による高級認定 |
| 判定規則 | 価格を見る前に複数の非価格領域と重み／閾値を決め、別の重みでも感度確認 | 今回の5逆転を説明するように規則を後付け最適化 |
| 集積の分母 | 対象町名または事前固定した範囲の住宅ストック戸数。戸数加重の該当割合と単位面積当たり戸数を区別 | 取引件数加重＝集積率とする。SOHOを住宅戸数へ混入 |
| 未確認資料 | 未確認を非該当とせず、台帳カバレッジを表示。総戸数が分かれば未分類戸数を使う上下限も提示 | 公式資料がない普通物件をゼロ点にして広告充実度を測る |
| 空間・時点 | 建物ID、範囲、竣工・設備開始日、資料公表日、取得日を別管理。現時点の施設を過去へ遡及しない | 現在の徒歩表記を2019年の徒歩に上書き |
| 自分と周囲 | 物件自身の品質と近隣集積を別変数にする。照合できれば自身の建物を近隣集積から除く | 自身の設備効果を地域の集積外部性と混同 |
| 交通代替 | シャトル、バス、車・自転車等の利用可能性は別の交通属性として時点確認 | 駅徒歩が長い＝総通勤が長い、裕福な購入者＝鉄道を使わない、と仮定 |

最初は勝どき・晴海に加えて亀戸と通常仕様の比較物件を含む小さな建物台帳が妥当。物件名が不明なMLIT行には町名レベルの環境指標までしか安全に結合できず、それを当該住戸の高級度とは呼ばない。全建物の分母が揃わなければ集積率は出さず、確認済み供給一覧とカバレッジだけを出す。

将来の検証では物件属性と駅・町名・四半期を揃え、徒歩の非線形曲線と集積の相互作用を比較する。一般的な立地価格差を示す主効果と、距離感応度の相互作用を区別する。価格基準が高いだけで同じ円の差が小さな率になることもあるため、円/㎡と対数単価の両方を明示。未使用期間・別地域で検証し、建物依存と共通支持不足に対応する。それでも観察研究だけで因果的な「弱化」を断定しない。今回この新規モデルは作成していない。

### 保存・検証

詳細はGit無視対象 `reports/location-009-walk-supplement/`：`near_far_summary.csv`、`composition.csv`、`common_support.csv`、`kameido_same_town.csv`、`other_nine_context.csv`、`protocol.json`、`source_notes.json`、`checks.json`。選択行もローカルのみ保持。既存データ／成果276ファイル、プログラム／テスト／例示入力33ファイルのSHA-256は不変。新規の提出対象は本説明と `docs/task009.md` のリンク追記だけ。Commit/Pushなし。

## English

### Conclusion and scope

The evidence supports substantial composition differences, **not a demonstrated reduction in walking-distance sensitivity caused by luxury-housing concentration**. This is a post-hoc descriptive study of five positive contrasts selected from 14 eligible station/municipality/year comparisons. Four are repeated years at Kachidoki, not four independent locations. Five out of 14 is not a Tokyo-wide probability. No model was trained or changed, and no anonymous record was linked to a named building.

Near means 0–5 minutes and far means >10–15 minutes of nearest-station access. All 14 original median ratios were reproduced. The five selected groups contain 462 records. The Japanese table gives sample sizes, unit-price medians in ¥10,000/m², area and age at transaction. Far-side premiums are 12.96%, 24.55%, 7.61%, 2.56% and 3.24%. Their IQRs overlap in every case; these ranges are dispersion, not confidence intervals.

### Composition findings

In all four Kachidoki cases, far-side homes are entirely in Harumi; near-side homes are in Kachidoki or Tsukishima. There is **zero common town support**. Far-side median ages are 4/5/6/8 years versus near-side 17/22/18/14; median areas are 55/65/62.5/65 m² versus 50/35/42.5/50. The far-side sample has more 2LDK/3LDK homes (70.8–85.1% versus 25.0–43.5%) and a higher RC share. RC/SRC describe construction, not amenities or luxury quality.

Every far-side Kachidoki record has one of four construction years: 2009, 2013, 2015 or 2016. Concentration in construction cohorts does not identify four buildings or a developer brand. Near-side age is missing in two records in each of 2020 and 2023. Missing layouts/structures remain visible in the local composition tables; percentages use all side records as denominator.

Kameido 2021 differs. Both sides have median area 25 m² and 17 one-room-with-kitchen homes, but the far side has 28/32 homes at or below 40 m² versus 21/33 near, and nine homes aged at most five versus none near. Median ages of 11 versus 12 hide distributional differences. Far-side median total price is ¥23.5m versus ¥25m near despite higher unit price. Restricting both sides to Kameido town retains 30 far and 33 near records; unit-price medians become ¥1.04m/m² versus ¥0.944444m, a 10.12% difference. The change from 3.24% shows sensitivity to two Ojima records, not a stable walking effect.

There are no shared town/age-band/area-band/layout/structure cells in the four Kachidoki cases. Kameido has only two, with 14 near and four far records; none has 30 per side. No supported adjusted effect is reported. Small-cell counts diagnose lack of overlap, not price effects.

### Timing, counterexamples and uncertainty

Quarter composition differs within the same year. For example, 2019Q3 accounts for 45.3% far versus 31.6% near at Kachidoki; 2021Q2 accounts for 53.1% far versus 30.3% near at Kameido. No within-quarter cell in the five cases has 30 records on both sides. Year matching therefore does not remove timing composition.

The other nine contrasts were retained as context. In Kachidoki 2024 the far/near median ratio reverses to 0.714; median ages are one year near and 11 far, with 38 of 71 near-side records built in 2023. Kameido ratios are below one in 2022 and 2023. A permanent far-from-station premium is unsupported.

Exact-duplicate-group flags and potential repeated buildings remain retained. Anonymous rounded records do not establish independent homes, so no IID bootstrap, significance claim or causal decomposition is made. The study does not quantify how much of a premium is explained by age, area, brand or amenities.

### Limited official building evidence

The linked official sources above establish non-price building facts or announced supply, not identities of MLIT transactions. Mitsubishi's project record lists Chrono's completion in November 2013 and Tiaro's in April 2016. Its 2025 release documents seismic isolation and long-life certification, which are independently checkable features but do not alone define luxury; a later source is not contemporaneous 2019 information.

Sumitomo's 2016-02-25 release documents shared spa/lounge facilities, September 2015 completion and approximately nine-minute Kachidoki access for Deux Tours. Nine minutes lies outside this study's far band: matching Harumi and 2015 is insufficient to assign far-side observations to that building. Mitsui's 2020 announcement describes a station-connected Park Tower Kachidoki project, with completion then planned for 2023; the announcement is not proof of realized delivery. High-specification supply cannot be assumed exclusive to farther locations. Promotional luxury adjectives and asking prices were excluded from the evidence definition.

The CSV lacks building IDs/names, precise addresses, floor, view, service and common-space details. No record linkage was attempted or asserted.

### Feasible future indicator and hypothesis test

Separate **composition** (farther samples contain different homes) from **effect modification** (comparable homes show a flatter access-price curve where high-specification stock is concentrated). Current data demonstrate the former's observable components, not the latter. There must be near and far support at multiple concentration levels to estimate an interaction.

A small building inventory is feasible; labelling all 140,888 transactions as luxury is not. Use a provisional *non-price high-specification/service housing stock concentration* measure:

- Record dated construction, dwelling counts, independently verified amenities/services and performance features; keep brand as a separate descriptor. Price, model residual, tower form, RC or brand alone must not define qualification.
- Predeclare dimensions, thresholds/weights and sensitivity checks before inspecting prices. Do not optimize the definition to explain these five reversals.
- Use dwelling stock, not observed transaction counts, as denominator. Separate qualifying dwelling share from density per area; exclude nonresidential units. Report inventory coverage and unknowns rather than treating undocumented properties as low-specification. Without a credible denominator, report an inventory instead of a concentration rate.
- Keep geographic unit, building ID, completion/service effective dates, source publication and acquisition dates. Do not backfill present-day access or amenities into historical years.
- Separate the subject building's quality from neighbourhood concentration; exclude the subject building from a surrounding-stock indicator where linkage permits. Otherwise a building's own amenity premium can masquerade as a neighbourhood effect.
- Record alternative transport separately. Longer station access need not mean longer full commute, and purchaser wealth or travel preferences cannot be inferred from price.

Begin with a modest inventory across Kachidoki/Harumi and Kameido including ordinary comparison stock. MLIT rows without building identity can at most receive a coarse town-level contextual measure, not a dwelling-level luxury label. Future evaluation should compare nonlinear walking curves and concentration interactions while controlling property, location and quarter, with held-out periods/areas, building dependence and overlap checks. Distinguish higher price levels from flatter gradients, and report both yen and log-unit-price effects. Even then an observational association is not automatically causal. No such new model was implemented here.

### Preservation

Detailed supporting tables, selected local records, protocol, source notes and checks are in ignored `reports/location-009-walk-supplement/`. All 276 pre-existing data/report hashes and 33 code/test/example hashes match. Targeted checks reproduced 14 contrasts and reconciled ten side summaries and 80 category distributions; the full 87-test review was not repeated. Only this note and a link in `docs/task009.md` are new submission changes for this supplement. No commit or push was performed.
