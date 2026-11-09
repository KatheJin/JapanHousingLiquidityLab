# 新版MVP 最終機能確認 / Final MVP acceptance

## 日本語

ユーザーによる最終確認後、この13ファイルを研究型MVPの安定チェックポイントとして正式Commitする。以下の「未Commit」等は機能審査時点の記録であり、提出準備・再試験はGit履歴で追跡する。地区価格比較の未検証状態は変えない。

2026-11-10。判定：**ローカル・私的利用の機能確認は通過。地区価格の同等性や順位の信頼性は未検証。** 新規モデル、再学習、正式な価格調整、公開配備は追加しない。Phase 4のPush済み `e984566` 以降のPhase 5と今回修正は未Commit・未Push。

### 候補の区分と実取引の裏付け

既存三Ridge・2026Q2共通住宅属性は維持。行政区＋駅を市場単位とし、面積・建築年/房齢・間取り・構造・徒歩分は同一。正式参考価格・差・推奨順位は引き続きnull/利用不可。研究診断と未調整の実取引分布は別フィールド・別ラベルにする。

説明用の固定区分は次のとおり。検証済みの統計的同等性の閾値ではなく、結果を分類する記述的な規則である。

1. **複数モデルが近い価格水準を示す**：三モデルの対象との差が各±10%以内、最大差−最小差が5ポイント以内、直近共同属性記録10件以上。
2. **モデルによって判断が分かれる**：直近記録は10件以上あるが上のモデル一致条件を満たさない。
3. **直近の比較記録が不足**：直近共同属性記録が10件未満。数値が一致してもこの区分を優先し、`model_agreement` の診断自体は保持。

既存の市場30件・共同属性10件という全期ゲートは変更しない。全期は2023Q1–2026Q2、直近は2025Q3–2026Q2。共同属性は面積±20%、2026Q2基準房齢±10年、間取り・構造一致、正確な徒歩±5分。対象と候補の条件は同じ。2018–2022の拡張件数で適用範囲を広げない。価格の有限正値が10件未満なら中央値・四分位数を抑制し、有効・無効数は残す。異常値や原記録は削除しない。

三軒茶屋25㎡・2005年築・1K・RC・徒歩10分では18候補のうち一致かつ直近支持十分0、モデル不一致2（初台・池袋）、直近不足16。うち6地域はモデル診断が比較的近いが直近不足である。対象自身も直近3件しかない。条件を緩めて「おすすめ」を作らない。

以下は地区比較用の条件帯で抽出した**未調整の実成約単価**。標準化モデル価格でも信頼区間でもない。期間と未観測品質の違いが残り、分布の重なりは地域市場価格の同等性を証明しない。

| 地域・駅 / Market | 全期 / 直近 n | 原単価中央値 万円/㎡ | Q1–Q3 万円/㎡ | 実際の記録期間 |
|---|---:|---:|---:|---|
| 世田谷区・三軒茶屋 | 30 / 3 | 124 | 110–134.25 | 2023Q1–2025Q3 |
| 中野区・中野(東京) | 16 / 5 | 127.5 | 118.75–137 | 2023Q2–2026Q2 |
| 品川区・不動前 | 11 / 4 | 125 | 117.5–142.5 | 2023Q1–2025Q4 |
| 品川区・大井町 | 26 / 7 | 132.5 | 125–143.75 | 2023Q1–2026Q1 |
| 文京区・後楽園 | 15 / 0 | 120 | 115–127.5 | 2023Q1–2025Q2 |
| 文京区・茗荷谷 | 33 / 8 | 120 | 115–125 | 2023Q1–2026Q2 |
| 渋谷区・笹塚 | 10 / 0 | 125 | 117.5–136.25 | 2023Q4–2025Q2 |

対象に対し、原中央値の差は中野+3.5、不動前+1、大井町+8.5、後楽園−4、茗荷谷−4、笹塚+1万円/㎡。モデル上は近くても原分布の中心は同じではない。例えば大井町の主モデル診断は対象比−2.69%だが、原中央値は+6.85%。これは同時期・完全同品質の比較ではなく、モデル差を独立検証したことにはならない。直近不足の四分位数は表示しない。

二子玉川70㎡・2005年・3LDK・RC・徒歩10分は共同属性6件、直近1件のまま、`unavailable` と空候補を維持。詳細な原単価分布も抑制する。三モデル上位集合の一致度や旧2025開発誤差は研究情報であり、新しい独立試験・校正済み区間とは呼ばない。

### 一入力の実ブラウザ確認

既存 `127.0.0.1:8501` の実Streamlitで住宅を一度入力し、順番に①歴史記録、②同地域掲載、③研究候補と候補地域掲載を操作。対象は世田谷区・三軒茶屋25㎡・2005年・1K・RC・徒歩10分・3,000万円、参考日2026-11-10。

歴史記録106件（2018–2022:66、2023–2026:40）は維持。実一致期間2018Q1–2026Q1、原単価中央値120万円/㎡・中央50%105–130万円/㎡。上表の30件とは期間・房齢・徒歩条件が異なることを画面に明記。取得済み2026Q2の未収録取引・改訂可能性と、当該条件の一致がないことを区別する。正式調整不可は他の機能を妨げない。

同地域・候補地域とも2一覧・2詳細の有界設定で明示クリック。初回地区比較と候補の選択だけではHTTPなし。共有限速・既存ジョブ/スナップショットを再利用し、長期collectorは起動しない。

| 検索地域 | 一覧 / 発見ID | HTTP | 実行秒 | 今回厳格 / 近似 | 関連する旧観測 |
|---|---:|---:|---:|---:|---:|
| 世田谷区・三軒茶屋 | 2 / 40 | 5 | 42.5 | 1 / 0 | 0 |
| 中央区・茅場町 | 2 / 40 | 4 | 34.4 | 0 / 0 | 2 |

全9HTTPは200。どちらも一覧の続きがあり部分検索。開始・確認時点はJSONにUTCで保存（今回JST04:57–04:59頃）。ページ順は変わり得るため前回の20ページ検索と同一範囲ではない。

世田谷では既知IDの新観測1件を取得。価格4,280万円、25.11㎡、2012年築/年差14年、三軒茶屋徒歩8分、1K、RC。原ページリンク・観測日時・170.45万円/㎡を実画面で確認。入力3,000万円を超えても除外していない。新しい住宅ID発見とは数えない。

中央区・茅場町のクリック後も元住宅入力は三軒茶屋のまま。直近1時間以内の詳細を再取得しない既存方針により、今回詳細確認は0、以前の関連観測2件は旧観測として展開できる。今回の厳格/近似0に加算しない。40発見IDのうち39に過去観測があるという総数と、条件に合う2件を区別。過去の2件を今回の新しい成功取得とは報告しない。0件を地域の在庫0とは解釈しない。

### 修正内容と試験方法

- 三機能を番号順に配置、同地域検索を地区研究より前へ移動。設定・研究診断・内部進捗・原エラーは折り畳みへ。重要な支持数、価格期、住宅属性、モデル間差と未検証警告は主画面に残す。
- 実行中の確認時点を「終了」と呼ぶ誤表示を修正。
- 日本語の通信・移動・アクセス制限・DB障害説明を表示。旧データや確認済み部分結果を消さず、0在庫へ変換しない。
- 掲載展開に単価・房齢・年差という計算法を追加。原URL、観測時刻、条件との差は保持。
- 今回0件で旧関連観測がある場合、空の近似欄へ誘導せず、旧観測2件と今回未確認を明記。

最終全**257テスト成功、137.939秒、skip0**。独立 `jhll_test` のPostgreSQL25件（基盤11、按需検索14）を含む。今回追加15件：地区4、統合画面4、表示7。最初の256件成功後、実ブラウザで見つけた旧観測の誘導表示を修正し、257件を再実行した。前回のログも保持。

正常経路、研究区分、部分範囲、現在一致と旧観測、原URL控件は実ブラウザで確認。ネットワーク失敗・DB不可用は制御されたAppTest障害注入で確認し、実DBを止めたりアクセス封鎖を誘発したりしていない。スマートフォン実機・一般購入者のユーザビリティ試験・外部公開環境は今回未検証。

### 保全と残る制約

今回開始時から旧314成果ファイルのハッシュ不変。旧スナップショット、バッチ、イベント、リクエスト、run、job、一覧、リンク、コマンドの全既存行に差分なし。成功IDは1,215のまま、成功観測は1,227→1,228、追加は実再確認1件のみ。元SQLite、旧価格モデル、研究コードは保持。私有API設定・接続文字列・実掲載・モデル・実験出力・ログはGit無視、公開候補の秘密スキャンは最終別記録を参照。ステージは空でCommit/Pushなし。

研究上の地区差は未検証、強い不確実性と標本不足が残る。MLIT駅名と掲載側駅IDの完全な対応、全市場網羅、現在の成約価格、正式価格順位は未実装。原単価の分布を価格指数や将来の購入確率に変換しない。検索状態は手動更新で、ウィンドウを閉じても進行中タスクは停止しない。停止は通信境界で行う。ローカル共通DBは多利用者向けの認可分離済みクラウドではなく、公開前には権限・データ利用条件・保管運用を別途確認する必要がある。

### 推奨Commit対象（今回は未実施）

Phase 4以降の未コミット分をまとめる場合の13ファイル。旧研究や実データを追加しない。

- `README.md` — 三機能・実装済み/研究中の区分
- `streamlit_app.py` — 統合ページ入口と私有データ表示
- `japan_housing_liquidity_lab/area_comparison.py` — 固定属性比較・支持・分布・候補区分
- `japan_housing_liquidity_lab/decision_page.py` — 一入力の三機能・明細と研究詳細
- `japan_housing_liquidity_lab/on_demand.py` — 候補移動時に元町名を持ち越さない
- `japan_housing_liquidity_lab/on_demand_page.py` — 時間/障害/旧観測の表示・房齢と単価
- `tests/test_area_comparison.py` — 支持・分布・モデル区分
- `tests/test_decision_page.py` — 統合画面と実106記録・失敗隔離
- `tests/test_on_demand_presentation.py` — 表示単位・旧観測・障害
- `tests/test_on_demand.py` — 候補移動の属性保持
- `tests/test_web.py` — 統合入口後の旧画面回帰
- `docs/phase5-area-comparison.md` — Phase5初回検証の説明
- `docs/mvp-final-review.md` — 今回の最終機能確認

私有証拠は `reports/mvp-final-review/` の `area-small-unit.json`、`area-family-unit.json`、`browser-searches.json`、`preservation-before.json`、`preservation-after.json`、`all-tests-final.txt`、`safety.json`。これらはCommitしない。スクリーンショットもローカルのみ。

## English

After user review, these 13 files are submitted as the stable research MVP checkpoint. Statements below about uncommitted status preserve the functional-review checkpoint; submission preparation and repeated checks are tracked in Git history. Regional price comparisons remain unvalidated.

Final functional review, 2026-11-10: **local private-use MVP accepted; reliable inter-area price equivalence and ranking remain unvalidated.** No new models, fitting, production reset, deployment, commit or push. Phase 5 and this review remain changes after pushed Phase 4 commit `e984566`.

The same property profile feeds all three panels. Regional comparisons retain municipality/station units, identical attributes and a 2026Q2 model reference. Formal prices/gaps/ranks remain unavailable. Added descriptive grouping requires all three model gaps within ±10% and a spread no greater than 5 percentage points. With fewer than 10 recent jointly comparable records, insufficient support takes precedence, while the diagnostic agreement flag is retained. These thresholds organize evidence; they are not validated statistical equivalence rules. Existing 30-market/10-joint full-period gates are unchanged.

The Sangenjaya example has 18 candidates: zero combining recent support and model agreement, two disagreements (Hatsudai/Ikebukuro), and 16 sparse recent samples. Six sparse markets nevertheless have relatively consistent model values. The first table gives their actual unadjusted, jointly filtered transaction medians and quartiles, with actual covered periods and recent counts. Target joint-profile median is 1.24 million JPY/m²; Oimachi is 1.325 million (+6.85%), even though the primary standardized diagnostic gap is −2.69%. Remaining quality and period composition differences prevent this from validating a model contrast. Quartiles are suppressed below 10 valid prices; counts and invalid-price counts remain. Futakotamagawa 70m² retains joint support 6/recent 1, unavailable status and no candidates. No gate is relaxed.

An actual Streamlit browser used one Sangenjaya 25m²/2005/1K/RC/walk 10/30 million JPY input. The historical result remains 106 records (66 older/40 existing-period), actual matching periods 2018Q1–2026Q1, raw median 1.20 million and IQR 1.05–1.30 million JPY/m². Its filters differ from the 30-record regional support profile, which is now explicitly explained. Acquired 2026Q2 data may still omit transactions or be revised; no match does not mean missing-quarter acquisition.

Explicit same-area search scanned two pages/40 source IDs, made five successful HTTP requests, and reconfirmed one strict match in 42.5 seconds: 42.8 million JPY, 25.11m², 2012/year-difference age 14, Sangenjaya 8 minutes, 1K, RC. Price above the input amount was not excluded. Expanded unit price, age, original URL and observation time were inspected in the browser.

Clicking Chuo/Kayabacho reused the property without re-entry and preserved the original target. Its two-page/40-ID search made four HTTP 200 requests in 34.4 seconds. The existing one-hour recheck policy skipped recently observed details: zero new strict/approximate confirmations, two relevant previous observations available separately. The 39 previously observed IDs across all discovered links are not 39 matching candidates. All nine HTTP requests succeeded; both searches are partial. No inventory-zero conclusion or new-property claim is made. One successful snapshot was appended overall.

Technical diagnostics and raw errors moved to expandable details while support, reference period, model differences and limitations remain visible. The live confirmation timestamp is no longer mislabeled as completion. Buyer-facing Japanese errors explain communication/access/redirect/database failures without exposing private connection details. Zero fresh matches now point to relevant past observations when available, rather than an empty approximate-results section.

The final suite passed **257 tests in 137.939 seconds, zero skipped**, including 25 isolated PostgreSQL tests (11 base, 14 on-demand). Fifteen tests were added in this review (4area,4unified UI,7presentation). After the initial 256-test pass, the browser-discovered cache wording was fixed and the entire 257-test suite rerun. Both logs remain. Actual browser testing covered the normal flow, group presentation, partial searches and fresh/old distinction. Network/database failures used controlled AppTest injection; the real database was not stopped to provoke errors. Physical phones, independent buyer usability studies and public-cloud operation were not tested.

All 314 pre-existing artifact hashes and all prior rows of the audited snapshot/batch/event/request/run/job/page/link/command tables remain unchanged. Successful SUUMO IDs remain 1,215; successful snapshots increased 1,227→1,228. Frozen SQLite and old models remain intact. Secrets, raw data, models, reports and logs stay private/ignored; final scan evidence is local. Staging remains empty. The 13-file manifest above is the proposed submission set, not a completed commit.

Remaining limits include sparse recent profiles, unvalidated spatial contrasts, station identity alignment, partial SUUMO coverage, manually refreshed progress and the absence of a public multi-user authorization/persistence deployment. No future buying probability or price-growth prediction is produced. Private evidence resides under the ignored `reports/mvp-final-review/`; it is excluded from the proposed commit.
