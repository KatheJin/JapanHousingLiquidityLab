# Phase 4 限定実掲載検索・Phase 5境界 / Demand Search and Area Contract

## 日本語

Phase 1–2 commit aa36f94、Phase 3 commit 5d89257をorigin/mainへ提出後に開発。ここからのコードは未commit・未push。長期収集器の起動停止や既存研究モデルの更新は行わない。

### 利用方法

Streamlitの「歴史成約分析」と「現在の類似掲載」はsession内housing_subjectを共有。後者だけでもフォーム入力して実行でき、JSON/CSVは不要。掲載総額は比較中の対象価格で、SUUMO価格の上限条件ではない。同市区町村内を検索し、同駅限定を解除できる。面積±20%、築年差±10年、指定間取り/構造は一致。徒歩±5分は任意、不明は有効時だけ除外。駅名は正規化文字列と自治体で識別し、路線駅IDは未対応。

既定予算は10一覧・12詳細、画面で最大20一覧・30詳細を設定可能。ラベル付きカードの面積・築年・間取りで予備選別し、全走査ページの候補から厳格条件に近いものを先に取得。不明属性だけでは予備排除しない。厳格一致と近似候補を別集計し、旧DB観測は今回の一致数に含めない。1時間以内の成功観測は再取得を省く場合があるが、旧観測と表示する。0一致は0在庫ではない。[改善後の実検索・制約・検証](phase4-search-validation.md)を参照。

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

既存の私有PG設定をサーバーprocessで読み、ブラウザーへ資格情報を返さない。ローカル私的利用だけで、公開サービス利用許諾・一般公開の権限/利用者隔離・運用認証は未整備。公開配備しない。

### 構造と失敗処理

on_demand.create(query,max_pages=10,max_details=12,strict_station=True,destination=None)がcollection_commandsへ保存する。新schema/frameworkは不要。createは短いtransaction/advisory lockで同一リクエストをまとめ、未処理20件上限。1processのexecutorは1worker。同一taskのfuture重複投入も抑止。

executeは既存planner lock12012002を先に取り、PostgresStoreのwriter lock12012001も取得。長期workerが使用中ならHTTPなしでwaitingとなり、無制限に待機/再試行しない。ユーザーの「再開」で再点検する。共有PublicHTTP、robots/規約hash、10秒以上の間隔、全source共通controlsと24時間の403/429/challenge抑止を維持。Captcha/認証/規制を迂回しない。

listing_pipeline.runの追加引数isolated_scopeだけが按需経路を分ける。既存長期runnerの既定挙動は保持。按需taskは独立scopeで、他runのrunning/paused/pendingを変更しない。累計page/detail予算を差し引き、完了jobを再取得しない。既存snapshotは追加のみ。partial/failedを消失・成約の証拠にしない。サーバー再起動後もPG内task/jobsから再開可能だが、自動daemon/定期実行は追加していない。

既知の完了/部分結果は15分間同一要求を再利用する。これは一瞬後の在庫保証ではない。再開は中断・失敗状態の同一taskだけで、使い切った予算を無制限に拡張しない。未設定の行政区entryは、共用lock下の公式東京都indexから検証する。現在の候補計画は23区と狛江で、都内全市区町村対応とは主張しない。

### Phase 5 インターフェース設計のみ

入力：subject（面積・固定建築年・間取り・構造・徒歩条件）、target_location（municipality/station）、reference_quarter、candidate_locations。候補間で同じ住宅属性、同じ時点、同じ欠損処理を用いる。

推定対象：p_ref(subject,location,t)。比較差はp_ref(candidate)/p_ref(target)−1。生の平均価格や回帰係数の距離は類似度にしない。地区の係数差を因果的な品質差とも呼ばない。

候補の出力契約：location、reference_unit_price_jpy_m2、relative_gap_pct、support_n、support_period、uncertainty（方法・範囲・校正状態）、model_version、availability、reasons。支持や共通属性の外挿/時点検証が不足する場合は価格とgapをnull、availability=unavailableとする。現時点で候補価格・順位は生成しない。

初回分析はモデル・支持度だけで地域を比較し、推薦地域全部をcrawlしない。利用者が地域をクリックした時だけcreate(subject,destination={municipality,station})へ渡す。このcreate境界は実装済みだが、候補生成・順位・クリックUIは未実装。目的地を変えても面積/建築年/間取り等を維持し、元入力もtaskへ保存する。

### 初期版の実行記録（改善前・記録を保持）

完全回帰211件成功、skip 0、94.908秒。追加8件はmock HTTPを使ったtask/PG/画面試験。価格を高くしても除外しないこと、共有入力、dedup、中央lock、partial、503後の同じtask復帰、中断後の同じrun/完了詳細スキップを確認。

実行日は2026-11-10（JST）。世田谷区、三軒茶屋25㎡・2005年・1K/RCを対象に、同駅限定は解除して1一覧・5詳細で実取得。robots・規約・一覧・詳細の計8要求は全てHTTP200。発見20 ID、5詳細成功、残り16 jobs（詳細15＋次一覧1）。部分結果で、25㎡/2005年/1Kの条件一致は0。取得した詳細は1962～1972年築、29.48～38.13㎡、1DK/1LDKで、指定条件外だった。別住宅を混ぜて成功結果を作らず、0在庫とも呼ばない。

5件は既知出所IDの再観測。唯一IDは1,207のまま、成功snapshotは1,209→1,214。価格・面積・建築年・駅・徒歩分・間取り・構造・URL・観測時刻を全5件で保持。全raw価格/面積は正数。原snapshot/batch/event/request行と長期runs/jobsは完全保存。新しいrun1、jobs22、request8、snapshot5等の追加だけ（discoveredのlast_discovered_atと共用限速時刻は通常更新）。実データ・生の結果・ログはreports/phase4-validationとPGにのみ保持しGit無視。

**残る制約**：現在は行政区一覧の一部を確認し、駅・間取りで取得順を優先する方式。SUUMO検索フォームの住宅条件をserver側へ送って網羅する実装ではない。狭い条件や近年築では最初の一頁に一致がなくても不思議ではない。当初のservice上限3/30・画面1/5は、改善版でservice/画面とも最大20/30・既定10/12に変更した。全候補を見つけたという主張はしない。住宅の階・内装・向き・管理品質の比較、掲載IDから実住宅への統合、推薦UI、Web認証、クラウド配備は未実装。

## English

Phase 4 was developed only after pushing Phase 1–2 (aa36f94) and Phase 3 (5d89257). New code remains uncommitted. Historical and current-listing pages share a session property input; current search also accepts its own form. Asking price is never a listing-price cap. Filters use area ±20%, construction-year difference ±10, optional exact layout/structure/station and optional walking tolerance.

The updated default budget is ten list pages and twelve details, configurable up to twenty/thirty. Labelled area/year/layout fields screen cards conservatively; unknown fields are retained. All scanned pages compete for the detail budget. Strict and approximate current matches are separate, and old database observations never count as reconfirmed. Successful details within one hour may be reused as explicitly labelled old observations. See [updated validation](phase4-search-validation.md). Results describe a bounded slice, not total inventory; zero matches is not zero stock. Tasks, progress and queues persist in PostgreSQL, observations append, and no disappearance is inferred.

Existing HTTP/parser/robots/terms/cooldown/ten-second throttle are reused. Admission deduplicates requests with a 20-pending cap; the process executor has one worker, while planner and writer advisory locks coordinate every process and the long collector. Busy sources issue no HTTP and require an explicit retry. Isolated scopes leave old long-running states/queues alone. Cumulative budgets and completed jobs survive interruptions. Finished/partial requests are reused for 15 minutes. No background daemon, new framework or schema migration is introduced.

Local private use only; public-service licensing, authentication and robust multi-user authorization remain deployment blockers. There is no public deployment.

Phase 5 is a contract, not a recommendation implementation: compare standardized p_ref(subject,location,t) under identical housing attributes/time. Report candidate reference unit price, target-relative gap, support, period, uncertainty/calibration, model version and availability. Raw area means or coefficient similarity are not the estimand. Unsupported outputs remain null/unavailable. Initial recommendations must not crawl all regions. Only a later user click calls create(subject,destination={municipality,station}); that service boundary exists, but candidate generation/ranking/click UI do not.

Initial-version record, retained for provenance: the full suite passed 211 tests with zero skips in 94.908 seconds. Eight new mock-HTTP/PG/UI tests exercise deduplication, high prices remaining eligible, shared input, global locks, partial results, public retry and interrupted-run continuation.

The actual Setagaya query used the 25m²/2005/1K/RC subject with station matching disabled, one list and five details. All eight requests (robots, terms, list, details) returned 200. It discovered 20 IDs and successfully parsed five details, leaving 16 jobs. None matched: these observed homes were built in 1962–72 with 29.48–38.13m² and 1DK/1LDK layouts. This is an honest partial zero-match result, not zero inventory. No synthetic or unrelated matched homes were substituted.

The five observations revisit existing source IDs: unique IDs remain 1,207 and successful snapshots grow 1,209→1,214. All five retain price, area, year, station, walk, layout, structure, URL and observation time. Old immutable observations/events/requests and long runs/jobs remain exact. New data/logs stay ignored. This version checks a bounded slice of municipality results and prioritizes station/layout text; it does not yet submit property filters through SUUMO's server-side search form. That initial three/thirty service cap and one/five UI budget were replaced with twenty/thirty caps and ten/twelve defaults in the follow-up. No exhaustive coverage, recommendation ranking, building identity resolution, public authorization or deployment is claimed.
