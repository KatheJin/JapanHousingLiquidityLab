# Phase 3 — 歴史成約分析 / Historical Transactions

## 日本語

2026-11-10。Phase 1–2の変更を保持して追加開発。旧Task003～012のモデル、CSV、研究結果は上書きしない。Phase 5推薦やオンデマンドcrawlerは実装しない。

### データベース復帰

55432にlistenerがなく、SUUMO workerも見つからなかった。既存clusterのPG_VERSION=18とglobal/pg_control、私有設定の存在、pg_ctl statusの停止状態を確認して既存pg_admin startを実行。初期化分岐には入らず、schema upgrade・移行再実行・restoreは行っていない。

復帰後は成功SUUMO出所ID 1,207、成功snapshot 1,209、失敗2、全snapshot 1,211。discovered 1,226、runs 37、jobs 1,341、events 1,209。jobsはdone 1,281、pending 58、error 2。source ID重複0、runを欠くsnapshot/job各0。

**運用上の未解決状態**：worker processとadvisory lockは無いが、running runが1件残る。これは停止した収集のチェックポイントであり、稼働中という意味ではない。本段階では書換えず、workerも起動しない。再開時は既存の単独writer lockと再開機構で状態を再点検する別作業が必要。DBを起動しただけで収集が自動再開したとは主張しない。

### 起動と入力

```powershell
.venv/Scripts/python.exe -m streamlit run streamlit_app.py --server.address 127.0.0.1
```

サイドバーで「歴史成約分析」を選ぶ。通常起動はローカル実データが既定。開発者はJHLL_ENABLE_DEMO=1（旧テスト互換はJHLL_ENABLE_REAL=0）で他の既存画面の合成Demoを明示的に有効化できるが、新ページは常に実データ専用。データ不在時はエラーとなり、Demoへ切り替えない。

対象の市区町村、駅、面積、建築年、掲載価格、参考日をフォームで入力。町名・徒歩分・間取り・構造は任意。築年数を使う場合は既存入力アダプター経由で建築年に変換できるが、本ページは曖昧さを避け建築年を入力する。JSON/CSVの手動アップロードは不要。

### 集計と比較の契約

140,888行のTask008統合CSVを既存web_adapterのhash・件数・期間検証で読み取る。価格bundleは読まず、推論や再学習を行わない。開始・終了四半期は実収録範囲内。参考日は取得確認日以降を必須とし、取引四半期と公表日・取得日を区別する。公表当時の版ではない。

面積±20%、取引時房齢と対象の参考日時点房齢の差±10年。指定町名・間取り・構造は完全一致、徒歩許容差は既定で無効。有効時は対象徒歩分±許容差へ区間全体が含まれる記録だけ採用。不明と一部重複は除外数を別表示。既存Task006 strict_maskを再利用する。比較範囲はstrict_station（同市区町村と駅）、municipality（市区町村内）、selected_locations（明示した市区町村/駅pairの集合）。条件を自動緩和しない。後者は将来の地域・駅比較用の境界であり、推薦ランキングではない。

駅はNFKC正規化した名称と自治体で区別する。駅ID・座標による同一性や表記揺れの完全解決は未実装。町名を指定したまま広域比較すれば一致標本が少なくなるため、適用条件を結果JSONに保存する。

最初に全比較記録数を返す。折りたたみ表に四半期・総額原表記・未調整単価（円/㎡と万円/㎡）・面積・建築年・取引時房齢・地区/駅・間取り・構造・元CSV名/行番号・データ区分を表示。欠損数、収録四半期、取得確認日、hash、標本数を表示する。匿名重複は削除せず住宅の実数や市場総数と呼ばない。小標本は警告する。欠けた四半期はnullとし、ゼロ取引とは扱わない。

2018～2022拡張と2023～2026既存期間を行単位・件数で分ける。既存期間でも正式調整の妥当性は未確認。Hedonic Adjustmentのformal_adjustment_statusを共用し、属性/時間/老化の正式価格は全てnull、status unavailable。研究的decompose値を本画面へ流さない。2018～22は既存モデル期間外の理由も明示。原単価の大小を将来確率・購入推奨へ変換しない。

### 実データの端到端例

世田谷区・三軒茶屋、25㎡、2005年築、1K、RC、3,000万円、参考日2026-11-10。2018Q1～2026Q2で106記録（拡張66、既存40）、全106行に単価あり。未調整中央値120万円/㎡、中央50%は105～130万円/㎡。この集合の町名・駅・徒歩原表記・建築年・間取り・構造の空欄は各0。モデルの信頼性を示す値ではない。

tests/test_historical_query.pyは既存mask関数を使わない独立の原表条件でも件数を再計算し、全行の出典key、四半期、面積、建築年、房齢、駅、間取り、単価を照合する。Streamlit AppTestで実フォームから送信し、106行の展開表・単価・quarter、2つのdownload入口、別sessionの非共有を検査。欠損ファイル時の拒否、比較scopeと正式調整gateも検査。これは自動UI端到端検証であり、手動実ブラウザー／スマートフォンの受入検査ではない。

### 保管と権利

ローカルの公開MLIT取引CSVを加工表示する。出典URLと加工を明記し、取得時点の利用条件を維持。現在の私有SUUMO/PG掲載はこの画面の明細・downloadへ入れない。JSON/CSVのdownloadは検索結果だけ。CSVの先頭数式文字はescapeし、JSONは元の値を保持する。データと入力はsession内、永続化しない。画面を公開配備する許可やアクセス制御は別課題。本段階で配備しない。

### 最終検証

完全テスト200件成功、skip 0、83.968秒。復帰直後の11件PG suiteも12.179秒で成功。実際の主庫13テーブルの全内容hashは試験前後で一致し、runs/jobsも変更なし。旧303成果hashと凍結SQLite hashも一致。公開候補113ファイルに実資格情報の混入なし、暫存0。生成したDB検査・例示全明細・試験logはGit無視のreports/phase3-validation内だけ。既存のrunning 1件は未修復で、収集再開は別途確認が必要。

### Phase 3収尾

収尾後の全203テストが84.677秒で成功、skip 0。元条件106記録を維持。後続の利用者指示によりPhase 1–2とPhase 3を別commitとして提出する（従前の未commit記述は当時の記録）。

明細は四半期・総額・単価・面積・房齢・駅・距離を先頭へ、追跡keyを末尾へ移動。Quarter表は取得済一致あり／取得済0件／公開確認済未取得／未公開／公開状況未確認を区別。収録の最終期だけから後続期を未公開と断定しない。将来期は未公開、公表状況不明の過去・現在期は未確認とする。

## English

The existing PostgreSQL 18 cluster was stopped. Its version/control files and stopped pg_ctl state were verified before using the existing start helper. No initialization, schema upgrade, restore or migration replay was performed. Recovered counts: 1,207 successful SUUMO IDs, 1,209 successful snapshots plus two failures; discovered 1,226, runs 37, jobs 1,341 and events 1,209. No duplicate source IDs or orphan snapshot/jobs were found. No collector/advisory lock exists, but one run retains running status and 58 jobs are pending. These checkpoints remain unchanged; no worker was launched. Restoring the DB does not automatically resume collection.

Use the loopback Streamlit command above and select 歴史成約分析. Real data is the normal default. Developer demo is explicit and applies only to the older pages; the new page always reads verified real data and refuses missing files without a synthetic fallback. Enter property details through a form; no JSON/CSV upload is required.

The service reuses Task006 matching and Task008 verified 140,888-row loading. Area ±20%, historical age versus subject age at reference date ±10 years, and exact supplied town/layout/structure remain explicit. Walking tolerance is off by default. When enabled, the entire reported interval must fit the tolerance; unknown and partial-overlap records are reported separately and excluded. Scopes are same city/station, municipality, or explicit city/station pairs; no automatic relaxation or regional recommendation is performed. Station identity is normalized name plus municipality, not a verified station ID.

Results expose source/coverage/missingness, original prices and expandable full transaction details. The 2018–22 extension and 2023–26 existing-model period remain separate. Neither period currently has approved attribute/time/aging adjusted prices: the shared Hedonic gate returns unavailable/null and research diagnostic values are never substituted. Counts describe anonymous observed records, not unique homes or the whole market; missing quarters are not zero, and lower historical prices are not future purchase probabilities.

The real Setagaya/Sangenjaya 25m², 2005, 1K/RC, JPY30m example yields 106 rows: 66 extension, 40 existing-period. Raw median is JPY1.2m/m² and interquartile range JPY1.05–1.3m/m². Independent source filtering and row-level checks match the Streamlit form/result/detail table. Tests cover downloads, session isolation, missing data and alternate comparison scopes. AppTest is automated UI end-to-end verification; no manual browser/mobile acceptance is claimed.

The page uses processed public MLIT transaction data with attribution; private SUUMO/PG listings are not exported here. CSV formula prefixes are escaped; JSON preserves source values. Results live only within the session. No deployment, commit or push is performed. Old models and research artifacts remain intact.

Final validation: all 200 tests passed with zero skips in 83.968 seconds; the isolated 11-test PostgreSQL suite also passed in 12.179 seconds. All 13 primary-table content hashes match before/after testing, including runs/jobs. The 303 old artifact hashes and frozen SQLite hash match. Credential scanning passed for 113 public candidates; nothing is staged. Runtime evidence and full example rows remain only in ignored reports/phase3-validation. The one stale running status remains unresolved; collection has not been resumed.

Polish: transaction facts precede provenance columns. Quarter states distinguish acquired matches/zero, verified-published-but-not-acquired, unpublished and unverified publication. The latest acquired quarter is not assumed to be the latest published quarter. Original no-walk-filter behavior remains unchanged.

Final polish passed all 203 tests without skips in 84.677 seconds and preserves the original 106-record query. Submission is now explicitly authorized as separate Phase 1–2 / Phase 3 commits; previous no-commit statements describe their historical checkpoints.
