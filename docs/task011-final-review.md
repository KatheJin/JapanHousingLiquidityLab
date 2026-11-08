# Task 011 最終レビュー / Final review — 2026-11-09

## 日本語

### 結論と実ブラウザー確認の範囲

ローカル研究原型としてレビューした。インターネット公開可能という判定ではない。利用者による既報の確認は「実ブラウザーで四ページを開き、過去の購入機会の合成結果を操作」であり、全ページのフォーム・グラフ・ファイル入出力・スマートフォンを網羅した受入れ確認ではない。

今回もWindowsブラウザーツールが現在URLを十分に確認できず、状態読取りで停止した。以後、ブラウザー操作の回避策は使っていない。従って今回の**実ブラウザー全操作、モバイル幅の視覚確認、実スマートフォン、実ファイル選択・ダウンロード、別ブラウザー間のダウンロードURL認可は未検証**。AppTestによる画面スクリプトとフォーム操作、バックエンドの出力検証を実機確認の代わりとはしない。

### 確認した問題と限定修正

1. 上限2MB以内でも、CSVの長いフィールドはcsv.Errorとなり従来の画面例外処理に入らなかった。深いJSONや不正な入力型も含め、Web入力境界で安全な入力エラーへ変換する。個票や個人情報をエラーに追加表示しない。
2. 媒体名等が`=1+1`などの場合、ダウンロードCSVにそのまま入っていた。表計算で式として解釈され得る先頭文字をWebのCSV出力だけでアポストロフィにより無効化する。JSONの値は変更しない。journal.json再取込みで元の値と履歴を復元できる。Task 010のCLI／原アルゴリズムは変更していない。
3. モード表示は主にサイドバーにあり、地域・掲載画面や狭幅での誤認リスクが残っていた。全ページの主領域に合成／実データを表示。フォーム・掲載属性・アップロードと許諾チェックをモード別に分離する。実掲載の観測価格にあった6,000万円の既定値をなくし、未知の価格を自動採用しない。

### 分析の意味と一致性

- 価格・歴史ページ：Task 005/006原関数と同一入力で一致する実データページ試験を実行。既存55,652件を使用。世田谷区・三軒茶屋・70㎡・2005年・2LDK・RC・6,000万円では直近比較2件、歴史比較5件。少数のため保留する。再学習なし。
- 地域ページ：140,888件と既存予算JSONを使い、Task 009の元のrun/CLI処理で生成する行政区表・駅表・通勤情報と適合数をWeb適合結果と照合する。原成約価格による歴史比較であり、現在の供給や品質調整済み優位性ではない。
- 掲載ページ：既存7合成バッチのJSON／CSVをWeb入口から取り込み、ZIP内history.jsonをTask 010のreplayと照合。journal.jsonの復元も一致。CSVの安全な表示用エスケープだけは意図的な差分。
- Task 011のhome_query、demo、load_real、analyze_home、budget、append_batches、manual_batchは開始前実装と構文木比較で不変。Task 001～010追跡コードはGit差分なし。モデルや原実験は更新しない。

結果は判断保留の具体理由を先に表示。低価格記録割合は過去の比較記録に対する割合で、将来の購入・成約確率ではない。モデル参考価格は時差を持ち、誤差幅は移用された開発誤差で、校正済みの予測区間ではない。五方法、学習窓感度、学習内回顧調整、四半期欠損、2026Q2改訂可能性は残す。全精度の研究JSONと詳細は削除していない。警告の理解度そのものは利用者テストが今後必要。

### プライバシー・ファイル・配備

セッション状態にユーザー入力を置き、共有ユーザーキャッシュや他人の保存フォルダ一覧はない。別セッション、失敗取込み、重複取込み、権利確認、実／合成の区別をテスト。JSON／CSVの既知項目・観測日時・ID同定根拠はTask 010で検査する。圧縮ファイルは入力しない。任意URLの取得・モデルアップロードはない。joblibは管理者の信頼済みローカルファイル専用であり、不正に置き換えられたモデルに対する安全性は保証しない。自由文の個人情報の自動検出、二次配布の許諾証明、匿名化保証は未実装。

セッションの切断・再起動でデータは失われ得る。ダウンロード済み資料や任意でローカル保存したファイルは、画面のセッション消去ボタンでは消えない。OS一時ファイルの異常終了時残留、巨大ジャーナル再計算・同時利用負荷、共有PCの管理者アクセスは運用課題。自動テストでセッション分離を確認しても、実ブラウザー間のダウンロードURL認可を実証したとは言わない。

現設定は127.0.0.1、2MBアップロード上限、利用状況送信なし。Python 3.12、Streamlit 1.67.0、PyArrow 18.1.0と既存model extraを使用。pip checkは依存関係整合性の検査で、脆弱性監査ではない。requirementsは全間接依存を固定したロックファイルではなく、Linux新規環境の再現試験も未実施。

公開前の阻害要因：所有者の承認、クラウド接続設定への切換え、非公開招待制・未招待者拒否の確認、使用データ／モデルのクラウド分析権利と非公開供給方法、秘密情報配置、実ブラウザー／スマートフォン・ダウンロード認可・負荷の検証。コード内認証と永続アカウント保存はない。Cloudではlocal saveを無効にしセッション限定と明記する。[公式Private appの説明](https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/trust-and-security)と[Secrets管理](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)を確認したが、実アカウントの設定や配備は行っていない。

data/reports/modelsとsecretsはGit無視。既存303成果のSHA-256と一致を確認し、追跡済みデータ／秘密なし・ステージ済みファイルなしを確認する。任意の別出力先やgit add -fまで阻止する仕組みではない。今回の証跡は無視対象reports/task011-final-review内。公開候補はREADME、streamlit_app.py、requirements.txt、.streamlit/config.toml、web_adapter.py、web_presentation.py、test_web.py、task011.md、本レビューのみ。

### 最終実行結果

全129テスト成功（既存109＋Web20）、22.230秒、skipなし。Task 005/006実データページ一致、Task 009元CLIとの全行政区・駅比較表一致（140,888件、条件一致3,842件）、Task 010の7バッチ履歴とJSON復元一致を確認。旧303成果ハッシュとTask 011分析関数構文木は不変。312ローカル資料が無視対象、ステージ済み0。依存整合性チェック成功、ローカルhealthはHTTP 200。実ブラウザー／モバイルの未検証範囲は上記のまま。

## English

### Conclusion and acceptance boundary

This is a local research-prototype review, not internet-release approval. Prior user feedback confirms opening four pages and exercising the synthetic historical-opportunity result. It does not establish complete acceptance of every form, chart, upload/download or phone layout.

This review's Windows browser tool stopped during state reading because it could not establish the current URL confidently. No workaround was used. Full desktop interaction, mobile-width visual inspection, physical-phone testing, file dialogs/downloads and cross-browser download-URL authorization remain unverified. AppTest and backend checks are reported separately and do not replace actual browser acceptance.

### Confirmed fixes

Long CSV fields within the 2MB limit raised an uncaught csv.Error. The Web input boundary now converts that error, deep JSON and relevant malformed-type errors into validation failures. Spreadsheet formulas embedded in source identifiers were exported unchanged: Web CSV output now prefixes formula-capable cells with an apostrophe. Exact JSON/journal values and Task 010 CLI behavior remain unchanged; restoration uses journal.json.

All pages now display the synthetic/real mode in the main area, so collapsed sidebars do not hide it. Forms, tracking attributes, uploads and consent are separated by mode. Real manual observations no longer assume the demo's ¥60m default price.

### Analysis and privacy review

Real price and opportunity page tests compare identical inputs against the original Tasks 005/006 functions, using 55,652 records and preserving two recent/five historical comparables and abstention for the established example. Regional verification uses 140,888 rows and compares Web region/station tables, matched count and commute declarations against the original Task 009 run/CLI output. Seven synthetic Task 010 batches pass through Web import/export, with history JSON equal to replay and journal restoration equal to the original batches. The only intentional CSV difference is spreadsheet-safe escaping.

Existing Task 011 analysis functions are checked unchanged by AST comparison; old tracked research modules are unchanged. No model fitting or replacement occurs. Historical fractions remain descriptive, empirical errors are not calibrated intervals, model lag/limited support/window sensitivity remain explicit, and full research detail survives in the advanced area and JSON. Whether ordinary users understand the warnings still requires usability testing.

User inputs use session state without a shared user cache or directory browser. Separate sessions, imports and mode separation are tested. There is no arbitrary URL fetch or uploaded model; local joblib must be trusted by the operator. Free-text PII detection, legal permission verification and anonymization guarantees are absent. Session clearing does not delete downloaded/local saved copies. Crash-temp-file cleanup, large journal recomputation, concurrency and host-administrator access remain operational considerations. Session tests do not prove real-browser download authorization.

The server remains loopback-only with 2MB uploads and telemetry disabled. Python 3.12, pinned Streamlit/PyArrow and existing model dependencies are used. pip check verifies dependency compatibility, not vulnerabilities; indirect dependencies are not fully locked and a clean Linux deployment has not been tested.

Release blockers remain owner approval, cloud binding changes, verified private invitations and outsider denial, cloud-use rights and private artifact provisioning, managed secrets, real browser/mobile/download checks and load testing. No in-app authentication or durable account storage exists. Cloud local saving must remain disabled. The official private-app and secrets references above were reviewed, but no account settings or deployment were changed.

Raw inputs, models, complete reports and secrets stay ignored. Verify 303 prior artifact hashes, no tracked private files and no staged files. Ignore rules cannot prevent forced adds or arbitrary external export paths. Local evidence is under reports/task011-final-review. Suggested public files are README, entrypoint, requirements, safe config, the two Web modules, Web tests, usage documentation and this review. No commit, push or deployment.

### Final execution results

All 129 tests passed (109 existing + 20 Web) in 22.230 seconds without skips. Real Task 005/006 page parity passed. Task 009 original CLI region/station tables matched on 140,888 records with 3,842 budget matches. Task 010 seven-batch history/export/restoration matched. All 303 old artifact hashes and existing Task 011 analysis function ASTs are unchanged. All 312 checked local artifacts are ignored; zero files are staged. Dependency compatibility passed and local health returned HTTP 200. Browser/mobile acceptance remains incomplete as described above.
