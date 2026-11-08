# Task 010 — 掲載観測・追跡 / Listing Acquisition & Tracking

## 日本語

### 実施範囲

基準コミット `53df3f9`。ネットワーク取得のないローカルJSON/CSVインポート、観測履歴、価格・属性変化、複数媒体の消失・再出現を実装。**今回は実際の掲載データを取得していない。全実行例はSYNTHETICと明示した架空データ**。既存モデル・Task 001～009成果は変更しない。Commit/Pushなし。

### データ入手可能性の調査（2026-11-08確認）

| 候補 | 許諾・取得経路 | 項目・頻度・制限 | 今回 |
|---|---|---|---|
| SUUMO | [公式利用規約](https://cdn.p.recruit.co.jp/terms/suu-t-1003/index.html)は私的利用の範囲を超える無承諾利用を制限。一般向け研究再利用APIの許可は確認できず | 掲載価格・属性の表示と、取得・保存・再配布許諾は別。更新SLAや履歴保存権は未確認 | 一括取得なし。必要なら提供者へ用途・保管・頻度の許諾を問い合わせる |
| LIFULL HOME'S | [規約第6条](https://www.homes.co.jp/kiyaku/)の権利制限。[公式データソリューション](https://data-solution.homes.jp/)に正式な相談窓口あり | 所在・交通・価格・面積・間取り・築年等を相談可能。価格は提供項目・量による見積り。研究保存・更新頻度・終了通知・ID継続性は個別確認 | 契約/APIキー未取得。必須依存にしない |
| at home | [公式サイト](https://www.athome.co.jp/)の掲載情報は無断転載禁止と表示 | 完全な規約本文は本ツールで405となり未確認。自動取得・再利用可能な一般提供API／更新頻度は未確認 | 制限を回避せず取得なし。書面による提供条件の確認が必要 |
| 提供者が許可したCSV/JSON・定期スナップショット | 住宅所有者・仲介会社・データ提供者が用途と保持を許可した資料 | ID・価格・住宅属性・観測対象の完全性を契約/仕様で確認。頻度は合意による | 受入れ口を実装。許可をCSV受領だけで推定しない |
| 手動入力・自作情報 | 自ら保持・利用する権利のある情報。単なる手入力は第三者資料の利用許可の代用ではない | 個別確認の時刻と根拠。全媒体の網羅性は通常不明 | 利用可能。現時点は合成例だけ |
| 自由再利用できる公開データ | ライセンスが明示された現行中古マンション個票が必要 | 東京全域の安定ID付き現行掲載を自由再利用できるデータは今回未確認。MLIT取引価格やREINS集計は掲載追跡の代替ではない | 依存なし。NII・有料データも必須にしない |

公開ページ、検索結果、robots設定は研究上の収集・長期保持・公開再配布の一括許可ではない。手動で少数読むことと定期取得の許可も区別する。提供者への連絡・申請・契約は今回行っていない。ライセンスの法的判断をプログラムが保証するものではない。

### データ構造と本人同定

保存は版付き `task010-v1` JSONジャーナル。入力バッチを保持し、状態・イベントは再計算する。各バッチ：`source`、媒体内一意の`batch_id`、`observed_at`、固定`scope_id`とその定義、`completeness`（complete/partial/failed）、確認根拠、`data_kind`、権利根拠。

各媒体掲載は `(source, listing_id)` で識別。提供元の実IDは任意の`source_record_id`、手動資料は自身が固定した`listing_id`を使う。内部の住宅IDは`property_id`。未指定なら媒体掲載から安定生成し、**似た面積・駅・価格だけで媒体をまたいで統合しない**。

既存住宅IDへ別掲載を結合するには`match_evidence`必須。原提供者の同一住戸キー、または棟だけでなく住戸まで確認した非個人的な資料の参照ID等を記載する。プログラムは文字列の真正性を確認できず、利用者の明示的な確認主張として保存する。住所・建物だけでの一致は不十分。既知の地域・面積・建築年が矛盾する新規結合は拒否する。同じ掲載IDでこれらが変われば`review_required`として住宅集約の確定判断を保留する。ID再利用への自動解決・修復リンクは本段階に含めない。

観測行は行政区、町名、最寄駅、駅アクセス分、面積、建築年または観測時年齢、間取り、構造、掲載総額、任意URL、状態・根拠・実掲載開始を保持。円/㎡はその観測行に価格と面積が両方ある場合に計算。最新表示の価格には`price_observed_at`が付く。未知値はnull/省略で、補完しない。電話、担当者、所有者名、画像、本文コピー等の専用入力欄はなく未知項目は拒否。自由文根拠にも個人情報を入れない。

URLは保持許可が必要。認証情報・query・fragmentを含むURLは受け付けない。権利メタデータには根拠区分（synthetic/manual_owned/provider_permission/open_license）、証拠参照、ローカル保持許可、URL保持許可を必須化。これは許諾の自動検証ではなく記録である。実データと合成ジャーナルの混合は拒否する。

### 時刻・観測の完全性

- `first_seen_at`：本システムが初めてpresentとして確認。実際の募集開始日ではない。
- `last_seen_at`：最後にpresentとして確認。失敗・欠落で更新しない。
- `first_listed_at`：提供者が明示した値だけ。日付のみなら日付精度のまま保持し、午前0時等を捏造しない。日付の比較は日本暦日、観測時刻はtimezone必須でUTCへ正規化。未知ならnull。
- `first_disappeared_at`：当該掲載の最初の確認済み非観測／明示終了の観測時刻。実終了時刻ではなく、最後のpresentとこの確認の間の不確実性が残る。`exact_end_at=null`。
- `last_successful_check_at`：個別の肯定／明示終了確認、または完全な追跡対象確認。単なる検索実行・失敗時刻ではない。

completeと申告しても普通の`filtered_search`からは消失を推定しない。価格や条件から外れただけの可能性がある。既知の対象IDを全件個別確認した`tracked_listing_ids`、または許可された完全フィード`entire_source_feed`で、同じ固定scopeのチェックがcompleteであった場合だけ欠落を`not_observed_complete`として記録する。部分結果・失敗・一時アクセス不可では`unknown_coverage`となり、消失イベントは作らない。同一scope IDの定義変更は拒否、新scopeの欠落を旧scopeの掲載終了としない。

完全性は入力者の根拠付き主張であり、実サイトの全ページ確認をソフトが保証するわけではない。未確認の新しいscopeでの失敗は旧scopeの掲載状態を変えない。最新根拠の観測時刻を必ず併記し、古いpresentを現在の確実な掲載と解釈しない。

### 状態と多媒体のイベント

媒体掲載状態：`present`、`not_observed_complete`、`provider_withdrawn`、`provider_sold`。後二者は提供者の明示的な根拠付き主張であり、真の成約日ではない。欠落をsoldに自動変換しない。記録された価格は上昇・低下・不変を検出し、属性更新も別イベントとして保存する。

同じ媒体の複数掲載がある場合、1件残れば媒体全体の消失とはしない。媒体内の全既知掲載が確定非観測/明示終了になった時点で`source_disappearance`を即時記録する。他媒体の消失を待たない。その最初が`first_source_disappearance`。媒体ごとに最初/最後のpresent、最初の消失、最後の成功確認を住宅レポートへ出す。

住宅の集約状態：一部媒体が非観測で別媒体がpresentなら`partial_disappearance`、全監視媒体が確定非観測/明示終了なら`full_disappearance`、未確認が残れば`unknown_coverage`。各媒体の最新根拠を非同期に集約した状態であり、同時刻の全市場調査ではない。`first_full_disappeared_at`と各媒体の初回確認差秒数も出すが、これは**チェック時刻差**であって真の掲載終了・成約時間差ではない。

同じ掲載IDの再presentは`reappeared`。新掲載IDの同住宅への結合は根拠付き`new_listing_linked`で、再掲載か別仲介掲載かの動機は推測しない。最初の消失時刻は保持、再出現後の新しい消失はイベント履歴で追える。再掲載間の真の空白期間や潜在的な未監視媒体は不明。

### 実行例（全て架空）

`examples/listing-tracking/`の順序で実行する。日付は架空シナリオの日時で、実行日・現実の市場観測結果ではない。最初のJSON例は架空住宅SYNTHETIC-HOME、架空媒体A/B。

```powershell
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.listings --store data/my-synthetic-tracker/journal.json import examples/listing-tracking/01-synthetic.json
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.listings --store data/my-synthetic-tracker/journal.json import examples/listing-tracking/02-synthetic.json
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.listings --store data/my-synthetic-tracker/journal.json import examples/listing-tracking/03-records.csv --metadata examples/listing-tracking/03-metadata.json
```

続いて04～07のJSONを番号順に同じstoreへimportする。`validate INPUT [--metadata META]`は保存せず検査のみ。CSVはUTF-8/UTF-8-BOM、空欄＝未知、1行1観測。JSONは1バッチ1オブジェクトで`records`配列を持ち、CSVはrecords以外をメタデータJSONへ置く。

```powershell
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.listings --store data/my-synthetic-tracker/journal.json history --property-id SYNTHETIC-HOME --output reports/my-synthetic-history
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

履歴出力はJSONとproperties/listings/snapshots/events CSV（ネスト値はJSON文字列）。出力フォルダの上書きを拒否。インポートは(source,batch_id)による冪等性を保証し、同じIDで内容が異なれば拒否。同一内容を別バッチIDで再投入しても増殖させない。時刻順入力が必要で、過去追加のための破壊的な並べ替えはしない。単一ライターlockと一時ファイルからの置換で不完全な書込を防ぐ。異常終了後のlockは実行中プロセス・バックアップを確認して人手復旧する。長期の巨大ジャーナルには全文再読込が重くなるので、本段階は小規模向け。

| 架空日 | 内容 | 検証結果 |
|---|---|---|
| 11/01 | A/Bで6,000万円 | 住宅は1つ、掲載IDは2つ |
| 11/02 | Aが5,900万円 | 価格低下イベント |
| 11/03 | Aの確認失敗 | 消失なし、確認不完全 |
| 11/04 | Aの対象ID全確認で欠落 | A消失を即時記録、住宅は部分消失 |
| 11/05 | Bが明示withdrawn | B消失、全監視媒体消失。初回確認差1日 |
| 11/06 | Aで5,800万円再出現 | 再出現、再度部分消失 |

7バッチ、6スナップショット、15イベント。失敗もバッチ・不完全イベントとして保存し、架空のpresent/掲載終了スナップショットを作らない。価格低下はA掲載内の6,000→5,900→5,800万円。これを実市場の研究結果として集計しない。

### 検証・今後

旧成果285ファイルのSHA-256一致を確認。全103テスト成功（既存87＋新規16）。価格変化・属性変化・開始日精度・ソース別初回/部分/全消失・1媒体複数掲載・再出現・根拠なし結合拒否・識別矛盾・失敗/部分/検索範囲・冪等性・競合・CSV/JSON一致・実CLI出力・ロックを確認。`reports/listing-tracking-010-final/`は架空実行のローカル証跡。原データと完全履歴はdata/reports内でGit無視、公開対象はプログラム・合成例・テスト・文書のみ。

次は利用許可が明確な小規模ウォッチリストを一定周期で継続し、失敗・未監視期間・識別判断・対象加入/退出を保存する。観測開始前の掲載期間は左側が不明、継続中は右打切り、消失は区間不明かつ理由混合。初回媒体消失と全媒体消失を別endpointとして将来検証し、成約と撤回を区別できる提供者情報を増やす。標本数だけでなく対象選択・周期・成功率・同一住戸確認率を確認する。現段階で売却確率・ランキングは出さない。

### 最終レビュー補足（2026-11-08）

通常の価格変化、JSON/CSV一致、再投入の冪等性、first_seenとfirst_listedの分離を維持したまま、以下の境界条件を修正した。

- 同一媒体の複数掲載を別々の部分確認で終了確認した後、完全確認で初めて媒体全体の消失が確定する場合、媒体イベントが欠落していた。最後の確定済み媒体状態を保持し、その完全確認時刻で記録する。単なる失敗からの復帰で既存消失を重複計上せず、再出現後の別消失は新イベントにする。
- 空欄の未知CSV列・不正表頭を行の有無にかかわらず拒否。空の誤形式CSVを完全な無掲載結果と扱わない。scope掲載IDの周辺空白を正規化し重複を拒否。権利オブジェクトの型を検査する。
- 同定がreview_requiredの住宅への追加結合を拒否。建築年と年齢の整合検査はUTC年ではなく日本暦年を使用する。年齢は本形式では「観測年−建築年」の年差であり、誕生日・竣工月による満年齢ではない。提供元が満年齢ならこの項目へ無変換で混在させず、建築年のみを入力する。
- CLI helpとimport/validate結果に手入力でも許諾が必要な旨を表示。helpは今回取得実掲載0件・同梱合成例を明示。historyのdata_summaryは実／合成の観測行数であり、ユニーク住宅数ではない。住宅絞込み時も対象行だけを数える。

6件の回帰テストを追加（Task 010計22、全体109）。最初の実行ではhelp自動折返しに対する文字列テストだけが失敗し、空白を正規化する検査へ修正した。最終の全109テストは7.728秒で成功。旧成果285ファイルのハッシュ一致、旧追跡対象ファイルの変更はREADMEのTask 010リンクのみ、既存合成例は7バッチ・6スナップショット・15イベント・実観測行0を再確認した。既存の実行証跡は上書きせず、今回のログと監査JSONはGit無視の`reports/listing-tracking-010-review/`へ保存した。Commit/Pushなし。

Git無視はdata/reports/models内のローカル資料に適用される。任意のCLI出力先まで保護する機能や自由文の個人情報自動検出機能ではない。必ず無視対象内へ保存し、根拠は個人情報を含まない参照IDにする。公開候補はコード・テスト・架空例・本書・READMEリンクのみ。元の103件成功という記載は初回開発時の記録として保持する。

## English

### Scope and source feasibility

Task 010 adds a standard-library-only local JSON/CSV journal, price/attribute changes and multi-source disappearance/reappearance. **No real listing data was acquired. All runnable examples are explicitly synthetic**, including their fictional observation dates. No existing model or Task 001–009 result was replaced; no commit or push.

Official sources checked on 2026-11-08 are linked in the Japanese table. SUUMO limits unapproved use beyond the stated private-use scope; this does not grant general research collection rights. HOME'S terms restrict unapproved content reuse, while its official data-solution service offers a formal inquiry route with negotiable fields/volume/pricing. Update cadence, stable IDs, historical retention and termination notices require agreement. At home's official page carries a no-unauthorized-reproduction notice; the full page returned 405 to the tool, so full terms and public API permissions remain unverified. No access restriction was bypassed.

Manual input and user/provider CSV/JSON are viable only with documented rights. Receiving a file or manually copying a page does not itself authorize reuse. No freely reusable, comprehensive Tokyo current-condominium listing feed was established. MLIT transactions and REINS aggregates are different data products. Neither NII nor commercial purchases are dependencies. No provider contact, contract or API-key use occurred.

### Identity, schema and evidence

Versioned batches retain source, batch ID, observed time, immutable scope definition, complete/partial/failed outcome, check evidence, synthetic/real kind and retention rights. Source listings use `(source, listing_id)` independently of internal dwelling `property_id`; optional original IDs and permitted URLs are retained. Without a supplied dwelling link, source-isolated IDs are generated deterministically. Linking a second listing requires explicit match evidence, not similarity in price/area/station. Evidence is a user assertion that software cannot authenticate. Conflicting known locality/area/construction-year links are rejected; changes to those fields under one ID flag identity review and withhold dwelling-level certainty.

Observations support municipality, town, station/access minutes, area, age or construction year, layout, structure, asking price, per-row unit price, status and evidence. Unknowns remain unknown. Contacts, owners, images and full ad text have no accepted fields; free-text evidence must also exclude unnecessary personal information. URLs require retention permission and cannot contain credentials, query tokens or fragments. Real and synthetic journals cannot mix.

`first_seen_at` is our first confirmed presence, not the actual listing start. `last_seen_at` advances only on presence. `first_listed_at` requires explicit source evidence and preserves date-only precision; observation timestamps require timezone and normalize to UTC. First disappearance is a check timestamp, with an unknown end between last presence and the check; no exact sale/end date is generated. Latest prices carry their observation timestamp. Source-start conflicts remain visible in history.

### Absence and multiple platforms

Missing rows imply confirmed non-observation only after a successful complete check of fixed tracked listing IDs or a genuinely complete authorized source feed. Ordinary filtered searches, partial results, failure and temporary access problems do not establish disappearance. Scope definitions cannot silently change. New-scope omissions do not remove old-scope listings. Completeness is an evidenced importer assertion, not a software guarantee that a website was exhaustively checked.

Listing states distinguish presence, complete-check non-observation, provider-reported withdrawal and provider-reported sale. Provider claims are not independently verified sale dates. Per-source disappearance is emitted immediately once all monitored listings for that dwelling on that source are absent; one remaining listing prevents premature source-level disappearance. First-source, partial and full disappearance are separate events. Full means all monitored sources, not all possible platforms. Reports expose each source's first/last presence, first disappearance and last successful check, plus first full disappearance and differences between first source-check timestamps.

Checks are asynchronous; current aggregate states summarize latest evidence, not a simultaneous market census. Missing coverage or identity uncertainty withholds a full-disappearance conclusion. Reappearance of the same ID and a verified new-ID link are separately recorded. Their underlying reason—sale, withdrawal, broker change or relisting—is not inferred. Check-time lags are not true removal or sale-time lags.

### Running, outputs and validation

Run numbered fixtures in `examples/listing-tracking/` in order using the commands above. Fixture 03 demonstrates CSV plus metadata; all others use JSON. CLI provides `validate`, `import` and property-filtered `history`, exporting JSON and four CSV tables. Preserve explicit synthetic labels. The seven-batch example produces six observation snapshots and 15 events: A falls from ¥60m to ¥59m, a failed check does not remove it, A disappears first, B later reports withdrawal, and A reappears at ¥58m. The first source-check lag is one day. These are invented software demonstrations, not market observations.

Repeated canonical batches are idempotent; conflicting IDs, out-of-order input and real/synthetic mixing fail before journal replacement. Writes use a single-writer lock and temporary-file replacement. Existing export folders are refused. The journal is intentionally small-scale and replayed in full; large-scale storage, automatic acquisition, scheduling and correction/rematching tooling remain future work. Inspect interrupted locks and backups before manual recovery.

All 285 pre-existing artifact hashes match. All **103 tests pass: 87 existing plus 16 new**. They cover prices, attributes, source-start precision, multi-platform events, multiple listings per source, reappearance, ambiguous/conflicting identity, failed/partial/changed coverage, idempotency, atomic rejection, CSV/JSON parity, actual CLI export and locking. Local synthetic evidence is in `reports/listing-tracking-010-final/`; raw data and full histories remain Git-ignored. Public candidates are only code, synthetic examples, tests and documentation.

Future liquidity research requires a permitted fixed watch list, consistent observation intervals, coverage/failure logs, reliable dwelling links and reasons supplied by providers. Pre-observation listing duration is unknown, ongoing records are right-censored, and disappearance intervals combine different causes. Study first-source and all-monitored-source endpoints separately without labelling either a sale date. No sale probability or combined value ranking is produced now.

### Final review addendum (2026-11-08)

The review preserved price tracking, JSON/CSV parity, idempotency and separation of observation/listing-start dates. It fixed a missed source disappearance when separate partial checks confirmed individual withdrawals and a later complete check first established that all listings on that source were absent. The last definitive source state now distinguishes first confirmation, failure recovery without duplicate events, and a new disappearance after reappearance.

CSV headers now reject unknown columns even when blank or header-only, so malformed empty input cannot imply complete absence. Scope IDs are whitespace-normalized with duplicate rejection; rights must be an object. New links to dwellings under identity review are refused. Construction-year/age validation uses Japan's calendar year: age here means observation-year minus construction-year, not completed years based on a completion month. Supply construction year alone when the provider's age convention differs.

CLI help and import/validate output disclose that manual entry does not grant rights. Help explicitly identifies zero real listings acquired for Task 010 and synthetic bundled examples. History reports actual real/synthetic observation-row counts, including property-filtered counts; these are not unique dwelling counts.

Six regression tests were added (22 Task 010 tests, 109 overall). The first run failed only a help-text assertion due to automatic line wrapping; the assertion now normalizes whitespace. The final full suite passed all 109 tests in 7.728 seconds. All 285 old artifact hashes still match; the only tracked-file change is README's Task 010 links. The original demonstration still produces seven batches, six snapshots, 15 events and zero real observation rows. Prior outputs are preserved; final logs and audit JSON are in ignored `reports/listing-tracking-010-review/`. The earlier 103-test statement remains the original development record. No commit or push.

Git ignores data/reports/models, not arbitrary user-selected export locations. There is no automatic personal-data detector for free-text evidence. Use ignored destinations and non-personal evidence reference IDs. Public candidates remain code, tests, fictional fixtures, this document and README links.
