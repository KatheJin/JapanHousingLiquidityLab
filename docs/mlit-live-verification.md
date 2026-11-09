# XIT001実接続・資格情報検証 / Live API and Credential Verification

## 日本語

2026-11-09、ユーザーが保存したrootの.env.mlit-localを使用し、既存mlit_clientとnet_httpを通じて実接続した。APIキーを会話や別ファイルへ転記せず、出力・ログ・Gitへ保存していない。SUUMOの採集とは別のHTTPS接続・ローカルdirectoryを使い、PGへの取引データ投入や価格モデル更新はしていない。

### 実際の要求と応答

[公式XIT001仕様](https://www.reinfolib.mlit.go.jp/help/apiManual/xit001)に従い、千代田区city=13101、2023Q1、language=jaを同じ条件として比較した。01は不動産取引価格情報、02は成約価格情報であり、どちらも現在の売出価格ではない。URLに資格情報は含まない。

|priceClassification|HTTP|全record|中古マンション等|PriceCategory|完全一致行重複|
|---|---:|---:|---:|---|---:|
|01|200|77|60|不動産取引価格情報|0|
|02|200|63|63|成約価格情報|0|

01の残りは宅地(土地と建物)14、宅地(土地)3。各分類のschemaは同じ29field。分類・市区町村でファイル名を分け、02が01の取得済みquarterに誤ってskipされないことを実証。両manifestを再読込みした再実行はHTTP 0回でSHA検査を通過した。

成功した2 GETは既存HTTPS transportで通常TLS検証、gzip解凍、timeout30秒、間隔10秒、retry上限1、redirect追跡なし。実測は2 attempts、失敗0、retry0。間隔は保守的なローカル設定であり、公式許可頻度の主張ではない。[公式API案内](https://www.reinfolib.mlit.go.jp/help/apiManual)は間隔を空けた要求を求めている。

### 品質（中古マンション等のみ）

|欠損field|01 / 60件|02 / 63件|
|---|---:|---:|
|市区町村・地区名・面積・価格・取引四半期|各0|各0|
|建築年|1 (1.67%)|2 (3.17%)|
|間取り|10 (16.67%)|0|
|構造|1 (1.67%)|2 (3.17%)|
|最近駅・駅徒歩時間|field自体なし|field自体なし|

価格・面積は全140行で正の正確な数値として読めた。これは外れ値が無い、価格が未丸め、物件品質が均一という意味ではない。どの行も削除していない。自治体code・取引Periodは要求と一致。取得日時と取引四半期は分離し、publication_dateは未知のまま。2023年当時の公開版を取得したという意味ではない。

PriceCategoryを除いた全field一致は分類間で0件。ただし安定した取引IDはなく、01と02が独立した取引集合とは証明できない。自動統合・重複削除・件数合算による市場全数推定はしない。APIには駅関連fieldが無く、既存CSVの駅featureを置換・推定埋めしない。今回は1区1四半期の接続試験で、東京都全域や全期間の取得完了ではない。

### 実証した資格情報の取扱い

- 第一優先は環境JHLL_REINFOLIB_API_KEY、旧REINFOLIB_API_KEYは互換用。無ければ.env.mlit-localの同名変数を読む。ファイル利用時はGit無視・未追跡を必須とし、重複定義や改行等の不正値は値を表示せず拒否する。
- 実接続processには両環境変数が無い状態を確認してから、私有ファイル経路で認証成功。環境優先・不正値・追跡済み設定の拒否はダミー資格情報だけでテストした。実キーを別の環境や設定へコピーして試験していない。
- 秘密はHTTPSのOcp-Apim-Subscription-Key headerのみ。request logはpath/status/elapsed/bytes等に限定し、headerやキーは含まない。条件cacheを無効化し、request本文cacheは作成していない。応答に資格情報が含まれる場合は保存を拒否する。
- 実キーをメモリ上だけで生成物・公開候補と照合し、非混入を確認。キーそのもの・hash・末尾文字等を証跡へ記録しない。保存するSHA-256はデータファイルのhashでありキーのhashではない。

これは会話経由の秘密受け渡しとGit混入を避ける仕組みであり、平文設定の暗号化、OS権限の隔離、実行processからの秘密隔離は実装していない。AI補助開発でもキーが必要なprocessは実行時にそれを読み取る。匿名化された結果の公開再利用は別途データ利用条件を確認する。

### 保存場所・再実行

Git無視のdata/mlit-live-verificationに分類別JSONとmanifest、reports/mlit-live-verificationにresults.json（欠損率・型・flag）、comparison.json、request metrics、credential-safety.jsonを保存。認証header・秘密は保存しない。既存のCSV／API／模型directoryを上書きしない。旧xit001.pyの未接続stubは互換のため変更していない。

```powershell
# data/mlit-live-verification/published.json に ["2023Q1"] を管理者が保存
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.mlit_client --published data/mlit-live-verification/published.json --classification 01 --city 13101 --directory data/mlit-live-verification
.venv/Scripts/python.exe -m japan_housing_liquidity_lab.mlit_client --published data/mlit-live-verification/published.json --classification 02 --city 13101 --directory data/mlit-live-verification
```

キーを引数へ渡さない。acquired.jsonを使う場合は選択分類・地域に一致する取得済みquarterだけを列挙する。404は未公表または該当なしとして保留し、取得済み・0件にはしない。

完全回帰テスト184件成功、skip 0、54.721秒。資格情報に関する試験は全てダミー値を使用し、実API要求は上記2回だけ。最終scanでも実キーの生成物・公開候補への非混入を確認。旧303成果hashと元PG snapshot/batch/event/requestは保持。SUUMOの中央worker／writer lockが稼働中で、最終監査時には成功1,026 ID・1,028 snapshot・旧失敗2件へ増加していた。API試験の取引データをPGへ混入させていない。詳細証跡はreports/mlit-live-verification/final-safety-audit.json。Commit/Push/配備なし。

## English

On 2026-11-09 the existing XIT001/net_http client authenticated using the user's ignored root .env.mlit-local file. The same Chiyoda municipality (13101), 2023Q1 and Japanese output were requested for classifications 01 and 02. Both returned HTTP 200: 01 has 77 records including 60 used condominiums; 02 has 63, all used condominiums. PriceCategory matches each requested classification. These are transaction/contract data, not current listings.

Both responses contain the same 29 fields and zero exact duplicate rows. Among condominiums, construction-year/structure missing counts are 1/60 for 01 and 2/63 for 02; layout is missing in 10/60 for 01 and 0/63 for 02. Municipality, district, area, price and period are complete. Neither response contains station/walking-time fields. All 140 price/area pairs were positive exact numerics; this does not establish absence of outliers or rounding. No rows were deleted. Cross-classification exact matches excluding PriceCategory are zero, but no stable transaction ID establishes independence. Do not automatically combine/deduplicate these sources or replace CSV station features.

Only one municipality/quarter was tested. Acquisition time is distinct from trade time; publication dates and historical release versions remain unknown. The existing verified-TLS/gzip client made two successful attempts with no retries, ten-second spacing, bounded timeouts/retries and no redirects. Reusing both stored manifests generated no additional HTTP requests.

Environment JHLL_REINFOLIB_API_KEY has priority; the legacy name remains compatible. Otherwise the loader requires the private file to be ignored and untracked, rejects duplicate/invalid values without echoing them, and does not export file values to child environments. Real authentication used the private-file route with both environment variables absent. Environment precedence and failure cases use dummy credentials only in tests.

The key is sent only in the HTTPS authentication header, not query parameters, logs, cached request bodies, reports or Git. Credential-bearing responses are refused before persistence. Generated results/public candidates were checked in memory against the actual key; neither key values nor fingerprints were recorded. This reduces chat/Git exposure; it is not encrypted storage or isolation from the executing process/AI tools.

Ignored data/mlit-live-verification holds classification/city-scoped JSON and manifests; reports/mlit-live-verification holds quality, comparison, request metrics and credential-safety evidence. Existing datasets/models and the legacy stub remain intact. Use the commands above with a locally created published-quarter list; never supply credentials as CLI arguments. Acquired inventories must match the selected classification/region. Missing responses are not zero transactions. No model retraining or deployment.

All 184 regression tests passed without skips in 54.721 seconds; credential tests use dummy values. Only the two documented live API requests were sent. Final scans found no actual key in outputs/public candidates. All 303 old artifact hashes and original PG snapshot/batch/event/request rows were preserved. SUUMO's central/writer locks remained active; it had grown to 1,026 successful IDs, 1,028 successful snapshots and the two retained failures at the final audit. API trade data was not inserted into the listing DB. No commit, push or deployment.
