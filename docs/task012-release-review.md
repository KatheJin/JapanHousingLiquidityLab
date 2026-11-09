# Task 012 公開前確認 / Release Review

## 日本語

2026-11-09。ネットワーク基盤・実掲載収集・PostgreSQL移行・東京都継続収集・HOME’S調査・公式XIT001接続を、依存関係を含めて整理した。価格モデルの再学習、既存訓練集合へのAPIデータ追加、DB再初期化、公開配備は行っていない。CommitとPushは利用者の明示指示に従って実行する。過去の監査文書中の「未コミット」「API Pending」「33 ID」は当時の固定記録であり、現在の状態ではない。

### 修正と検証

- 新規のJSON読取りに明示的UTF-8を指定。Windowsの既定文字コードに依存する箇所を修正し、非UTF-8環境を模擬した日本語manifestの再読込みテストを追加。
- SUUMO住所の「東京都新宿区市谷…」を「新宿区市」と誤分割する境界を修正。区の後に市を含む町名と、多摩地域の市名を合成例で検証。原文対応は維持する。
- **稼働中の収集processは再起動・hot reloadしていない。** 住所修正は次の通常起動から適用される。既存snapshotや派生地域列は書き換えていない。旧parser由来の地域誤分類については、次の運用確認で原文に照らして件数を調査し、監査可能な訂正手順を別途実施する必要がある。
- ネットワークDemoの出力は「この合成Demoでは公式API未実行」とし、既に承認済みのキーが未取得であるかのような表現を削除。
- READMEに私有設定・環境変数・Git無視による資格情報管理と、APIの29フィールド／既存CSVの21列・駅情報の差を明記。分類01／02を訓練集合へ自動投入しない。

最終の完全テストは **186件成功、skip 0、45.900秒**。このうち11件は専用PostgreSQL DB `jhll_test` で実行した。主庫 `jhll_listings` とテストDBのUTF8 server/client encodingを実接続で確認した。テストprocessへ本番DB接続変数・API資格情報を渡していない。依存整合性は `pip check` で確認。さらに、各暫存indexを私有ファイルのない独立directoryへexportし、HTTP/APIの19件と実収集/PG/東京都の38件を再実行して成功した。未提出ファイルへの暗黙依存がないことを検証した。

### データと公開範囲

Git候補と暫存blobを実資格情報とメモリ上で照合し、値を表示・記録せず非混入を検査する。`.env.mlit-local`、`.env.pg-local`、data、reports、models、DB・dump・backupを除外。キーの値・fingerprint・認証headerや個々の実掲載snapshotは公開しない。テストHTMLは合成値であり、実ページ本文ではない。生成した試験・安全検査レポートはGit無視の `reports/precommit-review/` のみに保存する。

旧303成果のhash、凍結SQLiteのhash、原PG snapshot/batch/event/request行の一致を再確認。中央collectorとwriter lockが存続し、監査中も実掲載件数が増加した。全地域の完了や3,000到達は本レビューでは主張しない。件数は `tokyo_collection status` で確認する。HOME’Sの403調査は保存済み証拠を使い、再要求していない。公式API実応答の証拠も保持し、本レビューで追加取得はしていない。

### 提出単位

1. HTTP基盤・合成ネットワーク試験・公式API認証と取得・安全なファイル読取り。
2. 実サイトadapter・Task010権利区分・発見queue・PostgreSQL移行／service・東京都継続収集・対応試験と方法文書。PG試験が東京都集計を検証するため、この依存を同一単位に含める。
3. README、固定監査記録の時点注記、最終公開前確認。

実データ・私有設定・実行ログは提出単位に含めない。SQLiteとPostgreSQLの利用・バックアップ・復元については[運用説明](postgres-homes.md)、収集再開は[東京都計画](tokyo-listing-expansion.md)、APIは[実接続記録](mlit-live-verification.md)を参照。

## English

Reviewed on 2026-11-09: HTTP infrastructure, real listing collection, PostgreSQL migration, Tokyo expansion, HOME’S investigation and live XIT001 support were organized with their dependencies. No retraining, API-to-training-set merge, database initialization or deployment was performed. Commits and push follow the user's explicit instruction. Older audit statements about pending keys, 33 IDs or uncommitted work remain historical checkpoints.

New JSON reads now specify UTF-8. A regression test reads a Japanese cached manifest under a simulated non-UTF-8 default. The address parser also now respects the ward boundary in “新宿区市谷…” instead of producing “新宿区市”; synthetic cases cover ward/town and Tama city boundaries. Raw-field mapping is preserved. **The active collector was not restarted or hot-reloaded:** this fix applies on the next normal start. Historical snapshots/projections were not rewritten. Existing misclassifications require a separate raw-field audit and traceable correction procedure.

The synthetic network demo now says the official API is not exercised by that demo, rather than claiming no approved key exists. README documents private credentials/environment handling and the verified API-versus-CSV field differences. No automatic training-data replacement occurs.

The final full suite passed **186 tests, zero skips, in 45.900 seconds**, including 11 actual PostgreSQL tests in dedicated `jhll_test`. Both production and test connections reported UTF8 server/client encoding. The test process did not inherit the production database URL or API credentials. `pip check` passed. Separate exports of each staged index, without private files, also passed 19 HTTP/API tests and 38 collection/PG/Tokyo tests, checking that the submission units do not depend on omitted files.

Candidate files and staged blobs are compared in memory against actual credentials without printing or recording their values/fingerprints. Private configuration, real data, models, logs, databases and backups remain ignored. HTML fixtures are synthetic, not downloaded pages. Generated verification reports remain only in ignored `reports/precommit-review/`.

All 303 old artifact hashes, frozen SQLite and original PG observation/batch/event/request rows were preserved. Collector/writer locks remained active and real acquisition continued during review. This is not a claim of complete regional coverage or reaching 3,000; use the status command. HOME’S was not probed again and no additional official API requests were needed.

Submission units are (1) HTTP/API foundation and tests, (2) real adapters, Task010 integration, queue, PostgreSQL, Tokyo scheduler and their tests/docs together, and (3) README and audit summaries. PG tests exercise Tokyo reports, so that dependency travels in the same unit. Private records/configuration/runtime logs are excluded. See the linked operator, Tokyo and API reports above.
