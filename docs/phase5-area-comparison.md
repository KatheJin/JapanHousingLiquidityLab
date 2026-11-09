# Phase 5 — 統一住宅比較と価格水準の近い地域 / Unified comparison and area research

初回Phase 5検証の記録です。追加の候補区分・最終機能確認は[新版MVP最終確認](mvp-final-review.md)を参照。 / This preserves the initial Phase 5 checkpoint; see the [final MVP review](mvp-final-review.md) for subsequent grouping and acceptance checks.

## 日本語

2026-11-10検証。Phase 4は `e984566aa95a524fb4bcad286a8c9dd3966a0589` でorigin/mainへPush済み。以下のPhase 5変更は未Commit・未Push、非公開のローカル検証のみ。

### 利用手順と実装範囲

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
.\.venv\Scripts\python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

既存ローカルPostgreSQLと私有MLITデータ・モデルを利用する。稼働中のStreamlitがある場合は重複起動せず、既存ページを更新する。データのコピー・公開、長期collectorの起動、モデル再学習は不要。

既定の「住宅比較（統合）」で住宅を一度入力し「この住宅で歴史と地域を比較」を押す。歴史明細・研究用地区比較は取得済みデータだけで計算する。現在掲載は利用範囲を確認し、同地域または候補地域の検索ボタンを明示的に押す。初回の地域比較で全候補をクロールしない。価格が入力予算を超えても掲載を除外しない。

三つの結果は独立して失敗を表示する。歴史調整やモデルが利用不可でも、歴史原価格や実掲載検索は利用可能。合成結果への自動切替はない。入力変更は再比較まで反映されない。候補クリックは元住宅の入力を変更せず、市区町村・駅だけを検索先に切り替え、元町名は持ち越さない。

検索中の確認済み部分結果、厳格一致、近似候補、旧観測、アクセス失敗、ページ数・HTTP数・日時を分離する。状態は「状態と結果を更新」で明示更新する。画面を閉じるだけではタスクは停止しない。「検索を一時停止／待機を解除」は通信間で停止し、応答待ちの通信はタイムアウトまで待つ。再比較も既存タスクを自動停止しないため、必要なら先に一時停止する。詳細はPhase 4文書を参照。

### 同じ住宅属性で比較する方法

市場単位は市区町村＋最近駅。町域は将来用の空欄を保持する。建築年・面積・間取り・構造・正確な徒歩分を固定し、比較期を2026Q2に統一する。2005年築なら全市場で築21年。候補ごとに変える入力は市区町村と駅のみ。旧模型の実予測単価を比較し、回帰係数や原価格平均の距離を使わない。

`p_m(a,x,t)=exp(f_m(a,x,t))`、研究上の差は `100*(p_m(candidate,x,t)/p_m(target,x,t)-1)`。`x` は固定住宅属性、`a` は市区町村＋駅。Ridgeの加法的な仕様は地区固有の属性効果を十分表せない可能性がある。差を立地・通勤の因果効果、同品質の保証、売買推奨として解釈しない。

| 凍結済みモデル | 学習範囲 | 今回の用途 |
|---|---|---|
| history_with_time | 2023Q1–2026Q2、線形四半期特徴 | 2026Q2の研究用主参照 |
| all_history_no_time | 2023Q1–2026Q2、時間特徴なし | 期間を混ぜた参照値による感度検査 |
| recent_no_time | 2025Q3–2026Q2、時間特徴なし | 直近期参照値による感度検査 |

後二者は2026Q2の独立した時点推定ではない。三モデル間の範囲は予測区間ではない。Task 004 HGBは古い学習期から2026Q2への未検証外挿になるため今回は用いない。Phase 1–2の3/5/8年実験には予測・指標が残るが学習済みモデルがなく、地域順位の再計算は行わない。モデル追加・再学習・旧成果の置換はしていない。

### 支持度、誤差、保留条件

140,888件の2018Q1–2026Q2を履歴として読むが、地域候補の支持度は既存模型の2023Q1–2026Q2だけで計算する。2018–2022の件数は別表示し、学習範囲の裏付けにしない。データとモデルのSHA-256、公開可能時点、モデルバージョンを研究JSONに保持。現在のデータ版が利用可能になる2026-11-08より前の参考日は受け付けず、当時公開版のバックテストとも呼ばない。

最低条件は市場全体30件以上、さらに面積±20%、比較期房齢±10年、同一間取り・構造、既知の徒歩±5分をすべて満たす共同支持10件以上。対象と候補に同じ条件を使う。面積の既存中心98%範囲、欠損、モデルで未知・少数カテゴリにまとめられた行政区・駅・間取り・構造も点検する。閾値達成は信頼性を保証しない。直近2025Q3以降の共同支持も別記し、10件未満・0件を明示する。歴史明細の106件とは期間・徒歩・房齢の支持条件が異なる。

2025年の既存開発用予測は2023–2024学習（recentは2024）による時間外予測で、駅・行政区・予測価格帯の誤差を診断として再利用する。現在の2026Q2まで学習したモデルの訓練残差を独立性能には使わない。ただし旧予測の誤差は現行版の校正でも地区間差の検証でもなく、2025年は既に参照済みの探索的開発評価。価格帯は予測単価50万・100万・150万円/㎡で区分し、実価格上位帯の精度と混同しない。Phase 2の実価格150万円/㎡以上の系統的過小予測も注意情報に保持する。

各モデルの価格差が小さい上位10市場の和集合を研究候補にし、三モデルとも±10%以内か否かの粗い区分、その後は行政区・駅名順に表示する。推奨順位は表示しない。順位の変動幅・上位集合の一致度は研究詳細で保存する。正式な `reference_unit_price_jpy_m2` と `relative_gap_pct` は全候補でnull。研究値は `diagnostic_*` に隔離。対象支持不足なら `unavailable` と空候補、支持があっても `research_only` に留める。

### 実データ結果

三軒茶屋・世田谷区、25㎡、2005年築、1K、RC、徒歩10分、3,000万円、参考日2026-11-10。履歴明細は従来通り106件（2018–2022:66、2023–2026:40）。地域比較の対象共同支持は30件、直近3件。847市場のうち対象を含む146市場が基本条件を通過、他145市場を比較。三モデルの前10市場の和集合18、三者共通3、Jaccard16.7%。これは精度や購入確率ではない。

| 市場 | 時間項あり研究単価 万円/㎡ | 対象との差 | 三モデルでの差の範囲 | 共同支持 / 直近 |
|---|---:|---:|---:|---:|
| 世田谷区・三軒茶屋 | 142.66 | 基準 | 基準 | 30 / 3 |
| 中央区・茅場町 | 136.37 | −4.41% | −4.41～+4.02% | 10 / 4 |
| 渋谷区・初台 | 142.58 | −0.06% | −0.06～+8.90% | 26 / 10 |
| 中央区・勝どき | 146.23 | +2.50% | +2.50～+16.87% | 14 / 6 |

例示順であり推薦順位ではない。対象の他モデル単価は全期間時間なし121.86、近期時間なし126.89万円/㎡。初台のモデル内順位の振幅27、勝どき44という不安定性がある。数値が近いだけで同じ市場価格水準とは確定できない。

対象駅の既存2025開発予測は69件、MAE21.56万円/㎡、MAPE19.35%、平均符号付き誤差−3.75万円/㎡。初台27件のMAE23.56万円/㎡、勝どき163件はMAE49.96万円/㎡・平均誤差−46.95万円/㎡。いずれも新しい地区差の独立検証ではない。二子玉川70㎡・2005年・3LDK・RC・徒歩10分は市場全体125件でも共同支持6件、直近1件のため利用不可になる。

### ブラウザから候補を検索した検証

上記住宅を一度入力し、歴史106件と研究候補を確認してから「中央区 / 茅場町」を選び2一覧・2詳細上限で検索。原入力は世田谷区・三軒茶屋のまま保持された。2一覧で40出所IDを発見、属性予備候補2件の詳細を再確認。厳格一致0、近似2、失敗0。HTTP6回（robots・規約・2一覧・2詳細）はすべて200、実行51.9秒。観測終了2026-11-10 04:33:47 JST（ログはUTC）。未確認の次ページがあり部分検索。

2件は既存IDの新しい観測で、新規住宅発見とは数えない。価格は5,298万円・27.9㎡・2005年・ワンルーム・SRC・三越前徒歩2分と、7,480万円・33.04㎡・2021年・1LDK・RC・八丁堀徒歩3分。どちらも元条件との差を列挙し、茅場町同駅の厳格一致に数えていない。取得済みHTMLの価格・面積等を表示、明細展開と原URLリンクをブラウザで確認。全中央区の調査・在庫ゼロ・価格の同等性は主張しない。

検証記録はGit無視の `reports/phase5-validation/`。`area-small-unit.json`、`area-family-unit.json`、`candidate-browser-search.json`、全テスト記録を保存。Phase 4の元の厳格1・広い条件9の実記録は別ファイルのまま保持。

### 試験・保全・残課題

全242テスト成功（135.016秒、skipなし）。新規18件は地区比較10、統合画面7、候補地区切替1。PostgreSQLは独立 `jhll_test`、実収集は既存本番DBを使用。実ブラウザで共通入力、106件、候補選択、実検索、部分結果、近似の展開・原リンクを確認。今回スマートフォン実機や外部公開は検証していない。

元の研究・モデル・実験303ファイルとSQLiteのハッシュは不変、旧DBの観測・イベント・ログ保持も確認済み。公開候補124ファイルの実秘密値スキャン、私有ファイルのGit無視を確認し、混入なし・ステージ済み0件。SUUMOは成功出所ID1,215、成功観測1,227件（今回2観測増）、共有ロック残留なし。Phase 5の出力や実掲載記録はCommit対象外。初回モデル読込は数秒、キャッシュは読取専用データ・モデルだけ。入力・結果は会話セッション単位、取得タスクは共有ローカルDBに保持する。タスクのユーザー別認可、外部公開・再分配許諾、持続保存の運用は今後の作業であり、インターネット公開可能な権限分離とは主張しない。

次の検証は地区間差そのものの時間外評価、価格帯と共同属性支持の改善、モデル定義・学習窓に対する候補の安定性、MLIT駅名と掲載側駅IDの検証。証拠が揃うまで研究候補を正式推薦に昇格しない。歴史低価格比率は将来の購入確率ではない。

### Pythonインターフェース

`area_comparison.load(root)` は既存資源と誤差証拠を読み、`compare(resources, query)` が元の住宅入力と共通属性、基準四半期、出所、対象支持、候補、研究誤差、保留理由を返す。ネットワーク・fit・DB書込はない。`decision_page.start_search(query, destination, pages=..., details=..., consent=True)` だけがPhase 4を起動。`destination` は `municipality` と `station`。町域は今後の拡張用。既存 `on_demand.progress` が新鮮度・進捗を返し、`render_task` が同じ条件表示を再利用する。

## English

Validated on 2026-11-10. Phase 4 was committed and pushed as `e984566aa95a524fb4bcad286a8c9dd3966a0589`. Phase 5 remains uncommitted, local only.

The default **住宅比較（統合）** page connects one property form to historical records, bounded same-area SUUMO search and research-only alternative markets. Use the existing local Streamlit command above and private artifacts. History and area analysis make no HTTP requests. A candidate is collected only after its explicit search button and local-use acknowledgement. Selecting an area preserves the original subject, changing only the search municipality/station and clearing the original town. Model or historical-adjustment failure does not disable other panels; no synthetic fallback is used. Existing pages remain available.

The market unit is municipality plus station, with a reserved town field. Area, construction year, layout, structure, exact walking minutes and reference period are identical across all predictions. A 2005 building is 21 years old at 2026Q2. Comparisons use predicted unit prices, `exp(f(area, property, time))`, and their relative differences, rather than coefficient distances or raw averages. Additive Ridge may not capture area-specific attribute interactions. No causal or equal-quality claim is made.

Three frozen Task 005 Ridge artifacts are reused: full 2023Q1–2026Q2 without time, recent 2025Q3–2026Q2 without time, and full history with a linear quarter feature. The timed model at 2026Q2 is the primary diagnostic; untimed fits are pooled-period sensitivity references, not independently validated 2026Q2 prices. Their spread is not a prediction interval. Task 004 HGB would extrapolate beyond its old training period. Phase 1–2 retained predictions/metrics but not fitted 3/5/8-year artifacts, so those ranking comparisons are not recomputed. No new fitting or model replacement occurs.

All 140,888 historical records are loaded, but support gates use only the 55,652-record 2023Q1–2026Q2 model period. Earlier records are counted separately. Both target and candidates require at least 30 market records and 10 jointly compatible records after area±20%, reference age±10 years, exact layout/structure and known walk±5 minutes filters. Central 98% area bounds and unseen/pooled categories are checked. Thresholds do not establish reliability. Recent joint support below 10 or 0 is explicitly disclosed. Data/model hashes, version and current-vintage availability are retained; reference dates before 2026-11-08 are refused. This is not a historical publication-vintage backtest.

Error diagnostics reuse the 2025 development predictions trained on 2023–24 (recent: 2024), never current-fit training residuals. Station, municipality and predicted-price-band errors are included; the bands are 0.5/1.0/1.5 million JPY/m², not actual high-tail accuracy. Phase 2 actual high-price underprediction remains a warning. These are previously inspected exploratory holdouts from prior fits, not current calibration or independent tests of inter-area contrasts.

The union of each model's closest 10 supported markets is retained. Display order uses broad all-model±10% proximity groups then names; precise diagnostic ranks appear only in research details. Formal price/gap fields remain null for every candidate. Values are isolated in diagnostic fields, with `research_only` status. Insufficient target support returns `unavailable` and no candidates.

The real Sangenjaya 25 m²/2005/1K/RC/walk 10 example preserves 106 historical records (66 older/40 existing-period). Joint model-period support is 30, recent 3. Of 847 markets, 146 including the target pass basic gates. The 145 alternatives produce 18 research candidates, with only 3 common to all model top 10 sets (Jaccard 16.7%). Primary target diagnostic is 1,426,590.55 JPY/m²; untimed references are 1,218,630.51 and 1,268,875.40. Hatsudai's timed gap is −0.057% but recent-fit gap +8.90%, rank spread 27; Kachidoki's +2.50% becomes +16.87%, spread 44. These do not justify a reliable ranking. The table above is illustrative, not ordered recommendations.

Sangenjaya's prior 2025 station holdout has 69 records, MAE 215,577.95 JPY/m², MAPE 19.35%, signed bias −37,523.28. Hatsudai has 27 records, MAE 235,574.06; Kachidoki 163 records, MAE 499,646.47 and bias −469,539.25. None measures current inter-area contrast accuracy. Futakotamagawa 70 m²/2005/3LDK/RC/walk 10 has 125 market rows but only 6 joint/recent 1 and correctly abstains.

Actual browser flow selected Chuo/Kayabacho from the Sangenjaya subject with a 2-list/2-detail budget. It discovered 40 source IDs, rechecked 2 eligible details, and returned 0 strict/2 approximate/0 failed. Six requests (robots, terms, two lists, two details) all returned 200; execution 51.9 seconds, completed 2026-11-10 04:33:47 JST. A next page remains, so results are partial. The two existing IDs gained observations, not new dwelling counts. Their prices were 52.98 million JPY/27.9 m²/2005/studio/SRC/Mitsukoshimae 2 min and 74.8 million/33.04 m²/2021/1LDK/RC/Hatchobori 3 min. Differences are visible; neither is counted as the requested same-station strict match. Browser result expansion and original URL controls were verified. The original Phase 4 strict 1/broad 9 evidence remains separate and unchanged.

The complete suite passed 242 tests in 135.016 seconds with no skips, including the isolated PostgreSQL test database. Added coverage: 10 area, 7 unified UI, 1 destination-preservation test. Browser acceptance used real local data, not only AppTest; no physical-mobile or public-cloud acceptance is claimed. Detailed JSON and test logs stay ignored under `reports/phase5-validation/`. The 303 old artifact hashes and frozen SQLite hash are unchanged; prior database observations, events and logs are preserved. All 124 public candidate files passed the actual-secret scan; private paths remain ignored and the staging area is empty. PostgreSQL retains 1,215 successful SUUMO source IDs and 1,227 successful observations (two added here), with no remaining collection locks. Read-only data/models may be cached; user forms/results are session-scoped. Shared local search tasks are persistent, not a completed multi-user authorization system. Public distribution, cloud access controls and persistent-storage operations remain separate work.

The read-only API is `area_comparison.load(root)` then `compare(resources, query)`. Only `decision_page.start_search(query, destination, pages=..., details=..., consent=True)` starts Phase 4 network collection. Destination contains municipality/station. Existing `on_demand.progress` and `render_task` provide coverage, freshness, confirmed partial observations, pause and explicit refresh. Closing a page or submitting a new comparison does not stop a running task; pause it first if desired. No long collector is started, no original observations are overwritten, and no arbitrary historical low-price proportion is converted into a future purchase probability.
