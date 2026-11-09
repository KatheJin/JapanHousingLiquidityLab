# Task 012 Extension — 実掲載収集 / Real listing pipeline

## 日本語

### 実行済みの結果（2026-11-09）

既存のpublic_listings.py、test_public_listings.py、public_terms_review追加、依存追加を作業開始時に確認。現在のC:\GitHub\JapanHousingLiquidityLab内にあり、別Work環境からの移行は不要だった。未コミット変更を上書きせず、新規listing_pipeline.pyとテストを追加した。既存HTTPクライアントとTask 010のvalidate/replayを再利用する。合成結果を実データとして数えない。

SQLite：`data/listing-extension/listings.sqlite3`（Git無視）。実ネットワークから**31個の一意なSUUMO掲載ID、32回の成功観測**を保存した。羽村市30ID、武蔵村山市1ID。これは同じ建物・住戸の別仲介掲載を含み得る掲載ID数で、31の異なる住宅と保証しない。価格は掲載価格で成約価格ではない。

| 出所 | 成功した一覧ページ読取り（反復込み） | 発見ID | 成功一意ID | 成功観測 | エラーと状況 |
|---|---:|---:|---:|---:|---|
| SUUMO | 6回、異なるページ3つ | 31 | 31 | 32 | 初期戸型解析失敗2観測。後続実行で回復、最新成功は31ID全件 |
| HOME'S | 0 | 0 | 0 | 0 | robotsは200、利用規約ページが403。停止、回避なし |
| at home | 0 | 0 | 0 | 0 | 最初に誤った規約URLを確認し404。公式ホームのリンクで正しい規約を確認後、明示的なcrawler禁止により停止 |

一覧ページ数は流水線DBの成功記録。別途実施した少数の構造確認リクエストは含まない。サイトの表示総数を収集数と扱っていない。最終羽村市実行で一覧2ページから30IDを確認し、その時点の未取得10IDのみ詳細を取得した。当日成功済み20IDを再ダウンロードしなかった。武蔵村山市は別実行で同一IDを再確認し、価格不変イベント1件を保存した。実観測で価格低下・終了を発見したという主張はしない。

成功観測期間：2026-11-09 **05:10:38～05:21:54 JST**（DBはUTC、2026-11-08T20:10:38～20:21:54+00:00）。最終時点で稼働中の未処理キューなし。失敗・置換済み実行を監査用に残す。初期の羽村市解析はpnパラメータのみ対応していたが、実サイトのpage=2を確認して修正。件数不一致をblockedとして保持し、2ページの実データで再検証した。

31IDの最新成功観測を分母とする取得率：物件名、価格、面積、建築年、建築月、間取り、構造、行政区、町名、駅名は100%。駅徒歩分は30/31＝96.8%。残りはバス20分＋停歩2分であり、駅徒歩分へ捏造せず未知とした。推定埋めはしない。原フィールド名と抽出値はraw.field_mappingへ保持する。年・月、万円→円、面積、RC等の正規化はその値と対応する。電話、担当者、写真、広告本文、全HTMLは保存しない。

### 三つの出所のルールと開発状態

[SUUMO規約](https://cdn.p.recruit.co.jp/terms/suu-t-1003/index.html)は私的利用を超える無承諾使用、認められない商業利用、運営妨害等を制限する。今回のローカル・私的・非商業の限定的な事実フィールド試験は実施したが、公開データライセンス、広範な研究再配布や商用利用許可を得たとはしない。独立書面許諾がないことだけを開発禁止と扱っていない。robotsと規約本文ハッシュは各実行で再確認し、変更なら停止する。

[HOME'S規約](https://www.homes.co.jp/kiyaku/)について、実HTTPでは403となったためその実行を止めた。検索エンジンの表示でアクセス制限を回避したことにはしていない。Discoveryプロトタイプは独立して用意したが、実一覧・実詳細は未検証、詳細アダプターは未有効化。

[at home公式規約](https://www.athome.co.jp/help/kiyaku.html)は通常HTTPで200を取得し、第4条にcrawler/spider等による情報取得の禁止を確認した。従って実一覧収集を禁止する明示的ガードを設けた。最初の404は単なるURL誤りで、サイト全体のアクセス拒否と誤記しない。独立Discoveryプロトタイプは未検証・実行停止状態。今後提供元が許す別経路が得られればその経路を別途開発する。

### 実行と増分更新

Python 3.12、既存の依存extraを利用：

```powershell
.venv/Scripts/python.exe -m pip install -e ".[public-listings]"
.venv/Scripts/python.exe -X utf8 -m japan_housing_liquidity_lab.listing_pipeline collect --source suumo --entry https://suumo.jp/ms/chuko/tokyo/sc_hamura/ --max-pages 3 --max-details 20 --recheck-hours 24 --local-private-only
```

`--resume`でpaused/interrupted/blocked実行のページチェックポイントと未処理詳細を再開する。終了済みなら新しい増分実行になる。既に成功し再確認時間に達しないIDは詳細取得をskip。failed IDと未取得IDは次の新しい走査で対象にする。新規走査は古い未終了走査をsupersededとし、古いキューと二重に走らせない。ページ失敗の再開では完了ページを再取得しない（規約とrobotsは再確認）。ページ内容の経時変化や総数不一致なら新しい走査が必要で、過去の完全性を無理に保証しない。

1実行の上限：一覧1～20ページ、詳細1～100件、待機中タスク最大1,000、1ページで受理するリンク最大300。キュー満杯では先に詳細を処理して空きを作る。デフォルトは3ページ・20詳細で、無限巡回しない。途中で予算に達するとpausedになり次回再開できる。HTTP間隔は最低10秒＋robots指定。接続timeout20秒、リダイレクト・cookie jar・ブラウザー偽装・代理切換えなし。既存Clientを使い、公開ポータルでは即時再試行0回という保守設定にした。403/429/認証要求後は停止し、同じDBで最低24時間の再アクセス抑制。規約禁止は時間経過で自動解除しない。

これらは運営者が許す取得頻度の保証ではない。異常・規約変更・禁止を検出したら数量目標より停止を優先する。HTTPキャッシュへの全HTML保存は無効化し、個人情報の混在する本文を複製しない。増分制御はDBのID・成功時刻・永続タスクで行う。すべてのルール確認とHTTP要求はrequests表へ時刻・URL・status・耗時・エラーを保存する。

```powershell
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.listing_pipeline summary --source suumo
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.listing_pipeline search --source suumo
```

標準DBは上記パス。別DBには`--database`を指定。CLI終了コードはblocked／completed_with_errorsなら2、正常終了／予算pausedなら0。API Keyは使用しない。

### SQLiteと次のUI接続

テーブル：runs（範囲・実行状態）、jobs（永続一覧／詳細キュー）、pages/page_links（ページハッシュ・リンク・チェックポイント）、discovered（source＋掲載ID一意）、snapshots（各成功／失敗観測）、batches/events（Task 010互換の状態と変化）、requests/controls（ログと出所単位の直近通信時刻）。同一source/IDの履歴をTask 010で計算し、snapshot・batch・event・job完了を同一SQLite transactionでcommitする。失敗時も観測が成功したようにlast_seenを進めない。

first_discovered_atは一覧での発見、first_seen_atは詳細を初めて肯定確認、last_seen_atは最新の成功確認、last_check_atは失敗も含む検査時刻。first_listed_atは取得できず推定しない。異プラットフォームの住戸を自動結合しない。

**検索結果からの消失や404は終了と断定しない。** 今回の実詳細パーサーは肯定観測のみ。失敗はunknown_coverage、再取得成功で肯定状態へ戻す。Task 010の確定終了・消失／再出現機構は再利用しているが、実サイトで終了を証明する安定した根拠のアダプターは未完成。従って本番で消失日／再掲載日を自動確定できるとは主張しない。再確認成功と、本当に下架後の再掲載は違う。

将来Streamlitは以下の独立サービスを直接呼べる。今回ページの大幅変更や手入力UI拡張はしない。

```python
from pathlib import Path
from japan_housing_liquidity_lab.listing_pipeline import Store
store = Store(Path('data/listing-extension/listings.sqlite3'))
try:
    matches = store.search(source='suumo', municipality='羽村市',
                           min_price=0, max_price=60000000, limit=100)
    coverage = store.summary('suumo')
    history = store.history('suumo', 'a_source_listing_id')
    events = store.events('suumo', 'a_source_listing_id')
finally:
    store.close()
```

searchは直近の肯定確認値を返す。最新確認失敗ならstateにunknown_coverageを付けるので「今も確実に販売中」とは表示しない。結果は最大1,000件、完全率は最大1,000IDの最新成功値が分母（今回31全件）。数千IDに拡大する前にインデックス・SQL側価格検索・保存量・低負荷運用を再評価する。

### Windows Task Scheduler

タスクは今回登録していない。所有者がまず手動実行を確認した後、1日1回、重複実行しない設定で：プログラム`C:\GitHub\JapanHousingLiquidityLab\.venv\Scripts\python.exe`、開始場所`C:\GitHub\JapanHousingLiquidityLab`、引数は上のcollectコマンドの`-X utf8 -m ...`以降＋`--resume`。実行結果はDBから確認できる。24時間重查が初期値。複数の行政区は同じDBへ順番に実行し、collector.lockで同時writerを拒否する。強制終了でlockが残ったら、稼働プロセス・DBを確認してから人手で復旧する。lockを自動削除して二重実行を許可しない。SQLite WAL込みのバックアップと保持期間は運用上の検討が必要。

### 検証・未完了項目

新テストはすべて合成HTML：推奨リンク除外、URL/ID重複排除、二方式ページング、キュー上限、SQL重複抑制、再確認期日、価格変化、取得失敗で消失しないこと、プロセス中断／ページ失敗の復帰、原値マッピング、納戸戸型、悪い値のtransaction拒否を検証。実収集はその代用ではなく上記のDBに記録済み。実ブラウザーでの新UI試験は今回対象外。

数千件・3プラットフォームの目標は未達。HOME'Sとat homeは上記理由で0。実サイトの確定下架判別、異媒体本人同定、定期タスクの実登録、長期の件数・保存量監視、同時利用、商用／公開再利用許諾、完全自動の規約意味判定は未実装。API Keyも依然Pending。旧モデルの再学習、成約価格との混同、Commit/Push/クラウド配備は行わない。

最終検証：全166テスト成功、36.037秒、skipなし（今回のSQLite／Discovery試験12件を含む）。SQLite integrity_checkはok。旧303成果ハッシュ一致、ローカル374ファイルがGit無視、ステージ済み0。同一掲載IDの重要属性が変わった場合はqueryもunknown_identity／review_requiredを返し、確定掲載として扱わない。既存listings.py／pyprojectの作業開始前の変更は保持した。

## English

### Real results and source status

The pre-existing SUUMO detail pilot, its tests, public_terms_review metadata and dependency changes were found in the current workspace and preserved. No cross-work-environment migration was needed. The new pipeline reuses Task 012 HTTP and Task 010 validation/state logic, adding SQLite discovery, checkpoints, observations and query services.

The ignored database data/listing-extension/listings.sqlite3 contains **31 unique real SUUMO source listing IDs and 32 successful observations**: Hamura 30 and Musashimurayama one. These are listing IDs, not guaranteed distinct dwellings. Six successful pipeline list-page reads covered three distinct pages, excluding separate diagnostic probes. The final Hamura traversal verified two pages/30 IDs and fetched only ten previously missing details, skipping twenty successful fresh records. Musashimurayama was fetched again and produced one unchanged-price event. No real price reduction, sale or verified removal was invented.

Successful observations span 2026-11-09 05:10:38–05:21:54 JST; stored timestamps are UTC. Two early ambiguous-layout errors were preserved and subsequently recovered. Actual page=2 pagination was corrected after the count safeguard exposed the missing page. Current support covers all 31 IDs, with no active pending queue at completion. Latest-success field availability is 100% for name, price, area, construction year/month, layout, structure, municipality, town and station; station walking time is 30/31 (96.8%). Bus-plus-stop walking is left unknown as station walking. Whitelisted original labels/values and transformations remain in metadata; contacts, staff names, images, ad prose and full HTML are not retained.

SUUMO was actually collected under a limited local/private/noncommercial evaluation with robots/terms checking. This does not establish a public licence or commercial/bulk redistribution clearance. HOME'S robots succeeded but the terms endpoint returned HTTP 403, so no list/detail acquisition was attempted. At home's initial guessed terms URL returned 404; the actual link was obtained from its official homepage and returned 200. Its explicit crawler prohibition stops that source. The two independent Discovery prototypes remain unverified; their detail adapters are not enabled. Zero records are attributed to them. Lack of a separate written permission alone was not treated as a development ban.

### Running and storage

Install the existing public-listings extra and use the commands above. Collection is bounded by list/detail budgets, a persistent queue, ten-second minimum spacing and robots restrictions. --resume continues checkpoints; new runs skip successfully observed IDs until their recheck interval, while failed/new IDs remain due. Fresh discovery supersedes old unfinished queues without deleting their audit history. No infinite crawl, redirect following, proxy switching, browser impersonation or login bypass. Public-portal immediate retry count is zero; 403/429/challenges stop the run and suppress further access in the same DB for at least 24 hours. Explicit terms prohibition is not cleared by waiting.

SQLite stores runs, jobs, page/link checkpoints, unique source IDs, snapshots, Task 010 batches/events and request/control logs. Observation, state changes and job completion commit together. first_discovered_at is list discovery; first_seen_at is first successful detail confirmation; last_seen_at advances on successful presence only. Actual listing-start time stays unknown. Cross-platform similarity never merges identities automatically.

Search omission and 404 do not prove withdrawal. The live parser currently supports positive observations only; failures become unknown coverage. Although the Task 010 state engine is reused, a verified real-site termination-evidence adapter is still missing. Recovered access is not labelled a proven relisting or sale. All original failed observations remain available for quality inspection.

Store.search supports source/municipality/price filters, returns latest confirmed values with latest-check status, and caps responses at 1,000. Store.history, events and summary expose price history, source state, scope and update metadata. The code example above is the future Streamlit integration point. No large UI rewrite was made. Scaling to thousands still needs indexed SQL filtering, retention/backups, low-impact operations and repeated quality review; completeness is capped at 1,000 latest successful IDs, explicitly disclosed.

Windows Task Scheduler setup is documented above but not registered: run the virtualenv Python from the project root once daily with collect, --resume and a 24-hour recheck interval, disable overlapping runs and inspect DB results. Municipalities must run sequentially against the same DB. Inspect stale locks and running processes before manual recovery; do not blindly remove locks. Back up WAL consistently.

### Validation and remaining work

New synthetic tests exercise canonical discovery, recommendation exclusion, both pagination formats, deduplication, bounded/resumable jobs, interrupted transactions, due checks, price changes, failure abstention, field mappings and layout normalization. Real acquisitions are independently persisted as reported. The multi-thousand/multi-source target has not been achieved. Verified removal/relisting classification, cross-platform identity, live scheduling, long-term monitoring, concurrency, legal clearance for public/commercial reuse and automatic semantic terms review remain outstanding. No API key use, model fitting, commit, push or cloud deployment.

Final verification: all 166 tests passed in 36.037 seconds without skips, including 12 new Discovery/SQLite cases. SQLite integrity_check returned ok. All 303 old artifact hashes match, 374 local files are ignored, and zero files are staged. Query results retain Task 010 identity-review uncertainty as unknown_identity when critical attributes conflict under the same source ID. Pre-existing listings.py and pyproject modifications were preserved.
