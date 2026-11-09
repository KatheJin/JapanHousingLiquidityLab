# 東京都・実掲載の継続収集 / Tokyo Real Listing Expansion

## 日本語

目標は、PGに成功観測を持つ一意なSUUMO出所掲載IDを3,000件以上にすること。広告総数・発見URL・観測snapshot数は目標件数と区別する。同一住戸の仲介違いを含み得るので、異なる住宅3,000戸という意味ではない。既存33 ID・成功35 snapshot・失敗2 snapshot・全履歴は保存し、事前custom dumpも作成した。HOME'Sへの要求は行わない。

### 収集計画・再開

まず既存の狛江runを--resumeで続行。その後、通常のPublicHTTP（robots・規約hash・10秒以上間隔・timeout・redirectなし）でSUUMOの[東京都入口](https://suumo.jp/ms/chuko/tokyo/)を一度読み、23区の正式なリンクを抽出する。全23区が揃わない場合は停止し、推測URLで埋めない。狛江＋23区のplanはGit無視のdata/tokyo-collection/plan.jsonへ保存。

狛江の未完了走査を優先し、その後23区のうち成功IDが少ない未完了区から有界batchを順次処理する。同数時は行政区順。特定の高額物件だけを選ぶ抽出ではないが、サイト表示順と部分走査の偏りは残る。各区を同じ時刻に全数確認した市場台帳ではない。

1 batchは既存runの一覧最大2page・詳細最大50件、pending queue最大1,000件。中央計画lockと既存PG writer lockで多重起動を拒否。各batchの結果をbatches.jsonlへ追記、進捗をstatus.jsonへ保存。queue自体は既存PG内でtransaction管理。停止・再起動時も同じ未完了runとjobを再開し、完了jobを繰り返さない。run再開時のrunning表示も更新する。

initialは既に成功取得した詳細の期限再観測を抑え、新規IDを優先（既存pending jobは保持）。incrementalは24時間の再確認間隔で新しい価格観測を追記する。両者とも過去snapshotを上書きしない。未取得・失敗の詳細は既存ルールどおり監査用に残る。完了run内のerrorを同じ--resumeで無限再試行せず、incrementalの新規走査で再確認する。

### 停止条件と報告の意味

アクセス403/429・challengeは出所全体を24時間以上停止。過去の制限後に成功requestがあっても制限記録を見落とさないよう検査を補強した。規約変更・pagination不一致・HTTP等でblockedなら自動計画を止め、無理に別区で続けない。batch内詳細失敗5件以上も品質確認のため停止する。明示禁止は待機で解除しない。接続失敗等を「消失」「成約」と認定せず、正の掲載観測のみを収集する。

statusには地域別成功一意ID、成功snapshot、最新run、kind/state別queue、発見ID、成功した発見ID、サイト広告総数、失敗原因、全体field completenessを記録。field completeness分母は全latest-success IDで、1,000件に切らない。coverage_fractionは当該runの成功発見ID／広告総数の参考比率。ページ間総数が変わる、全page未読、発見数不一致ならcoverage_comparable=false。100%であっても現在の市場全数や物件品質を保証しない。未着手地域を市場在庫0件としない。

### 実行・Windows定期実行

既存PGを起動し、rootで以下を使う。DB URLは環境変数、または既存のGit無視.env.pg-localから読込む。初期化・移行・DBリセットは不要。

```powershell
cd C:\GitHub\JapanHousingLiquidityLab
./scripts/start-postgres.ps1 -PostgresBin C:\posgresql\18\bin
./scripts/collect-tokyo.ps1 -Mode initial -Target 3000 -MaxBatches 200 -MaxSeconds 86400
# 読取り専用の実時点集計。収集は開始しない。
.venv/Scripts/python.exe -X utf8 -m japan_housing_liquidity_lab.tokyo_collection status
# 件数・FK関係・時刻・派生field・価格面積の全件read-only検査
.venv/Scripts/python.exe -X utf8 -m japan_housing_liquidity_lab.tokyo_collection validate --target 3000
# 初回蓄積後の更新例（同一時刻の大量再取得を避ける）
./scripts/collect-tokyo.ps1 -Mode incremental -MaxBatches 24 -MaxSeconds 14400
```

最大時間はbatch境界で判定するので、進行中のbatchの所要分だけ超過し得る。initialで目標達成すると次のbatchを開始しない。1 batch中の増加分だけ目標を超え得る。低頻度の3,000詳細取得には数時間を要し、瞬時の完了を約束しない。目標未達・アクセス停止はstatusで明示する。

Task Schedulerは管理者が手動設定：プログラムpowershell.exe（またはpwsh.exe）、引数 `-NoProfile -File "C:\GitHub\JapanHousingLiquidityLab\scripts\collect-tokyo.ps1" -Mode initial -Target 3000 -MaxBatches 200 -MaxSeconds 86400`、開始フォルダはrepo root、同時実行は「新しいインスタンスを開始しない」。長時間起動はsleep設定とTask Schedulerの終了時間制限を確認。初回達成後は引数をincrementalへ切替え、24時間以上の周期とする。自動登録・クラウド配備はしていない。既存の正規collector以外を並行実行しない。

### データ保全・公開範囲

status/plan/log/DB/dumpはdata/またはreports/内でGit無視。保存は事実field whitelistのみ。SUUMOの限定ローカル私的非商業条件を継続し、件数増加を公開再配布許諾と扱わない。価格モデル・研究結果は変更しない。新しいUIや合成実データは作成しない。テスト用合成fixtureは運用DBへ入れない。

### 今回の実行証跡（継続中・目標未達）

2026-11-09に実行。狛江の旧19 pendingから再開し、追加pageを発見して計75 IDを取得。旧第1pageの広告総数76と当日の75が異なったため、旧runを無理にcompletedにせず、新しい4page走査で75/75を照合した。新走査では詳細取得0・重複snapshot0。旧観測は残す。その後、公式23区リンクを実HTTPで取得し、千代田区40 IDから中央区へ連続進行。区の途中で予算を消化するとpausedになるが、計画全体は次の区へ続く。

実行途中の数値はreports/tokyo-expansion/progress-snapshot.json/csv、最新はstatusコマンド。ここに3,000到達の固定主張を記載しない。中央processが止まるまで採集を続け、別の待機processも終了後のread-only validateを実行する。端末／PCの終了やsleepに対する永続サービス保証ではない。停止時は同じコマンドでcheckpointから再開する。Task Schedulerは未登録。

全180テスト成功、skip 0、47.490秒（実PGテスト11件）。Windows wrapperは構文検査、Python CLIと実HTTP→PG連続運転を実行。全ての既存snapshot/batch/event/requestを旧検証済み復元DBと逐行比較し保持を確認、旧303成果と凍結SQLite hashも一致。実データでのvalidateも実行し、重複source ID、孤立snapshot/batch/event、時刻・派生値不整合、非正価格面積は全て0だった。現在値の検証成功と3,000件目標達成は別の状態。

## English

The target is at least 3,000 distinct SUUMO source listing IDs with successful PG observations, not discovered URLs, snapshots or website-advertised totals. IDs may represent multiple agents for one dwelling. The original 33 IDs, 35 successes, two failures and all history remain preserved with a pre-expansion dump. HOME'S remains paused.

The existing Komae run resumes first. The planner then obtains actual ward links from the official Tokyo index using the existing rule-checked, throttled HTTP client. It requires all 23 ward links instead of inventing URLs. Komae is drained first, followed by incomplete wards with the fewest successfully acquired IDs. This improves breadth but does not remove source-order or incomplete-traversal bias.

Each batch uses at most two list pages and 50 details with the existing bounded queue and transactional snapshot writer. A separate central-plan lock prevents overlapping scheduled plans. PostgreSQL checkpoints, ignored plan/status JSON and append-only batch logs support resumption. initial prioritizes first acquisitions; incremental uses a 24-hour recheck interval and appends observations. Errors and old snapshots are retained. No search omission or HTTP failure generates sale/disappearance claims.

403/429/challenges impose a source-wide cooldown even if later success logs exist. Blocked requests, changed terms/pagination or five detail failures in a batch stop the plan for review. Regional reports expose successful IDs/snapshots, queue states, advertised/discovered/supported counts and failure causes. Completeness uses all latest-success IDs without a 1,000-record cap. Coverage fractions describe a traversal; changing counts or unfinished/mismatched discovery are flagged, and unvisited regions do not mean zero inventory.

Use the Windows commands above from the repository root. Existing local credentials are loaded without printing them; no migration/reset is needed. Time budgets apply between batches. The initial goal may be exceeded by one bounded batch and can take hours at the retained rate. Scheduler instructions above are manual: disable overlapping instances, set the working directory and review sleep/maximum-runtime settings. No scheduled task was registered. After initial accumulation, schedule incremental updates at least 24 hours apart.

Only factual whitelisted fields are retained locally under the existing private/noncommercial scope. Database, status, logs and dumps remain ignored. No HOME'S probing, model retraining, new UI, synthetic production records, commit, push or deployment is included.

### Actual run, still in progress

The old Komae pending queue was resumed and expanded to 75 successfully acquired IDs. The previous entry page advertised 76, while new pages advertised 75. A fresh four-page reconciliation confirmed 75/75 without fetching any known detail again; old observations/runs remain audited. Official links for all 23 wards were actually fetched. Continuous collection then acquired the first 40 Chiyoda IDs and advanced to Chuo. Paused regional batches are checkpoints, not whole-plan completion.

The as-of snapshot is reports/tokyo-expansion/progress-snapshot.json/csv; use the status command for current counts. No 3,000-completion claim is made here. The central process continues until target/budget/review conditions; an independent waiting validator also runs after it stops. This is not a persistent-service guarantee across PC shutdown/sleep. Restart the same command to resume. No scheduler was registered.

All 180 tests passed without skips in 47.490 seconds, including 11 real PG tests. The Windows wrapper passed syntax validation; the Python CLI and actual HTTP-to-PG continuous flow were exercised. Original snapshots/batches/events/requests, 303 old artifacts and frozen SQLite hash were preserved. Read-only validation on actual data found zero duplicate source IDs, orphan records, timestamp/projection mismatches or nonpositive prices/areas. A valid partial dataset and meeting the 3,000 target are reported separately.
