# Task 007 — REINS Market Activity, Seasonality & Price Bands

## 日本語

### 範囲・データ源・取得日

2026-11-08確認。出典：公益財団法人東日本不動産流通機構（東日本REINS）「Market Watch 月例速報」。[公式ホームページ](https://www.reins.or.jp/)の「マーケットデータ／ライブラリー」から各年の「データ」PDFを参照。CSV/APIがあるとは仮定していない。今回だけの限定的な4ファイル取得であり、クローラーや定期取得は実装していない。

| 月報ファイル | 公開日（表紙） | 月次表の掲載期間 |
|---|---|---|
| MW_202312data.pdf | 2024-01-12 | 2022-12～2023-12 |
| MW_202412data.pdf | 2025-01-14 | 2023-12～2024-12 |
| MW_202512data.pdf | 2026-01-13 | 2024-12～2025-12 |
| MW_202609data.pdf | 2026-10-13 | 2025-09～2026-09 |

全ファイルの取得日は2026-11-08。公式2026年一覧で月例速報が確認できた最新月は9月（10月13日公開）。10～12月をゼロとしていない。取得URL、SHA-256、公開日、取得日、ページ、住宅種類、地域粒度、ファイル版を各観測に保存する。

分析範囲は**2023-01～2026-09の45か月**。首都圏、東京都、埼玉県、千葉県、神奈川県、東京都内の5地区、および研究側で合算した23区の11地域系列。3指標、495地域月、1,485計数セルがそろい、この範囲に欠損はない。地域は階層的に重複するため、11地域を合計してはならない。

価格帯はPDFの5～7ページから**2023Q1～2026Q3の15四半期、首都圏・4都県、8区分、3指標＝1,800セル**を整理。元表のラベル（～1,000、～2,000、～3,000、～4,000、～5,000、～7,000、～10,000、10,000万円～）を保持し、境界値の包含規則を独自に補わない。総額の価格帯であり、㎡単価ではない。四半期価格帯を月次季節性の観測として使わない。固定された名目金額の境界では、市場全体の価格上昇・下落だけでも同様の住宅が隣の帯へ移る。この価格帯移行効果を除いていないため、構成比変化を需要構造の変化と直接解釈できない。

2018～2022年は未取得。2022年1月に新規登録の集計対象が変更され、媒介契約更新・登録期間延長が除外されたため、単純に長期系列へ接続できない。今回の最小版では2023年以降に限定した。

### 東京23区の定義

東京都全体を23区の代理にしない。PDFの8、12、16ページにある以下の**重複しない23区**を合算し、名称を `東京23区（5地区合算）`、粒度を `derived_23_wards` とする。

| 公式地区 | 構成区 |
|---|---|
| 都心3区 | 千代田区、中央区、港区 |
| 城東地区 | 台東区、江東区、江戸川区、墨田区、葛飾区、足立区、荒川区 |
| 城南地区 | 品川区、大田区、目黒区、世田谷区 |
| 城西地区 | 新宿区、渋谷区、杉並区、中野区 |
| 城北地区 | 文京区、豊島区、北区、板橋区、練馬区 |

各PDFの構成区名を検査し、変更時は処理を停止する。合算は件数のみで、地区平均価格を足さない。東京都との差は「東京都のうち23区以外」であり、検証なしに多摩と断定しない。今回の価格帯表に23区別の内訳はないため、**23区価格帯は未実装**。駅別、単独区別の市場需給を推定しない。

### 指標と時間・版の管理

- 成約件数：当月にREINSへ成約報告があった件数。実際の契約締結月とは限らない。
- 新規登録件数：当月の新規登録イベント。市場に初めて現れたユニーク住宅数とは限らない。
- 在庫件数：月末に登録されている在庫。月をまたいで合計してはいけない。
- 媒介物件に加え、会員の売り主・代理物件を含み、「中古」として登録されたマンションが対象。
- 価格帯の成約・新規登録は四半期累計、在庫は四半期末時点。成約価格と登録価格の分布は異なる母集団であり、直接的な値引き率や成約確率にならない。

月次の前月比・前年比は暦月を照合する。欠損をゼロ補完したり、直前の観測を前月扱いしたりしない。成約について2025年1月の登録適正化をまたぐ比較は、原数値変化を残しつつ `comparable_pct=null` と制度変更フラグを出す。同制度内でもデータ改訂や市場構成は残る。`comparable_pct` は制度境界をまたがないという機械的条件のみであり、制度変更の影響が解消された保証ではない。この留意点は価格帯の成約件数と成約を分母とする比率にも適用する。新規登録／成約、在庫／成約は記述的比率であり、販売速度、成約確率、売却所要期間ではない。

`source_vintages.csv` は全掲載版を保持し、分析は利用可能な最新掲載版を選ぶ。月次198セル、価格帯480セルの重複掲載に今回値の変更はなかった。重複掲載を重複取引と扱わない。限られた重複範囲で変更がないことは、45か月全体に改訂がなかった証明ではない。元の月報初版と同じURLでの差し替えは網羅的に保存されていない。

`--as-of YYYY-MM-DD` は月報の**公開日**以下に限定する。年末月報中の過去月を、元の月に既知だった値と仮定しない。元の初回月報の公開日・改訂履歴は未取得のため、この制約は保守的であり、当時利用できた全情報を復元するものではない。例えば2025年末時点では、2026-01-13公開の2025年12月報を使えない。取得日と公開日は別フィールド。Task 006の歴史検証へ自動連結していない。

### 結果

2026年9月（出典：東日本REINS、研究側集計）：

| 地域 | 成約報告 | 新規登録 | 月末在庫 | 成約前年比 | 新規前年比 | 在庫前年比 |
|---|---:|---:|---:|---:|---:|---:|
| 東京都 | 1,699 | 10,760 | 29,785 | -30.11% | +26.62% | +30.66% |
| 東京23区・5地区合算 | 1,385 | 9,595 | 26,207 | -30.58% | +31.73% | +36.07% |
| 首都圏 | 3,457 | 17,721 | 50,450 | -22.75% | +15.40% | +15.05% |
| 埼玉県 | 398 | 1,801 | 5,407 | -18.61% | +6.13% | +1.07% |
| 千葉県 | 447 | 1,363 | 3,998 | -6.68% | -2.57% | -8.09% |
| 神奈川県 | 913 | 3,797 | 11,260 | -15.15% | +0.93% | -0.84% |

東京都の年間成約報告は2023年19,465件、2024年20,091件、2025年26,439件。新規登録は112,862→103,598→101,708件、12月末在庫は25,793→23,227→22,921件。**2025年の成約増加を制度変更と切り離して需要増加と断定できない**。2026年9月の東京都では新規・在庫増と成約報告減が併存するが、これだけで個別住宅の売れやすさを判断できない。他県では在庫の前年比が異なり、首都圏の動きを全地域へ一般化できない。

季節性は完全な年だけを年平均100に正規化し、2023～2024年と2025年以降を分離する。2026年は未完全年なので正規化から除外。東京都は2023・2024年とも成約報告が3月最大、8月最小。2年平均の3月指数119.28（各年115.10～123.46）、8月76.996（73.05～80.95）。新規登録は3月106.75、8月89.84と成約より変動が小さい。首都圏にも春高・夏低の形が見られる。一方、東京都在庫の最大／最小月は2023年5月／12月、2024年2月／7月と一致しない。

**反復する月差の手掛かりはあるが、安定した季節法則の確立ではない。** 比較可能な変更前の完全な年は2年、変更後は1年のみ。年平均正規化では年内トレンド、営業日数、祝日、制度変更の段階的影響を除去していない。季節調整済み系列や有意性検定ではない。

東京都の「10,000万円～」価格帯：

| 指標 | 2025Q3 | 2026Q3 |
|---|---:|---:|
| 成約報告に占める割合 | 18.35%（1,196/6,516） | 19.42%（995/5,124） |
| 新規登録に占める割合 | 20.49%（5,064/24,709） | 28.00%（8,406/30,019） |
| 9月末在庫に占める割合 | 20.39%（4,647/22,795） | 30.15%（8,981/29,785） |

高額帯の登録・在庫構成比が成約構成比を上回る。品質・面積・立地の変化、登録価格と成約価格の違い、同一物件の追跡欠如があるため、割高率・販売確率・品質調整済み価格上昇を示すものではない。

### 検証・実行方法

既存の `reports/reins-007-v2` を復元・再利用し、月次PDFの全再処理はしていない。`v1` は都県のみの先行検証であり、11系列の正式な今回結果は `v2`。価格帯のみ新規に5～7ページを抽出した。

- 月次：直接抽出1,560セルをpypdfとpdfplumberで照合、さらに23区156セルを合算。都県合計156チェック、再計算できる公式前年比1,020チェックに相違なし。
- 価格帯：2,400原セル（重複掲載と2022Q4を含む）を両エンジンで照合。8帯合計、公式構成比、四都県合計を検証。300地域・期間・指標の総量のうち260を同じ版の月次表と照合し一致。
- 残る40は各月報で最初に掲載された四半期の成約・新規登録について、月次13か月表に最初の2か月がないため照合不能。成功扱いにせずJSONへ列挙。別の月報を同版と偽って埋めない。
- 原PDFの表構造と抜粋値を目視確認。両エンジン一致だけでは原PDF自体の誤りを検出できない。追加の全セル手入力照合は未実施。
- 中断前に生成した月次結果を再利用し、強化した23区構成と価格帯閾値チェックは保存済み抽出テキストにも適用した。
- `python -m unittest discover -s tests -v`：**49件成功（既存28、新規21）**。欠損、版、公開日、年またぎ、制度変更、23区構成、在庫非加算、価格帯、既存結果上書き拒否を含む。小型テスト表は合成データである。
- Task 004～006等を含む既存64成果ファイルのSHA-256一致、変更ゼロ。既存モデルや実験を再学習・上書きしていない。

Python 3.12、既存環境で追加依存を導入する場合：

```powershell
python -m pip install -e ".[reins]"
python -m unittest discover -s tests -v
```

再現用CLI（実行時は未使用の出力先を指定。ネットワーク取得はしない）：

```powershell
python -m japan_housing_liquidity_lab.reins data/raw/reins/MW_202312data.pdf data/raw/reins/MW_202412data.pdf data/raw/reins/MW_202512data.pdf data/raw/reins/MW_202609data.pdf --acquired-on 2026-11-08 --start 2023-01 --output reports/reins-007-reproduce --plots
python -m japan_housing_liquidity_lab.reins_prices --monthly-output reports/reins-007-v2 --raw data/raw/reins --output reports/reins-prices-007-reproduce
```

必要なら各コマンドに `--as-of` を追加。月次 `--end` を取得範囲外へ延長した場合、欠損はJSONに列挙され、CSVは空欄になる。

今回の成果は `reports/reins-007-v2/{monthly,selected_counts,source_vintages,annual_profiles,seasonality}.csv`、`summary.json`、`activity.png`、`seasonality.png`。価格帯は `reports/reins-prices-007-v1/{quarterly_price_bands,source_vintages}.csv` と `summary.json`。CSVはUTF-8 BOM、JSONはUTF-8。各地域の月次・季節性データを含み、画像は東京都と首都圏の比較。価格帯CSVはそのまま図表用データとなる。

### 利用条件・Task 006との関係・次の検証

公式「データの利用について」と著作権PDFを確認。引用・転載は原則として許可不要だが、**継続的な転載は事前連絡**が必要。出典を必ず明記し、加工グラフには「東日本REINSデータに基づき当研究で作成」と示す。意味を変える改変・一部地域や期間の一般化を避ける。統計資料を主たる内容とする営利販売は禁止。公式のリンク方針に従い文書の外部リンクはホームページとし、取得元の正確なURLはローカル来歴に保存する。これはデータの再配布許諾を包括的に意味しない。

原PDF・整理データ・画像はGit無視対象の `data/`、`reports/` にのみ保存。Git候補はコード、文書、合成テスト、必要最小限の研究摘要だけ。Commit/Pushは行わない。

Task 006の価格比較とは独立した「地域・報告月・公開日・指標定義付きの市場背景」として利用できる。例えば、歴史的価格比較の横に都県または23区合算の活動推移を示す。ただし現段階はCLI/CSVの独立出力にとどめ、Task 006の計算は変更していない。MLIT個票との結合、駅需給、将来の良い物件出現確率は扱わない。

次は元の月報ごとの公開日・改訂履歴を限定取得し、過去時点表示を監査する。その後、2022年境界を踏まえた長期資料、営業日・トレンド調整、制度変更後の複数年で季節性の安定性を検証する。大量取得や継続公開の前に公式利用条件を再確認・必要な連絡を行う。今回、urllibの証明書検証で取得失敗があったが、検証を無効化せずWindowsの通常TLS検証を使う公式ファイル取得へ切り替えた。価格予測・機械学習実験は追加していない。

## English

### Sources and scope

Source: East Japan REINS, *Market Watch*, accessed 2026-11-08 through the [official homepage](https://www.reins.or.jp/) and its annual library pages. Four explicitly selected official PDFs were downloaded, without a crawler or assumed CSV/API endpoint. Their filenames and cover publication dates are listed above. September 2026, published October 13, was the latest listed monthly report verified; unpublished months are not zeros.

The monthly analysis covers January 2023–September 2026: 45 months, three measures, and 11 overlapping geographic series (Greater Tokyo, four prefectures, five Tokyo ward groups, and a derived 23-ward sum), totaling 1,485 selected count cells. There are no missing cells within this scope. Never sum all 11 hierarchical regions.

Tokyo 23 wards are explicitly derived from five disjoint official groups, with all 23 member names checked against each PDF. The Japanese table above enumerates them. Tokyo prefecture is not a substitute for this geography. Only counts are summed. Price bands are available here for Greater Tokyo and four prefectures, **not the 23 wards**. No station-level inference is supported.

Price-band output covers 2023Q1–2026Q3, 15 quarters, five geographic series, eight total-price bands, and three measures: 1,800 selected cells. Official band labels are retained without inventing exact boundary inclusion rules. Contract and new-registration bands are quarterly flows; inventory bands are quarter-end stock. They are not monthly observations or unit-price bands, and must not enter monthly seasonality analysis. Fixed nominal thresholds create band migration when overall housing prices rise or fall, even for similar properties. Changes in band shares therefore cannot directly establish changes in demand structure. Contract-price and registered-price distributions represent different populations.

2018–2022 were not downloaded. The January 2022 registration-definition change excluded brokerage renewals and registration extensions, so extending the series requires a comparability review.

### Meaning, availability and methodology

Contracts count reports received during a month, not necessarily contracts signed that month. New registrations are registration events rather than distinct homes newly appearing on the market. Inventory is registered stock at month-end, never summed across months. The scope includes brokerage, members' own-sale and agency properties registered as used condominiums.

MoM/YoY calculations match actual calendar months; missing values remain missing. Contract comparisons spanning the January 2025 reporting-system correction retain raw changes but suppress the comparable-change field and flag the break. The comparable-change field only checks whether a comparison crosses the reporting boundary; it does not guarantee that reporting effects have disappeared. This caution also applies to quarterly contract price bands and ratios with contracts in their denominator. Descriptive registrations/contracts and stock/contracts ratios are not sale probabilities, marketing durations or selling speeds.

All source vintages, SHA-256 hashes, URLs, publication/acquisition dates and page references are retained. Latest available supplied vintages are selected. There were 198 monthly and 480 price-band overlapping publication cells, with no value revisions observed. These overlaps are not duplicate transactions. No differences in these limited overlaps does not establish that the full 45-month history was never revised; original monthly first releases and same-URL replacements are not fully archived.

`--as-of` filters by the **source report's publication date**, never just its reference month. Historical observations in a later year-end report are not assumed known earlier. Original first-release dates and revision histories remain unavailable, making this a conservative source-availability bound rather than a complete historical information set. Monthly and price-band commands both support this cutoff.

Complete calendar years are normalized to annual mean 100, with pre-2025 and post-2025 profiles separated. Incomplete 2026 is excluded from normalization. This removes annual level differences, not within-year trends, holidays, working-day effects or evolving reporting effects. It is neither a seasonally adjusted series nor a significance test.

### Findings

In September 2026, Tokyo prefecture recorded 1,699 contract reports, 10,760 registrations and 29,785 month-end inventory; respective YoY changes were -30.11%, +26.62%, +30.66%. The derived 23 wards recorded 1,385, 9,595 and 26,207. Greater Tokyo recorded 3,457, 17,721 and 50,450. The full regional comparison appears above: inventory increased strongly in Tokyo but declined in Chiba and slightly in Kanagawa. A capital-wide result cannot be generalized to every area.

Tokyo's annual contract reports were 19,465 in 2023, 20,091 in 2024 and 26,439 in 2025; new registrations were 112,862, 103,598 and 101,708. December inventory was 25,793, 23,227 and 22,921. The 2025 contract increase cannot be separated from reporting changes using these data alone.

Tokyo contract reports peaked in March and bottomed in August in both 2023 and 2024. Mean normalized indices across those two years were 119.28 and 77.00. Registration indices were 106.75 and 89.84, showing smaller swings. Greater Tokyo also shows a spring-high/summer-low pattern. Inventory peak/trough months differed across years, so stable inventory seasonality is not established. Only two complete pre-change years and one post-change year are available: these are exploratory recurring differences, not a fixed purchasing calendar.

For Tokyo's official “10,000万円～” total-price band, contract shares rose from 18.35% in 2025Q3 to 19.42% in 2026Q3; registration shares rose from 20.49% to 28.00%, and September inventory shares from 20.39% to 30.15%. The higher registration/stock shares do not measure overpricing, sale probability, price discounts or quality-adjusted appreciation. Property composition and lack of linked listings remain major limitations.

### Validation, use and next steps

Existing `reins-007-v2` monthly results were reused after the interruption; only previously unprocessed price-band pages were newly extracted. The earlier `v1` is the prefecture-only preliminary run. Two PDF engines agreed on all 1,560 directly extracted monthly count cells; 156 additional 23-ward cells were derived. All 156 prefecture-total checks and 1,020 recomputable published YoY checks passed. Strengthened ward-membership and price-threshold guards also passed against cached extracted text from all four reports.

The price-band engines agreed on 2,400 raw cells, including overlap and 2022Q4. Band totals, printed shares and prefecture sums passed. Of 300 source-specific region/period/metric totals, 260 matched same-vintage monthly observations. The remaining 40 flow totals could not be checked because each report's first quarter lacks its first two months in the 13-month monthly table; they are explicitly listed as unavailable, not counted as successful. Source layouts and selected observations were visually inspected. Agreement cannot detect errors already present in the official PDF, and exhaustive independent manual transcription was not performed.

The full test command above passed **49 tests: 28 existing plus 21 new**, using synthetic small fixtures. Hashes of 64 pre-existing artifacts were unchanged. Task 004–006 models, experiments and calculations were preserved. No new ML model, web interface, commit or push was introduced. An initial urllib certificate-validation failure was handled using normal Windows TLS verification; certificate checking was not disabled.

Install the optional `[reins]` dependencies in the existing Python 3.12 environment and use the reproduction commands above with fresh output directories. Existing outputs are never overwritten. UTF-8 BOM CSVs include monthly counts/changes, vintages, annual profiles and seasonal chart data; PNGs compare Tokyo and Greater Tokyo. Price-band CSV/JSON is in `reports/reins-prices-007-v1`, monthly outputs in `reports/reins-007-v2`.

Official terms generally allow attributed quotation/reproduction without individual permission, but continuous reproduction requires prior contact. Adapted charts must identify REINS as source and this project as creator. Do not distort meaning, generalize a limited period/region to the whole, or sell materials primarily consisting of their statistical data. The homepage linking policy is respected; exact retrieval URLs remain in local provenance. This is not a blanket redistribution license. Raw PDFs, full cleaned datasets and generated plots remain Git-ignored; only code, bilingual documentation, synthetic fixtures and limited research summaries are candidates for review.

These independent aggregates can provide regional background alongside Task 006, with reference month, publication date and geographic scope displayed. They are not merged with MLIT records and do not change historical opportunity calculations. Next, audit original monthly release dates/revisions through a bounded acquisition, then investigate longer comparable histories, working days, within-year trends and several post-change years before making stronger seasonal claims. Recheck reuse conditions before bulk acquisition or continuous public reproduction.
