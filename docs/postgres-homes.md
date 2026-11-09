# PostgreSQL移行・HOME'S再調査 / PostgreSQL Migration & HOME'S Review

## 日本語

後続の[最終監査](postgres-final-review.md)で、強制終了復帰の修正、175テスト、全表復元・queue副本検証と提出対象一覧を記録。本書の174テストは初回移行開発時点の実行記録。

### 実施結果

SQLiteを削除せずバックアップし、PostgreSQLへ移行後、原フィールド・時刻・関係・冪等性を確認して主書込み先を切替えた。既存PostgreSQL 18はインストール済みだったが既知の5432/5433接続を利用できなかったため、同じバイナリで**127.0.0.1:55432の独立開発クラスタ**を作成した。既存サービスのパスワード・設定は変更していない。Dockerやクラウド配備は行っていない。

| データ | 移行元SQLite | 初回PG移行直後 | 実増分後PG |
|---|---:|---:|---:|
| 発見済みsource＋掲載ID | 31 | 31 | 51 |
| 詳細成功の一意ID | 31 | 31 | 33 |
| 成功観測 | 32 | 32 | 35 |
| 失敗観測 | 2 | 2 | 2 |
| 全snapshot／batch | 34／34 | 34／34 | 37／37 |
| events | 32 | 32 | 35 |
| runs | 8 | 8 | 12 |
| jobs | 55 | 55 | 81 |
| pages／page_links | 6／51 | 6／51 | 9／73 |
| requests／controls | 54／3 | 54／3 | 68／3 |

武蔵村山市を実HTTPで再確認してPGへ1観測を追加、狛江市の一覧から新しく2IDを実取得してPGへ追加した。狛江市の実行は予算でpaused、残り19タスク（詳細と次ページ）を保存している。全東京都や狛江市の全件取得を主張しない。33は掲載ID数で、実住戸の同定数ではない。現行掲載価格と成約価格は区別する。HOME'Sの実レコードは0。

原SQLite：data/listing-extension/listings.sqlite3。アプリのread-only接続とWindows read-only属性で凍結し、ハッシュも切替え前と同じ。バックアップはdata/postgres-backups内、PGクラスタはdata/postgres-local/cluster内。パス・数値・監査結果はreports/postgres-homes内。全てGit無視で、元DBを削除・置換していない。

### スキーマ・移行・トランザクション

SQLAlchemy metadataとAlembicの012pg001→012pg002を使用。初期モデルはpg_schema_v1.pyへ凍結し、後続変更は新revisionで管理する。元の各列・JSON文字列・ISO時刻文字列を維持し、加えてTIMESTAMPTZ・JSONB・地区・価格の索引列を保持する。controls.last_request_atは元の浮動小数時刻を保つ。観測の微秒や元タイムゾーン表現を丸めず、native時刻との同一瞬間も検査する。

source＋listing_id複合主キーを維持。run→job/page/request/snapshot、snapshot→batch/event、page→page_links等に遅延可能外部キーを設け、同一transactionで親子をcommitする。runと観測のsource一致も検査する。source/ID/観測日時、地区/価格、pending queueに索引を設ける。クロール処理は既存のまま、小さいSQL bridgeで既存のパラメータ化SQLをSQLAlchemyへ接続する。任意SQLite SQLの完全互換層ではない。新しいUI参照はSQLAlchemyのネイティブ読取りサービスを使う。

移行はcollector lock取得→SQLite online backup→Alembic upgrade→PG単一transaction→原値／時刻／関係検査→検証receipt→任意の切替えマーカー、の順。途中エラーはrollbackし切替えない。繰返しは主キーで重複させず、初回証跡をmigration_receiptsに保存する。増分開始後は観測・batch・event等の元の不変行を再照合し、更新されたqueue/control等を古い値に戻さない。実データで移行を繰り返し、増分後も再実行した。

SQLiteとPGの双方で、snapshot・batch・event・job完了は一括書込み。PG advisory lockは中央の収集writerを1つに制限し、移行も同じlockを利用する。ListingQueryは別接続のread-only transactionなので、普通の閲覧が収集を開始しない。元SQLiteを再び書込み先へ自動fallbackしない。

立上げ時に浮動小数の通信時刻、jobのpending初期値、text/native timestampのSQL bind、native datetimeのJSON出力の差を修正した。未完了の初期PG実行は監査記録に残した。元SQLiteやモデルは修正していない。

### 実行コマンド

rootでPython 3.12を使う：

```powershell
.venv/Scripts/python.exe -m pip install -e ".[postgres,public-listings]"
./scripts/start-postgres.ps1 -PostgresBin C:\posgresql\18\bin
# 初回移行：検証が成功してから切替え
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin migrate --activate
# 中央workerとしての継続収集（CLI・ローカル限定）
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin collect --source suumo --entry https://suumo.jp/ms/chuko/tokyo/sc_komae/ --max-pages 2 --max-details 10 --recheck-hours 24 --resume --local-private-only
```

start-postgres.ps1はDB起動とAlembic upgradeのみ。初期設定には既存PGバイナリを使い、schema/migrateだけならJHLL_DATABASE_URLで管理者の既存ローカルDBへ接続できる。開発補助pg_adminは環境変数を優先し、未指定ならGit無視の.env.pg-localからローカルパスワードを読み環境へ設定する。新しいローカルクラスタだけランダムパスワードを生成する。既存クラスタで資格情報を失ったときは自動再生成・リセットしない。パスワードをCLI引数・alembic.ini・Gitへ書かない。

SQLAlchemy／Alembicを直接使う場合は、資格情報を公開せずJHLL_DATABASE_URLをプロセス環境へ設定する。`alembic upgrade head`、`python -m japan_housing_liquidity_lab.pg_migrate --activate`が使える。helperを介さない既存listing_pipeline CLIも、切替えマーカー後はPGを既定にするが、環境変数が必要。パスワードを含むURLを画面やログへ表示しない。

```powershell
# 新しいパスを使う。既存dumpを上書きしない。
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin backup --file data/postgres-backups/operator-backup.dump
# 必ず新しいDB名。既存DBへの破壊的な上書きはしない。
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin restore --file data/postgres-backups/operator-backup.dump --database jhll_restore_new
# ローカル専用クラスタを停止
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin stop
```

pg_dumpのcustom dumpとpg_restoreの単一transactionを使用。今回は実dumpを新DB jhll_restore_verifyへ復元し、十の原テーブルを主庫と逐行比較した。モデル予測や普通利用者データは作成していない。開発ownerは広い権限を持つので、公開時は別のreader/worker/migration roleへ最小権限を分離する必要がある。

### HOME'Sの実HTTP結果

以前の403は`https://www.homes.co.jp/kiyaku/`で、robots取得後・一覧前の規約確認段階だった。旧collectorはnet_http、公開プロジェクトUA、TLS検証、redirect/cookieなし。サイト全体が読めないという証拠ではない。

今回はRequestsで指定された`https://www.homes.co.jp/mansion/chuko/tokyo/list/?page=1`を独立して確認した。UAはJapanHousingLiquidityLab/0.2 (limited public page verification)、timeout接続10秒／読取り20秒、redirectなし、通常のTLS検証、10秒間隔。robotsは200、対象パス許可。**一覧は403、HTML応答919 bytes、約0.83秒**だった。対象一覧の403を繰返し試したり、cookie/login/proxy/browser偽装で回避していない。サーバー側理由は未確認で、bot判定・IP・地域制限等の原因を断定しない。

従って本段階では一覧ページング、detail HTML、字段、同じ建物の住戸別安定IDは実証できず、実収集0件。検索結果キャッシュを実取得として数えず、第二出所の完成とは呼ばない。元の未検証Discoveryプロトタイプも有効な第二sourceとして扱わない。通常アクセス条件で対象ページを取得できる段階に、住戸IDと建物IDを区別してadapterを検証する。robots許可は再利用許諾ではない。SUUMOのPG更新は独立して完了した。

### UI・一鍵操作の実装境界

**実装・実行済み**：Windowsの1コマンドDB起動スクリプト、CLIによるschema初期化／検証付き移行／収集／backup／新DB restore、SQL読み出し。これらは開発者用の簡単な起動操作であり、「普通利用者向けのWeb一鍵収集」ではない。

**schema／interfaceのみ**：collection_commandsにsource/scope/action/status/requested_at、model_referencesにobservation_id/model_version/predicted_at/reference_quarter/resultを確保。今はcommands consumerも自動予測も動かない。モデル再学習・差替えなし。ListingQuery.search/history/coverageは実装し、接続不能時はDataUnavailableという日本語の説明へ変換する。実データがなければ空／エラーで、合成データへfallbackしない。

```python
from japan_housing_liquidity_lab.pg_store import ListingQuery, DataUnavailable
query = ListingQuery()
try:
    rows = query.search(source='suumo', municipality='狛江市',
                        min_price=0, max_price=60000000, limit=100)
    history = query.history('suumo', 'source_listing_id')
    coverage = query.coverage('suumo')
except DataUnavailable as error:
    # Future Streamlit: st.error(str(error)); never generate dummy inventory.
    pass
```

source IDは複合キーで分離し、類似住戸の自動統合はしない。返却値は最後の肯定観測、最新検査、unknown_coverage／unknown_identity等を併記し、古い価格を確実な現行在庫としない。画像・個人連絡先を新たに取得しない。

**後続の具体案**：普通購買者画面は実データ検索・履歴・既存価格参照・地域比較だけを表示する。管理者画面は認証済みadminだけにsource/地域/周期/start/pause/stopを提示し、確認後にcommandを登録する。中央workerだけがcommandを消費し、閲覧者の検索でcrawlerを起動しない。progressはrun/job/requestから成功・失敗・更新時刻・実範囲を表示する。OIDC等の認証gatewayとrole検査、command冪等キー、取消し協調、scheduler、監視、必要なデータ許諾を独立タスクで実装する。現在はログイン・admin画面・Webボタン・公開userサービスはない。旧JSON/CSV、合成デモ、ログは将来developer/admin領域へ移す。既存Streamlit原型は今回大改造しない。

Windows補助スクリプトは実機試験済み。Docker Composeによるdb＋worker＋webの分離は今後の配備案で、今回は設定を作成・実行していない。Docker版では同じAlembicと環境変数を使い、PGを外部公開せず、volume・backup・role・ネットワークを検証する。クラウド／AWS配備・アクセス公開は未実施。

### 検証・制限

PostgreSQLテストは専用jhll_test DBで行い、DB名を確認してからテスト表を消去する。本物の採集DBをテストでtruncateしない。移行、再実行、増分後再移行、微秒保持、FK、rollback、source命名空間、価格変化、失敗で下架しないこと、writer lock、reader検索・履歴・範囲を検査する。未設定の環境ではPGテストは明示的にskipするため、実行していないPGを合格と呼ばない。

初期立上げでWindows pg_ctl出力pipeが完了待ちになったため、公開したpg_adminでは子プロセス出力を無視対象ファイルへ直接渡す方式に修正した。最終Windowsスクリプトは実行成功。原SQLiteハッシュ、データ・資格情報のGit無視、旧研究artifactも確認する。HOME'Sは未取得のまま。Webの一鍵操作、権限の実装、連続耐久／負荷試験、Linux/Composeでの再現性は未完了。Commit/Push/配備なし。

最終検証：174テスト成功、43.249秒、skipなし。うち8テストは実PostgreSQL専用DB。最終CLI増分確認も正常終了し、24時間以内の既知詳細を再取得しないことを確認。backup/restore再検証、旧303成果ハッシュ、元SQLiteハッシュ、Git無視と実パスワード非混入を確認。ステージ済み0。

## English

The subsequent [final audit](postgres-final-review.md) records the killed-worker recovery fix, 175 tests, full-schema restore/queue-copy checks and commit manifest. This document's 174-test count is the earlier migration-development run.

### Implemented and actually run

A dedicated PostgreSQL 18 cluster runs on 127.0.0.1:55432 using installed binaries; existing service settings/passwords were not changed. SQLite was backed up, migrated transactionally and verified before activating PG writes. The original file is retained read-only with the same hash.

Initial migration preserved 31 discovered/successful IDs, 32 successful plus two failed observations, 34 batches, 32 events, eight runs, 55 jobs, six pages, 51 page links, 54 request logs and three controls. Repeated migration did not duplicate rows. Exact legacy values, microsecond timestamps, native timestamp equivalence and foreign/source relationships were checked.

Real post-cutover collection added one Musashimurayama recheck and two new Komae IDs. PG now has 51 discovered IDs but **33 successfully collected unique IDs**, 35 successful/two failed observations, 37 batches and 35 events. Komae is bounded/paused with 19 remaining tasks, not a complete-city census. Listing IDs are not guaranteed unique dwellings. A custom pg_dump backup was actually restored into a new database and all ten original tables compared exactly. SQLite was never deleted/replaced.

SQLAlchemy/Alembic maintain the schema, frozen v1 definitions and migration receipts. Original text/JSON/time precision stays intact alongside indexed native TIMESTAMPTZ/JSONB/municipality/price fields. The old collector uses a narrow parameterized SQL bridge rather than a rewritten state machine. New reader services use native SQLAlchemy, read-only transactions and clear errors, without synthetic fallback. Source IDs are namespaced, writes commit snapshots/events/tasks together and a PG advisory lock permits one central writer.

### Operator commands

Use the installation/start/migrate/collect/backup/restore commands above from the project root. PostgreSQL binaries default to C:\posgresql\18\bin. JHLL_DATABASE_URL is the direct SQLAlchemy/Alembic connection environment variable. The local helper can load an ignored .env.pg-local into the process environment; it generates a random password only for a new development cluster. Credentials are never passed in CLI arguments or committed. Losing credentials does not silently reset an existing cluster.

start-postgres.ps1 actually starts/checks the local DB and upgrades its schema. pg_admin migrate --activate backs up and verifies before cutover. pg_admin collect uses PostgreSQL explicitly. Restore requires a fresh database and will not overwrite an existing one. Original SQLite collection is blocked after activation; environment/connection failure does not fall back to writing SQLite. The development owner has broad privileges; production needs separate least-privilege reader/worker/migration roles.

### HOME'S finding

The previous 403 was at /kiyaku/, after robots but before listings, using the project's normal HTTP client. This was not proof that all pages were inaccessible. This time ordinary Requests fetched robots successfully and confirmed the supplied Tokyo list path was allowed, then GET https://www.homes.co.jp/mansion/chuko/tokyo/list/?page=1 returned **403 (919 bytes, approximately 0.83 seconds)**. The project UA, verified TLS, no redirects and bounded timeouts/ten-second spacing were used. No proxy switch, browser impersonation, cookie/login or challenge bypass followed.

The server-side cause remains unknown. Pagination/detail HTML, fields and stable room-level versus building-level IDs could not be validated, so no HOME'S records were inserted and no verified second-source adapter is claimed. Search-cache content was not counted as acquired data. SUUMO migration and incremental writes proceeded independently.

### Product boundary and future plan

Implemented/tested conveniences are developer CLI/Windows commands and database query services—not a buyer-facing Web collection button. ListingQuery.search/history/coverage provide the future Streamlit boundary, including latest evidence and unknown states. collection_commands and model_references reserve command/progress and observation/model-version/prediction-time/reference-quarter metadata; no consumer or automatic model scoring is implemented.

A later buyer UI should expose real search/history/reference/region information only. An authenticated administrator UI should enqueue scoped start/pause/stop/frequency commands; a central worker alone consumes them. Viewer searches must never launch duplicate crawls. OIDC/role enforcement, idempotent commands, cooperative cancellation, scheduling, progress/error screens and licence review require separate implementation. Existing demos/manual files become developer tools. No full UI redesign, login system or public deployment occurred. Docker Compose db/worker/web isolation is a future design, not a tested deployment delivered here.

Dedicated jhll_test integration tests cover idempotent migration, precision, FK/rollback, source separation, failed-observation abstention, writer locking and reader services. Missing test configuration causes explicit skips elsewhere. Local logs/backups/cluster/credentials remain ignored. Original research/models are preserved. No MLIT-history bulk import, model retraining, commit, push or cloud release.

Final verification: all 174 tests passed in 43.249 seconds without skips, including eight real PostgreSQL integration tests. The actual operator collect CLI also completed, skipping fresh known details. Backup/restore and original SQLite hash checks passed; all 303 old artifact hashes match. No credentials or raw databases are tracked, and nothing is staged.
