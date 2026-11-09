# HOME'S HTTP 403 調査 / HTTP 403 Investigation

## 日本語

2026-11-09。**現在の通常HTTP collectorでは、HOME'Sを持続的な第二の実掲載sourceとして有効化できない。** 7回の限定GETでrobotsのみ200、残る6 URLは403。実掲載取得0、PG追加0。検索サービスの表示情報を実観測に転用していない。

### 実際のネットワーク結果

要求開始はUTC 09:22:00～09:23:25（JST 18:22:00～18:23:25）。Python Requests、公開UA `JapanHousingLiquidityLab/0.2 (limited public page verification)`、TLS検証有効、接続10秒・読取り20秒timeout、同一URL再試行0、10秒以上の間隔。redirectは追跡せず、認証・cookie移植・proxy切替・UA偽装は行わない。各URLは一度だけ確認。下記は全て `https://www.homes.co.jp` 上。

|パス|種類|HTTP|展開後bytes|秒|
|---|---|---:|---:|---:|
|`/robots.txt`|robots|200|6,210|1.531|
|`/mansion/chuko/tokyo/list/?page=1`|東京都一覧|403|919|0.828|
|`/kiyaku/`|利用規約|403|919|0.797|
|`/sitemap-bukken-detail-mansion-chuko.xml`|robots公開の中古マンション詳細sitemap|403|919|0.750|
|`/sitemap-mansion-chuko-town-list.xml`|robots公開の町別一覧sitemap|403|919|1.046|
|`/mansion/chuko/tokyo/chuo-city/list/`|中央区一覧|403|919|0.859|
|`/mansion/b-1473060002259/`|検索で確認した詳細1件|403|919|0.766|

robotsのContent-Length 1,010はgzip転送長で、上表の展開後長と異なる。robotsは今回の対象パスを禁止していない。大量sitemap巡回・ページング・別経路の探索は行わず、確認した拒否を尊重して停止した。robots許可は保存・再配布の許諾ではない。

6つの403はいずれも `Server: CloudFront`、`X-Cache: Error from cloudfront`、`Via: ...cloudfront.net (CloudFront)`、`X-Amz-Cf-Pop: NRT12-P2`。HTMLはCloudFront生成の汎用エラーで、短い診断文は **Request blocked.**。Location・Retry-After・WWW-Authenticate・Set-Cookieは今回の応答に無く、3xx、ログイン画面、captcha画面、JS challengeは観測していない。captchaが無いことは自動アクセスが許されることを意味しない。応答ごとのRequest ID、取得UTC時刻、SHA-256、応答headerと拒否本文はGit無視の `reports/homes-diagnostics/requests.json` に保存。

### 原因をどこまで確定できるか

CloudFront配信経路と、その経路上で返された拒否応答は確認できる。listingの本文やアプリ固有のエラーには到達していない。**AWS WAFが原因と断定できない**。[AWS公式403説明](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/http-403-permission-denied.html)は、WAF、origin、地理的制限、署名設定、distribution設定等を候補としており、CloudFrontはWAFとorigin由来の403をステータスだけで識別できないと説明する。本調査のheader/bodyだけではIP・地域・UA・TLS特性・アクセスルールのどれが原因か、またoriginへ転送されたかは不明。汎用本文の混雑／設定不備という案内も原因確定の証拠ではない。

根本原因の確定には運営側のCloudFront/WAF/originログが必要。運営に確認する場合は今回のUTC時刻、正確なURL、UA、Request IDを渡し、研究用低頻度アクセスまたは正式なデータ提供方法を相談する。ユーザーへの連絡・申請は本作業では送信していない。CloudFrontの裏側・別host/IP・署名・認証等を探索しない。

### 検索サービスで見えた情報との区別

公開Web検索／閲覧サービスでは[東京都一覧](https://www.homes.co.jp/mansion/chuko/tokyo/list/?page=1)、[中央区一覧](https://www.homes.co.jp/mansion/chuko/tokyo/chuo-city/list/)、[詳細](https://www.homes.co.jp/mansion/b-1473060002259/)のテキスト表示が得られた。これは**本機Requestsが取得したHTMLではない**。検索側のclient、cache、更新時刻は本機と同じと確認できない。この表示経路をcollectorの代替に使わない。

詳細表示には価格、専有面積、築年月、間取り、駅・徒歩分、構造、HOME'S物件番号のラベルが存在する。調査対象表示は81.2㎡、2005年8月、2LDK、天王洲アイル徒歩12分、RC、番号0147306-0002259で、URL数値部とは先頭ゼロ／区切りが異なる。IDは文字列として保持する必要がある。ただし住戸の永続ID、同一住戸の別仲介掲載、再掲載時のID安定性は未検証。掲載番号を建物または住戸の普遍IDとしない。

同じ詳細の検索表示は情報有効期限2026-07-04で、本調査日より古い。一覧と詳細の表示価格にも不一致があり、同じ版と扱えない。動的な「○時間前」表記も実取得時刻の証拠にしない。したがって価格例や検索テキストを「現在の実掲載」としてPGへ保存しない。新たなDOM selector、HTML parser、pagination、詳細field completenessは実HTML未取得のため未検証。既存HomesDiscoveryは原型のままで、production対応を主張しない。

### 利用条件と代替経路

検索経由で[公式規約](https://www.homes.co.jp/kiyaku/)も読めた。第6条は権利の留保と無断使用等の制限、第16条には営利目的・サービス妨害等の制限がある。robotsだけから商用・公開サービスへの再利用許諾を推定しない。本調査はあらゆる事実情報の研究利用が一律禁止という法的判断をしていない。技術的な403と利用条件の検討を区別する。

実行可能性が確認できる継続sourceは既存の限定SUUMOのみ。[LIFULL公式データソリューション](https://data-solution.homes.jp/)は、希望項目のデータ提供と定期更新を案内しており、第二sourceとしてはこの正式経路の条件確認を優先する。見積・契約・対象地域／中古売買／掲載ID／更新周期／保存・公開権限の確認が必要。公開無料API、取得済みfeed、接続済み契約ではない。問い合わせは送信していない。

at homeは既存調査の明示的crawler制限を維持。MLITの公式APIは成交情報であり、現在の掲載feedの代用にはならず、KeyもPending。第三者scraper業者の宣伝は許諾の証拠として採用しない。**今回、無料で通常collectorから継続利用可能な第二の現在掲載sourceは確認できなかった。** NIIを導入条件にしない。

### 保全・検証

本作業は診断と文書だけ。既存collector、PG schema、SUUMO処理、モデルは変更していない。全主庫テーブルを以前の検証済み復元DBとread-only照合し一致。SUUMO成功33 ID、成功35＋失敗2＝37snapshot、35event、HOME'S snapshot 0。旧303成果hashも一致。証跡は `reports/homes-diagnostics/database-preservation.json`、ネットワーク原記録は上記requests.json。いずれもGit無視。Commit、Push、配備なし。

回帰検証は全175テスト成功、skip 0、50.285秒。実PGテストは専用jhll_testのみで、第三者サイトの新たな要求はテスト中に行わない。ログは `reports/homes-diagnostics/all-tests.txt`。git diff --check、資格情報非混入、診断証跡のGit無視も確認。

## English

On 2026-11-09, seven bounded ordinary Requests GETs confirmed robots 200 and six CloudFront 403 responses for Tokyo/Chuo lists, terms, two robots-advertised sitemaps and one search-discovered detail. Exact paths, sizes and timings are tabulated above. Requests used the disclosed project UA, verified TLS, 10/20-second timeouts, no redirect following, at least ten-second spacing and no repeated URL attempts. No authentication, cookie transfer, impersonation or proxy switching was used. Acquisition stopped after these diagnostic checks.

The rejection responses carry Server CloudFront, Error from cloudfront, CloudFront Via/POP/request IDs and a generic generated error body. No Location, Retry-After, WWW-Authenticate or Set-Cookie appeared; no redirect/login/captcha/JS challenge was observed. This establishes the delivery path and denial, not an exact WAF/IP/geo/UA cause. [AWS documentation](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/http-403-permission-denied.html) explains that multiple configurations, WAF and origin responses can produce 403. Definitive attribution requires operator-side logs. The local ignored JSON retains timestamps, request IDs, headers, hashes and denial text for a possible operator inquiry; none was sent.

Search-service text exposes list/detail labels for price, area, construction date, layout, station/walking time, structure and a source listing number. It is not locally acquired listing HTML. The selected detail's displayed validity date is 2026-07-04; list/detail prices disagree, so their versions cannot be assumed equal. Source number 0147306-0002259 differs in leading-zero/separator formatting from the URL token. Treat IDs as strings; room/building identity and stability across agents/relisting remain unverified. No selectors, pagination or field-completeness claims were validated against live collector HTML.

**Actual HOME'S listing acquisitions and PG inserts: zero.** Search text was not imported or used as a substitute feed. The existing unverified discovery prototype remains disabled as a production source. Robots permission alone grants no reuse rights; the [terms](https://www.homes.co.jp/kiyaku/) retain rights and restrict certain uses. This is not a blanket legal ruling against all factual research use.

HOME'S is not currently a sustainable second source for this collector. Further repeated technical probing is not recommended. The [official LIFULL data-solution service](https://data-solution.homes.jp/) offers tailored data and recurring provision; licence, cost, scope, source IDs and update/retention/publication rights require confirmation. This is an available negotiation route, not a connected/free public API. Existing limited SUUMO collection remains the only verified operational listing source here. at home's restriction remains; MLIT transaction data cannot replace current listings, and its key is pending. No free second current-listing feed was verified and NII is not required.

Read-only comparison against the previously verified restore confirmed every primary table unchanged: 33 successful SUUMO IDs, 35 successful/two failed observations, 35 events and zero HOME'S snapshots. All 303 old artifact hashes match. No collector, schema or model logic changed. Evidence stays ignored under reports/homes-diagnostics. No commit, push or deployment.

All 175 regression tests passed without skips in 50.285 seconds, with PG tests confined to jhll_test and no new third-party requests during tests. The separate log is reports/homes-diagnostics/all-tests.txt. Diff checks, ignored evidence and credential exclusion passed.
