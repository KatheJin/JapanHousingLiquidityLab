# Phase 4 実検索改善の検証 / Live search validation

## 日本語

2026-11-10 JST、ローカル私的評価。価格モデル・Phase 5の地域推薦契約を変更せず、長期collectorを起動/停止せず、公開配備もしていない。初期の1一覧・5詳細の試験は `reports/phase4-validation/` に保持し、本試験は別のGit無視ディレクトリ `reports/phase4-search-improvement/` に保存する。

### 通常検索の調査とアクセス境界

[世田谷区の公開一覧](https://suumo.jp/ms/chuko/tokyo/sc_setagaya/)のフォームに面積下限/上限（mb/mt）、間取り区分（md）、駅徒歩分（et）、価格上下限が存在した。築年条件cnはhidden値として確認しただけで、選択肢の意味は未検証。駅名・構造・建築年を任意のサーバーパラメータに変換していない。価格条件は使用しない。

フォーム送信先 `/jj/bukken/ichiran/JJ012FC001/` は [robots.txt](https://suumo.jp/robots.txt) に照らし既存Protego判定で拒否された。**対象エンドポイントへのHTTP送信前に停止**したので、403が返ったという意味ではない。送信・別パスへの条件移植・制限回避をせず、許可された行政区の公開一覧と、そのページに実在する次ページリンクのみを取得する。規約hash照合・robots確認・source全体10秒以上間隔・403/429抑止・共有PGロックは維持。robotsの許可だけを再利用権や公開サービスの許諾とはみなさない。

### 選別と表示

- 既定10ページ/12詳細、利用者設定上限20ページ/30詳細。全走査ページの候補を比較してから詳細予算を使う。
- カードのラベル付き専有面積、築年月、間取り、所在地、沿線・駅を取得。広告文の高価格や宣伝内容で除外しない。欠損・不明属性だけでは予備排除せず、詳細確認へ残す。カードの除外理由は数値境界と部屋数系統による。
- 厳格一致：同市区町村、面積±20%、固定建築年±10年、指定した間取り・構造。駅一致と徒歩許容幅は利用者の選択。徒歩不明は徒歩条件有効時に厳格一致から除く。
- 近似候補：厳格一致以外で、同市区町村、面積±35%、建築年±20年、同じ部屋数系統。1R/ワンルーム/1K/1DK/1LDKは同系統だが、同じ住み心地と主張しない。他駅/構造を許し、徒歩条件有効時は許容幅を5分拡張、不明は明示する。面積・築年等の必須事実が不明な詳細を無理に近似一致にしない。
- 両群は重複しない。新発見、再確認、既発見IDの初詳細、旧DB観測、失敗を区別。1時間以内の詳細を再取得しない場合も「今回再確認」にはしない。旧観測の一致は別枠・別件数。
- 発見した全ID/page_linksを保持し、予備排除は詳細取得だけに適用。広告総件数と実取得数を分け、次ページ入口・残詳細・停止理由・時刻・HTTP件数を表示する。次ページ入口1件は、残りが1ページという意味ではない。
- 15分以内の同一タスク再利用、累計予算、中断再開、完了詳細スキップを維持。25と25.0等の数値表現を正規化して重複起動を防止。既存スナップショットを更新/削除せず追記する。

### 実際の結果

| 事前に設定したケース | 一覧頁 | 発見ID | 予備候補 | 詳細成功/試行 | 今回厳格/近似 | 旧DB一致（別枠） | HTTP | execute所要秒 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 世田谷区・三軒茶屋、25㎡、2005年、1K/RC、同駅必須、徒歩制約なし | 20 | 400 | 2 | 2/2 | 1/1 | 0 | 24、全200 | 234.14 |
| 世田谷区、40㎡、1980年、1LDK、構造・同駅・徒歩制約なし | 10 | 200 | 51 | 9/10 | 9/0 | 24 | 21×200＋1×301 | 222.67 |

双方の比較対象価格は3,000万円だが、検索価格上限ではない。サイト表示件数は各ページ2,244で一致したが、取得済み件数ではない。両ケースとも一覧末尾未到達。重複する頁を含む2回の独立検索なので400+200を600個の異なる住宅とは数えない。上表のHTTPはrobots・規約・一覧・詳細を含むcollectorの値。事前のフォーム調査は別に8回のHTTP200（禁止送信先は0回）。ブラウザー原頁確認の画像等の要求はcollector件数に含まない。画面内run所要時間は231.36秒/219.89秒で、execute全体には開始/結果生成も含まれる。

厳格ケースで確認した例は25.11㎡、2012年築、1K、RC、三軒茶屋徒歩8分、4,280万円、170.45万円/㎡。2005年±10年に2012年が含まれる。3,000万円超でも保持した。近似例は30.71㎡、2004年築、1K/RC、千歳船橋徒歩7分、4,990万円、162.49万円/㎡で、面積±20%外・別駅という相違を明示した。住宅品質や割安さの判定ではない。

幅広ケースは10件目の詳細でHTTP301となり、リダイレクトを自動追跡せず停止。9件の成功結果は表示・保存し、失敗1件と未処理詳細36件、次一覧入口1件を残した。301から売却・下架を推定していない。24件の旧DB一致を9件に足して「今回33件取得」とは表示しない。

11成功詳細は、リストと詳細の共通フィールド（面積・築年・間取り・自治体・駅・徒歩分）で差異0。価格・面積・築年・間取り・構造・駅・徒歩分・自治体・URLは全11件で存在し、価格/面積の単価計算を確認。成功唯一ID 1,207→1,215、成功snapshot 1,214→1,225。今回初発見1、以前発見したIDの初詳細7、再確認3、失敗1。全原snapshot/run/job/event/batch/request行の変更0、削除0。新発見時刻・共有限速時計の通常更新は別扱い。以前からDB上runningのままの旧runを勝手に修復せず、長期collectorプロセスを起動していない。

### UI・検証・限界

実ブラウザーでフォーム送信→既存タスク再利用→厳格/近似表示→明細展開→SUUMO原ページを新タブで開くまで確認。原ページの価格・面積・建築年月・間取り・RC・徒歩8分と一致。幅広ケースの301警告と成功結果の共存、JSONダウンロードも確認し、ダウンロード実体は厳格9/近似0/旧観測24/失敗1と一致した。狭いブラウザー表示で縦積み・スクロールを確認したが、実スマートフォン端末の試験とは呼ばない。

合成HTTP/独立jhll_testを使う自動テストは、全ページ優先順位、予備排除後も発見総数維持、不明/バス表記、価格上限なし、厳格と近似の分離、旧観測除外、共有ロック、部分結果、301/503、中断再開を検証。最終完全テストは **220件成功・skip 0（102.262秒）**。按需検索関連17件を含む。結果はローカル `all-tests.txt` に記録した。

現在は自治体一覧の掲載順に依存する部分検索であり、網羅的な同駅検索ではない。駅の公式公開ランディングリンクは原詳細で確認できたが、この版では駅ID対応・地域境界検証・別経路の取得を追加していない。今後その公開範囲を個別に検証する余地はあるが、禁止フォームの代替送信はしない。広告IDの重複住宅統合、価格査定、Phase 5推薦、クラウド公開、認証は本変更の対象外。

## English

Local/private validation on 2026-11-10 JST. Existing price models, Phase 5 contract, old research and collector history are retained. No long collector was started/stopped, no database reset, commit, push or deployment. Initial one-page/five-detail evidence remains under `reports/phase4-validation/`; this follow-up uses the separately ignored `reports/phase4-search-improvement/`.

The normal municipality page exposes area bounds (mb/mt), layout category (md), walking limit (et) and price bounds. Construction-age cn was observed only as a hidden value; its option semantics are not verified. No invented station/structure/year parameters are used. The form destination `/jj/bukken/ichiran/JJ012FC001/` is disallowed by the existing robots evaluator: it stopped **before requesting the endpoint**, not after an HTTP403. No alternate-path parameter workaround is attempted. Only permitted municipality pages and observed next links are used, retaining terms checks, robots, global ten-second spacing, cooldowns and both PostgreSQL coordination locks.

Default budgets are 10 pages/12 details, configurable to 20/30. Labelled list facts conservatively screen area, construction year and room-count family; unknown facts remain candidates. Candidates across all scanned pages compete for the detail budget. Asking price is never a cap. Strict matches use the same municipality, area ±20%, construction year ±10, supplied exact layout/structure and optional station/walking requirements. Disjoint alternatives allow area ±35%, year ±20, the same room-count family, other stations/structures, and optionally five more walking-tolerance minutes with unknowns labelled. Studio/1K/1DK/1LDK share a screening family, not equivalent utility or quality.

New discoveries, reconfirmations, first details of previously discovered IDs, old database observations and failures are distinguished. Cached details under one hour may avoid another request but never count as a new confirmation. Every discovered ID is retained even if its card excludes it from detail fetching. Tasks remain bounded, persistent and resumable; numeric input spellings normalize for deduplication. Old snapshots append only; failures never imply withdrawal.

| Predetermined case | Pages | Discovered IDs | Candidates | Successful/attempted details | Current strict/approximate | Separate old matches | Collector HTTP | Execute seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Setagaya/Sangenjaya, 25m², 2005, 1K/RC, same station, no walking limit | 20 | 400 | 2 | 2/2 | 1/1 | 0 | 24, all200 | 234.14 |
| Setagaya, 40m², 1980, 1LDK, no structure/station/walking limit | 10 | 200 | 51 | 9/10 | 9/0 | 24 | 21×200 + 1×301 | 222.67 |

Both subjects ask JPY30m, without capping result prices. The site advertised 2,244 records, not the number collected. Both traversals remain partial; overlapping pages cannot be added as unique homes. Collector counts include robots/terms/list/detail requests; separate form inspection used eight HTTP200 requests and zero requests to the disallowed destination. Browser assets are outside collector counts. Stored run elapsed times are 231.36/219.89 seconds, while execute durations also include setup/results.

The strict example is 25.11m²/2012/1K/RC/Sangenjaya walking8 minutes, JPY42.8m (JPY1.7045m/m²). It meets the explicitly defined ±10-year rule and is retained above the subject price. The alternative is 30.71m²/2004/1K/RC/Chitose-funabashi walking7 minutes, JPY49.9m; its area exceeds strict tolerance and the station differs. Neither is a purchase recommendation. In the broader case the tenth detail returned301, stopping without redirect following. Nine successes survive, with one failed detail, 36 pending details and one next-page entry. The 24 older matching observations are not presented as fresh results or added to nine.

All eleven successful details agree with their list facts on shared fields; price, area, year, layout, structure, station, walk, municipality and URL are present in all eleven. Unit prices were recalculated. Successful unique IDs increase 1,207→1,215 and successful snapshots 1,214→1,225: one newly discovered ID, seven previously discovered IDs receiving their first detail, three reconfirmations and one failure. Every pre-existing snapshot/run/job/event/batch/request row is unchanged and retained. The legacy stale running row is left untouched.

Real-browser checks covered form submission/reuse, disjoint groups, expanded details, opening the original SUUMO link, the 301 warning alongside partial successes, and actual JSON download. The downloaded JSON contains 9 strict/0 approximate/24 older matches/1 failure. Narrow-window layout was inspected, not a physical smartphone test. Automated synthetic HTTP and dedicated PostgreSQL tests cover screening, cross-page priority, unknown facts, price independence, deduplication, old observations, source coordination and interrupted/error recovery; the final full suite passed **220 tests, zero skips, in 102.262 seconds**, including 17 on-demand tests, with output in local `all-tests.txt`.

This is still a bounded municipal search biased by the site's ordering, not exhaustive station inventory. An official station landing link was observed on the verified detail page, but station-ID mapping, boundary validation and additional route collection are not implemented here. Listings are not verified unique homes or transactions. Region recommendations, authentication, public licensing and cloud deployment remain outside this change.
