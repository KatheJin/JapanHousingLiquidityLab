# データ取扱い / Data guide

## 日本語

`data/raw/` に利用許諾を確認済みの CSV を手動配置してください。元ファイルは変更しません。
本リポジトリには実データを同梱せず、NII、API キー、スクレイピングを必要としません。
データ提供元、取得日、対象期間、地域、利用条件、文字コードを各入力とともにローカルに記録してください。

検査コマンドは UTF-8（BOM 可）、CP932 の順で厳密にデコードします。必要なら `--encoding` で指定します。
列の意味やデータ型は推測せず、全行を逐次検査します。ヘッダー重複・空欄・空ファイルはエラーです。
完全な空行は除外し、列数不一致行は別集計します。欠損は正常な列数の行における空文字・空白のみを数えます。
`NA` 等の表記、数値の妥当性、単位、スキーマ適合性は別途確認が必要です。実データの行内容は出力しません。
CSV の列構成は提供時期によって異なり得るため、実際のヘッダーを確認してから変換処理を追加します。

将来の掲載観測の候補項目: `listing_id`, `observed_at`, `asking_price_jpy`, `status`, `source`, `first_seen_at`, `last_seen_at`。
識別子は再掲載と物件単位を区別し、時刻にはタイムゾーンを保持します。下架理由が不明なら成約とラベル付けしません。
ローカルデータ・モデル・レポート・秘密情報は Git で無視します。共有が必要な派生集計は公開可否を確認して選択します。

## English

Manually place authorized CSVs in `data/raw/`. Input files are never modified.
No real dataset is bundled. NII, API keys, and scraping are not required.
Keep source, acquisition date, coverage period, region, usage terms, and encoding with each local input.

The inspector strictly decodes UTF-8 (optional BOM), then CP932. Use `--encoding` to override.
It streams all rows without guessing column semantics or types. Duplicate/blank headers and empty files are errors.
Entirely empty lines are skipped. Rows with incorrect field counts are reported separately.
Missing counts cover only empty or whitespace cells in correctly sized rows; NA markers, numeric validity, units, and schema compliance require separate checks.
No individual records are printed. Inspect actual headers before adding version-specific transformations.

Future observation fields may include `listing_id`, `observed_at`, `asking_price_jpy`, `status`, `source`, `first_seen_at`, and `last_seen_at`.
Distinguish relisting identifiers from property identity and preserve timestamp timezones. Unknown disappearance reasons must not be labeled as sales.
Local data, models, reports, and secrets are ignored by Git. Review derived summaries before selecting them for publication.
