# PostgreSQL・実掲載拡張の最終監査 / Final Migration and Collection Audit

## 日本語

以下は移行監査時点の固定記録です。狛江pending・現在件数・API Pendingの記述はその時点のものです。後続の[継続収集](tokyo-listing-expansion.md)・[公式API検証](mlit-live-verification.md)・[公開前確認](task012-release-review.md)を参照してください。

2026-11-09の最終監査。実データ主庫への追加収集・削除・リセット、Commit、Push、公開配備は行っていない。以下は移行時点と増分後の違いを明示した結果であり、SQLiteと現在のPGの総数が同一であるという主張ではない。

|項目|凍結SQLite / 初回移行|現在のPostgreSQL|
|---|---:|---:|
|成功した出所別掲載ID|31|33|
|成功観測|32|35|
|失敗観測|2|2|
|全snapshot / batch|34 / 34|37 / 37|
|event|32|35|
|発見ID（詳細未取得を含む）|31|51|
|run / job|8 / 55|12 / 81|
|page / page_link / request|6 / 51 / 54|9 / 73 / 68|

### 検査と修正

- 元SQLiteのSHA-256は `34cdb95d43972cc1b357cdf5b27a668c4e3e9742bb5998cdfcd5d3c666c19678`。Windows読取り専用属性とアプリのread-only接続を確認。原ファイルは保持。
- 移行をさらに2回実行し、主庫全テーブルの内容が不変であることを確認。初回receiptと不変観測行を照合し、更新済みqueue/controlを古い値へ戻さない。元列・JSON・微秒・タイムゾーンに加えて、派生JSONB・数値・地域・native時刻列を全行再計算して照合。
- 新しいcustom dumpを新DBへ復元。元の10テーブルだけでなく、予約2テーブル、migration_receipts、alembic_versionも主庫と完全一致。復元先のみで後述の合成障害試験を実施。主庫と凍結SQLiteは試験後も不変。
- 複合source/listing ID、PK/UNIQUE、遅延FK、transaction rollback、writer lock、観測・地域・価格・pending索引を確認。Alembic headは012pg002。schema v1は変更せず、破壊的downgradeは禁止のまま。
- **実際の修正**：強制終了時に残ったファイルlockとrunning行がPGの再開を妨げた。PGは既存のsession advisory lockだけを使い、単独writer取得後に残ったrunning行をinterruptedへ変更して再開する。SQLiteのファイルlockは従来どおり保持。別workerのlockを削除しない。
- 強制終了状態を再現するPG回帰テストを追加。SQLite読取り専用テストも、sqlite3単体ではなく実際のStoreと切替えmarkerを検査するよう修正。

### 狛江の19件と失敗復帰

主庫のpaused runにpending 19件（一覧1、詳細18）が残る。新しい復元副本で実queueを使用し、合成HTTP 503相当の失敗を注入したところ19件を保持。次の再開で同じrun IDを使い、完了済み最初の一覧を読み直さず、合成一覧1件と合成詳細1件を処理して17件になった。これは**queue制御の副本検証**であり、新規の実SUUMO取得を示さない。副本の合成観測を主庫へ戻してはならない。主庫は19件のまま。

通常の再開はpendingのみ処理する。既にerrorとなった詳細は監査記録として残り、同じrunの--resumeで無条件再試行しない。原因・アクセス制限を確認後、新しいrun（--resumeを付けない）で未成功・再確認期限到来の詳細を再検査する。403/429等の24時間抑止や規約禁止を解除する操作ではない。意図的な期限到来再観測は新snapshotを追加するため、すべての反復実行がゼロ書込みになる意味での冪等性ではない。完了jobの再開・期限内既知詳細のスキップ・移行再実行では重複しない。

現在のSUUMO parser、読取りquery/search/history/coverageを検証。主庫queryは33 ID、狛江2 ID、HOME'S 0件。今回サイトへの新たな取得は行わず、実HTTP成功の証拠は前回の実行記録を保持している。今後の実サイト構造・アクセス可否を保証するものではない。

HOME'Sは前回の通常Requestsでrobots 200・指定一覧403。以前の403は規約URLだった。詳細、ページング、住戸単位IDは未検証で、Discovery原型を完成した第二sourceとしない。[正確なURL・要求条件](postgres-homes.md)を参照。at homeの禁止、公式API Key Pendingも未解消。

### Git・依存関係・成果保全

完全テストは **175件成功、skip 0、49.016秒**。うち9件は実PostgreSQL専用テストDBで実行。pip checkおよびgit diff --checkも成功。前回174件は以前の実行記録であり、今回の結果で置き換えて解釈しない。

data/、reports/、models/、.env.pg-local、DBクラスタ、CSV、SQLite、dump、実行ログはGit無視。候補ファイルを実パスワードで検査し非混入を確認。旧303成果のハッシュ一致、価格モデル・旧研究アルゴリズムは変更なし。listings.pyのpublic_terms_review許容は今回より前のTask012変更で、実パイプラインの入力に必要な依存差分。公開再分配許可を与えるものではない。

下のmanifestはTask012の未コミット依存も含む。PGファイルだけのコミットでは不十分。実データ、資格情報、生成レポート、監査副本、scratch scriptは含めない。git add/commit/pushは未実行。

### 次の運用

rootで実行。既存venvは再作成不要。全テストには既存研究/UI依存も必要：

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pip install -e ".[reins,public-listings,postgres]"
./scripts/start-postgres.ps1 -PostgresBin C:\posgresql\18\bin
# 狛江の主庫pendingを続行。新規runにしない。
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin collect --source suumo --entry https://suumo.jp/ms/chuko/tokyo/sc_komae/ --max-pages 2 --max-details 10 --recheck-hours 24 --resume --local-private-only
# 同名既存ファイルを使わない。
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.pg_admin backup --file data/postgres-backups/after-komae.dump
```

再移行は通常の増分更新に不要。再検証する場合だけ `pg_admin migrate` を使用（既に切替え済みなので--activate不要）。復元は `pg_admin restore --file data/postgres-backups/after-komae.dump --database jhll_restore_next` のように必ず新DBへ。既存DBを上書きしない。

PGを含む完全テストでは専用jhll_testへ接続するJHLL_TEST_DATABASE_URLをプロセス環境へ設定し、`python -m unittest discover -s tests -v`を実行する。パスワード付きURLをコマンド履歴へ直接記載しない。未設定時のPG skipは実検証成功ではない。現在の読取り層はStreamlit接続境界として使えるが、認証・DB最小権限・Web管理画面・定期実行・公開利用許諾は次段階。

## English

The following is a frozen migration-audit record. Its Komae queue, counts and API-pending statements describe that checkpoint. See subsequent [collection](tokyo-listing-expansion.md), [API verification](mlit-live-verification.md) and [release review](task012-release-review.md).

Final audit on 2026-11-09. No new live collection, primary-data deletion/reset, commit, push or public deployment. The table above distinguishes the frozen SQLite baseline from legitimate later PostgreSQL observations: 31→33 successfully collected source IDs, 32→35 successful observations, two retained failures, 34→37 snapshots/batches and 32→35 events. Discovered IDs (51) are not successful acquisitions.

Two further migrations left every primary table unchanged. Original immutable rows/receipt, legacy fields, microsecond/native timestamps, JSONB, price and region projections were verified. A new dump restored exactly into a fresh DB, including reserved tables, receipt and Alembic version. The original SQLite retains its hash and read-only protection. SQLAlchemy constraints, indexes, transaction rollback and writer exclusion passed review; frozen v1 and Alembic head 012pg002 were retained.

One real recovery defect was fixed: a killed worker could leave a filesystem lock and running status that prevented PG resumption. PG now relies on its existing session advisory lock; after acquiring exclusive ownership, abandoned running rows become interrupted. SQLite file locks remain unchanged. A PG regression test exercises stale status/lock, same-run resumption and no repeated completed detail. The frozen-SQLite test now exercises the actual Store/activation path.

The real Komae queue has 19 pending jobs (one list, 18 details). On an isolated restored copy, a synthetic page failure preserved all 19; the next resume reused the run, skipped the completed entry page, processed one synthetic page/detail and left 17. This verifies control flow, not new live acquisition. The primary remains at 19 with unchanged data. The review copy contains synthetic validation data and must never be promoted or merged into production.

Resume handles pending jobs; terminal error details remain audited. After investigating the cause/access restrictions, a fresh run without --resume can revisit unsuccessful/due details. Access cooldowns and explicit prohibitions still apply. Intentional later observations append snapshots; idempotence does not mean suppressing legitimate time-series observations. Migrations and completed-job/fresh-detail skipping do not duplicate data.

Queries return 33 SUUMO IDs, including two Komae IDs, and zero HOME'S records. Existing real network evidence was retained; this audit did not issue new portal requests. The earlier HOME'S ordinary Requests probe got robots 200 and list 403; its older terms request also returned 403. Pagination, detail fields and stable room IDs remain unverified. See [request details](postgres-homes.md); no verified second source is claimed. at home's restriction and the pending official API key remain unresolved.

Git ignores credentials, data, databases, dumps, models and runtime reports. Candidate files contain no actual DB password; 303 old artifact hashes still match. Existing pricing/research algorithms are unchanged. The pre-existing listings.py rights-enum addition is required by Task012 and grants no redistribution permission. Include all dependencies in the manifest below, not just PG modules. No staging occurred.

The complete suite passed **175 tests, zero skips, in 49.016 seconds**, including nine actual PostgreSQL tests in the dedicated test DB. pip check and git diff --check passed. The earlier 174-test result remains a historical execution record.

Use the installation/start/resume/backup commands above from the project root. Normal collection does not need another migration. Restore only into a fresh named DB. Complete tests require JHLL_TEST_DATABASE_URL pointing at dedicated jhll_test via the process environment; never put credentials in shell history. Existing read services are ready for later Streamlit integration; authentication, least-privilege production roles, admin UI, scheduling and public-use clearance remain separate work.

## コミット対象 / Commit manifest

```text
README.md
.gitignore
pyproject.toml
alembic.ini
docs/task012.md
docs/task012-real-pipeline.md
docs/postgres-homes.md
docs/postgres-final-review.md
docs/homes-http-investigation.md
docs/tokyo-listing-expansion.md
docs/mlit-live-verification.md
docs/task012-release-review.md
japan_housing_liquidity_lab/listings.py
japan_housing_liquidity_lab/net_http.py
japan_housing_liquidity_lab/crawler.py
japan_housing_liquidity_lab/mock_site.py
japan_housing_liquidity_lab/mlit_client.py
japan_housing_liquidity_lab/network_demo.py
japan_housing_liquidity_lab/public_listings.py
japan_housing_liquidity_lab/listing_pipeline.py
japan_housing_liquidity_lab/tokyo_collection.py
japan_housing_liquidity_lab/pg_schema_v1.py
japan_housing_liquidity_lab/pg_schema.py
japan_housing_liquidity_lab/pg_store.py
japan_housing_liquidity_lab/pg_migrate.py
japan_housing_liquidity_lab/pg_admin.py
migrations/env.py
migrations/versions/012pg001_initial.py
migrations/versions/012pg002_receipts.py
scripts/start-postgres.ps1
scripts/collect-tokyo.ps1
tests/test_network.py
tests/test_public_listings.py
tests/test_listing_pipeline.py
tests/test_postgres.py
tests/test_tokyo_collection.py
tests/test_mlit_credentials.py
```
