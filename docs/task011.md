# Task 011 — 住まいの判断ノート / Housing Decision Assistant

## 日本語

[最終レビュー（修正・実機未検証範囲・配備阻害要因）](task011-final-review.md)

### 使い方

Python 3.12。プロジェクトルートで実行：

```powershell
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

ブラウザーで http://127.0.0.1:8501 を開く。既定は**合成デモ**。架空区・架空駅・120件の架空取引と固定参照値を使い、実市場を再現する学習モデルではない。利用者の実住宅を合成デモで評価しない。実データへの自動フォールバック・自動取得・再学習はしない。

ローカルの既存ファイルを使うには、同じPowerShellで明示的に設定して起動：

```powershell
$env:JHLL_ENABLE_REAL = '1'
# 任意：データを含む信頼できるプロジェクトルート（ブラウザー入力ではない）
$env:JHLL_DATA_ROOT = 'C:\GitHub\JapanHousingLiquidityLab'
.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

「ローカル実データ」を選ぶ。価格・機会ページは `reports/competitiveness-005-v2/reference.joblib` と `reports/history-003-verified/merged_retained.csv`（55,652件、2023Q1～2026Q2）。データSHA-256とモデル内プロトコルの一致を必須にする。地域ページは `reports/task008-data/merged_retained.csv` と `quality.json`（140,888件、2018Q1～2026Q2）。ハッシュ・件数・四半期集合を検証する。ファイル不足ならエラーを示し、合成結果へ置換しない。joblibは任意コードを実行できるため管理者が検証した既存ローカルファイルだけをロードする。モデルアップロードやURL入力は設けない。

### 四つのページ

1. **住宅価格分析**：行政区・駅・面積・建築年か築年数・掲載額・参考日を入力。金額入力は万円、計算は円、面積は㎡。町名、徒歩分、間取り、構造は未知なら未入力。築年数は参考年との差で建築年へ変換する。Task 005の三参照方法・偏差・比較件数・経験誤差幅を表示する。比較記録不足やモデル誤差を消さず「判断できません」を保持する。経験誤差は校正済み予測区間ではない。
2. **過去の購入機会**：Task 006の原始単価、属性全履歴、属性近年感度、属性＋時間、時間のみを区別し、四半期件数と分布を表示。表示は%（JSONの元値は0～1）。10件未満は比率を保留。Task 008の訓練窓感度、旧方式の学習記録内調整、階・改装等の欠落を表示する。独立した予測性能や将来の購入確率として扱わない。この旧フレームの期間は2023Q1以降に限定し、2018年へ無断拡張しない。
3. **地域と予算**：期間、予算上下限、最小面積、取引時の最大築年数、徒歩上限、行政区でTask 009の既存関数を呼ぶ。絞込み後の件数・面積／築年数四分位・最多間取り・間取り分布を表示。30件未満の要約保留を維持。最小築年数や建築年の範囲指定は初版未対応。駅は行政区＋駅名。歴史サンプルであり現行在庫ではない。交通手段は公共交通・車・自転車・混合を受け付けるが時間は全て未知、通勤条件での絞込みは未実施。
4. **掲載追跡**：Task 010へ手動入力、JSON/CSV＋メタデータ／journal.jsonの復元。価格・属性・同一住戸確認根拠・観測根拠・権利根拠を保持。最初の媒体消失、部分・全監視媒体消失、再出現を表示。消失は確認時刻、成約日ではない。missingは固定ID完全確認だけ。失敗／部分確認では消失を推測しない。異媒体結合は明示根拠を必須にし、プログラムによる本人同定の保証はない。最初の掲載開始日はソースJSON/CSVで明示値を受け付け、first_seenから作らない。

分析結果はJSONダウンロード。原取引行の表示・ダウンロードは提供しない。掲載履歴はJSONと4表CSVをZIPでダウンロードし、次回journal.jsonを復元できる。CSV再取込みには元の権利・scope情報が必要。生成CSVは履歴閲覧用、元バッチCSVと同じ入力形式ではない。不要な個人情報・画像・広告本文を入力しない。手入力／ファイルを受け取ること自体は利用許諾にならない。今回新規取得した実掲載は0件。

### 保存・プライバシー

既定は接続ごとの `st.session_state` のみで共有キャッシュなし。二つのセッションは独立。モードごとに実／合成ジャーナルを分離し混合を拒否。更新・切断・再起動で履歴を失う可能性があり永久保存ではない。削除ボタンは現在セッションのアプリ入力と結果を消去するが、既にダウンロード／保存した資料は消さない。入力値をURLに埋め込まない。外部分析・フィードバック自動送信なし。ホスト管理者はサーバー情報へアクセスできるので、会話・個人情報保管サービスとして利用しない。

ローカル保存が必要なときだけ `JHLL_LOCAL_SAVE=1`、`JHLL_RUNTIME=local` とし、掲載ページの保存ボタンを使う。`data/web-sessions/<ランダムID>/<新規ID>.json` に書き、既存結果を上書きしない。他ユーザーの保存ファイルを一覧・自動ロードしない。ローカル保存はログインに紐づくアカウント保存ではない。クラウドでは `JHLL_RUNTIME=cloud`、`JHLL_LOCAL_SAVE=0` を必須とする。OS一時領域もインポート／出力に利用するが操作終了時に削除する。異常終了による一時ファイル残留はOS・運用側の削除方針が必要。

### データ利用とクラウドへの準備

出典：国土交通省「不動産情報ライブラリ」取引価格情報を加工した独自研究。公式価格査定ではない。[公式規約](https://www.reinfolib.mlit.go.jp/help/termsOfUse/)は権利表記がない対象にPDL1.0を適用し、対象外・第三者権利・加工時の出典等は別途確認する。これは保有ファイル全てを再配布できるという確認ではない。REINS原PDF／利用制限付き集計、掲載資料・画像の権利は別であり、本UIへ追加していない。

Cloud候補はentrypoint `streamlit_app.py`、Python **3.12を明示選択**、root `requirements.txt`。Streamlit 1.67.0、PyArrow 18.1.0を固定（最新版PyArrow 26は既存NumPy 1.26と非互換だった）。既存scikit-learn等はpyprojectのmodel extraを利用し変更しない。初版はクリック時ロード・計算で、共有の利用者入力キャッシュなし。大量同時利用のメモリ・応答時間は未負荷試験。

**今回はデプロイしていない。** `.streamlit/config.toml` は127.0.0.1限定、利用状況送信を無効化、アップロード上限2MB。Cloudではホストの接続設定へ変更が必要だが、許諾と招待制を確認する前に外部公開しない。

- [Cloud公開手順](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy)：既定のデモはGit内のコードだけで動く。実データ配信の実装は未完了。将来は管理者の非公開ストレージから認証取得し、ダイジェスト／版／許諾を検証してサーバーだけへ配置する設計。今回はネットワーク取得コードを入れず、モデルやCSVをGitへ追加しない。
- [Private app](https://docs.streamlit.io/deploy/streamlit-community-cloud/get-started/trust-and-security)：利用可能な非公開設定・招待閲覧者を実アカウントで確認し、未招待者のアクセス拒否を検証する。コード内にログインはなく、現在の設定でインターネットに晒さない。
- [Secrets](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management)：将来の資格情報は管理画面へ置く。`.streamlit/secrets.toml` は既存Git無視。キーや環境ダンプを画面・ログ・文書へ出さない。
- [Session State](https://docs.streamlit.io/develop/concepts/architecture/session-state)：セッションの存続と永続保管は別。Cloudローカルディスクをバックアップと呼ばない。アカウント間の恒久保存は未実装。

### Private Beta開始前チェック（未完了の項目は公開を止める）

- [ ] 所有者が実際の公開を承認し、デモ限定か実分析かを選択。
- [ ] 招待制・未招待者拒否・秘密設定を実環境で確認。
- [ ] 使用する版のデータ／モデルの出典、加工、クラウド利用、集計表示の権利を確認。
- [ ] 実分析なら非公開ファイル供給とチェックサム検証を実装・検証。Gitへ入れない。
- [ ] Cloudのセッション限定・切断時損失・利用者側エクスポートを説明。
- [ ] 同時ブラウザー2人、ダウンロードURL、エラーログに入力漏洩がないか再確認。
- [ ] ブラウザーの視覚確認、スマートフォン表示、実機ファイル選択・保存を実施。
- [ ] 説明を読んだ利用者が「判断できない」「歴史低価格比率」「成約でない消失」を理解するか少人数で確認。
- [ ] 匿名化した画面名・再現手順・期待／実際の動作を受け取る窓口を所有者が決める。今回は連絡・外部送信なし。

### 検証と制限

`python -X utf8 -m unittest discover -s tests -v`。新規テストは入力単位、原関数一致、少数拒否、五方法、取込み／復元、状態、二セッション分離、ファイル不足と実ページのフォーム送信を検査。Streamlit AppTestは画面スクリプトとウィジェットを実行するが実ブラウザーの視覚検証ではない。ローカルHTTPとhealthは200で起動確認。Windowsブラウザー自動操作はツールが現在URLを確信できず停止したため、ブラウザー視覚・実ファイルダイアログの確認は未完了。回避して自動操作を続けていない。

失敗と修正：初回ページの表ラベル中の非識別文字を修正、表フォーム切換えをフォーム外へ移動、テストのボタンをラベルで選択、PyArrowの互換版を固定した。実データ対照ではまず間取り／構造が未入力のケースを既存全項目例と誤比較し、同一入力へ揃えて再検証した。旧価格・機会モデル、Task 001～010コードや実験を変更していない。Task 007市場背景の埋込みや新モデルは今回なし。

最終結果：全123テスト成功（旧109＋新14）、13.758秒。既存303成果ファイルのSHA-256一致。実価格ページは既存55,652件モデルと同じ予測、厳格直近比較2件で保留。歴史ページは同入力で5件、比率を保留。地域ページは140,888件から既存例の条件一致3,842件。元のモデル・旧コード・旧結果は変更なし。

### ブラウザー試用後の読みやすさ改善（2026-11-09）

利用者から、実ブラウザーで四ページを開き、過去の購入機会の合成デモを操作できたとの確認を受領した。今回の追加変更は表示層のみ。Task 005/006のアルゴリズム、モデル、原統計は変更していない。

割合は0.65→65%、単価は857,142.857円/㎡→85.71万円/㎡と表示する。JSONの割合は元の0～1、単価は円/㎡の精度を保持する。5方法を比較・統合して単一の推奨値にせず、通常表示では保留理由・比較件数・比較期間・未調整単価中央値／四分位・掲載単価を下回る過去記録の割合を説明する。「65%でも将来65%の確率で購入できるという意味ではない」と明記。

保留理由は結果から個別表示：10件未満なら実件数、方法による割合の差（算出できる場合）、学習内回顧計算と窓感度、参照データの時差、成約と掲載・未観測品質の違い。合成モードなら架空のため実住宅を評価できないことを先に示す。5方法の結果表、四半期図、完全研究明細は初期状態で閉じた「高度な分析」に保管し、全結果のJSON保存も維持する。

合成参考価格は固定値で、割合は固定生成した架空記録と入力から算出するため、全入力に対して一定の割合を保証するわけではない。繰り返す棒の高さは生成規則であり実際の季節性ではない。これらの注意は結果直前と高度な図表の両方に出す。

実データは、既存サーバーを停止して同じシェルで`$env:JHLL_ENABLE_REAL='1'`を設定後、起動し直して「ローカル実データ」を選ぶ。起動済みサーバーの環境は別シェルの変更では切り替わらない。新規ページテストで実モードの有効化、実モデル／55,652件ロード、世田谷区・三軒茶屋・70㎡・2005年・2LDK・RC・6,000万円の原関数一致を確認。直近比較2件、歴史比較5件で保留する。学習は行わない。ローカルファイルがない公開環境では、この実データ対照テストだけを明示的にskipする。


最終追加検証：全126テスト成功、23.125秒。実データ対照も実行済み（skipなし）。ローカルhealth応答200。旧303成果ファイルとTask 005/006コードは不変。Commit/Push/デプロイなし。

## English

[Final review: fixes, unverified browser checks and deployment blockers](task011-final-review.md)

### Running and implemented pages

Use Python 3.12 and run `python -m pip install -r requirements.txt`, then `python -m streamlit run streamlit_app.py` from the repository root. Open http://127.0.0.1:8501. The default is a clearly labelled synthetic demonstration (120 fictional records and constant reference arithmetic, no fitted model). Set `JHLL_ENABLE_REAL=1` and optionally `JHLL_DATA_ROOT` to the trusted local project root to enable real-data selection.

Price and historical-opportunity pages reuse Tasks 005/006, with the existing 55,652-row 2023Q1–2026Q2 model-matched CSV. Regional budgets reuse Task 009 over the verified 140,888-row 2018Q1–2026Q2 dataset. Hashes, counts and coverage are checked as applicable. Missing files produce an error, never a synthetic replacement. Only operator-controlled trusted joblib is loaded; there is no uploaded model or arbitrary-path input. No retraining or old-model replacement.

Forms accept amounts in ten-thousand yen, convert to yen internally, use m², and derive construction year from reference-year age when requested. Price outputs retain abstention, comparable support and empirical error ranges, not calibrated intervals. Historical results distinguish all five existing methods, small-sample suppression and Task 008 training-window sensitivity; they include fitted-row retrospective adjustments and are not independent prediction evaluation or future probabilities. Regional tables apply budget/area/age/walking filters before counting support. They describe historical transactions rather than current inventory. The initial form supports maximum trade-time age, not minimum age or a construction-year range. All four transport modes remain unsupported for route times.

Tracking reuses Task 010 for manual observations, JSON/CSV imports, source-level disappearance, first/partial/full monitored-source disappearance, identity checks and reappearance. Disappearance times are check times, not sale/removal dates. Explicit first-listed dates may be imported and are never inferred from first-seen. No real listing was acquired. Export downloads a ZIP containing journal JSON and four reporting CSV tables; journal.json restores the history, while report CSVs are not batch-input CSVs. Manual entry and file receipt do not establish reuse rights.

### Privacy, deployment and beta gates

Inputs/results live in each connection's Session State without a shared user cache. Real and synthetic tracking are separate. Disconnects, refreshes or restarts may lose data; users should download history. Optional local saving requires `JHLL_LOCAL_SAVE=1` and `JHLL_RUNTIME=local`; new files are isolated under random session folders in ignored data/web-sessions. This is not an authenticated account store. For cloud use, set `JHLL_RUNTIME=cloud` and disable local saving. Temporary import/export files are cleaned on normal exit; host cleanup policies must cover crashes. Avoid personal data in inputs, evidence and feedback. No external feedback or analytics transmission is implemented.

The configuration binds loopback, disables usage telemetry and caps uploads at 2MB. There is no application login. **Nothing has been deployed.** Future Community Cloud preparation uses streamlit_app.py, explicit Python 3.12 and root requirements.txt. Streamlit 1.67.0 and compatible PyArrow 18.1.0 are pinned; existing model dependency pins remain unchanged. Latest PyArrow 26 proved incompatible with NumPy 1.26. Concurrent load/resource testing remains outstanding.

Before any release: obtain owner approval; verify private-app invitations and denial for outsiders using the official links above; review the specific data/model rights and attribution; implement authenticated nonpublic artifact delivery with hashes if real analysis is intended; keep credentials in managed secrets; disable cloud local saves; test two real browsers, downloads and error privacy; complete visual/mobile and file-dialog checks; explain session loss and statistical limitations; choose an anonymized feedback channel. No automatic private data delivery, accounts, durable multi-user storage or Task 007 market-context integration was added.

MLIT outputs are independently processed from the Real Estate Information Library and are not an official valuation. Its current terms apply PDL1.0 where specified, subject to exclusions, third-party rights and attribution. This does not authorize indiscriminate redistribution of every existing file. REINS PDFs/restricted aggregates and listing content have separate restrictions. All raw CSVs, models and complete reports remain outside Git. Cloud can start in synthetic mode using code alone; real-data cloud deployment is blocked pending rights, artifact delivery and access verification.

### Validation

Run the full unittest command above. New tests exercise units/validation, original-function parity, five historical methods, small-sample abstention, import/export, state changes, separate sessions, missing data and actual Streamlit form submissions through AppTest. AppTest is not browser visual QA. The loopback root and health endpoints returned 200. Windows browser automation stopped because the tool could not establish the current URL confidently; no workaround was used, and visual/file-dialog checks remain outstanding. Initial syntax, widget-test targeting and dependency compatibility failures were corrected. Real-page parity checks use identical layout/structure inputs after an initially mismatched-input comparison. Final local logs are in ignored reports/task011-review. No commit, push or deployment.

Final verification: all 123 tests passed (109 existing + 14 new) in 13.758 seconds; pip check reported no conflicts. All 303 old artifact hashes match. The real price page reproduced the existing 55,652-row reference predictions and abstained with two recent comparables. Historical analysis found five strict records for the same example and withheld fractions. Regional analysis used 140,888 records and found 3,842 matches for the existing budget example. No old modules/models/results changed.

### Readability follow-up after browser feedback (2026-11-09)

The user confirmed that all four pages opened in a real browser and exercised the synthetic historical-opportunity page. This follow-up changes presentation only, preserving the Task 005/006 algorithms and fitted artifacts. Fractions such as 0.65 display as 65%; unit prices display in ten-thousand yen per m². Full-precision JSON keeps the original fractions and yen/m² units.

The default result prioritizes concrete abstention reasons, support, comparison period and unadjusted descriptive prices. It explicitly explains that a 65% lower-price historical record fraction is not a 65% chance of buying a cheaper home in future. All five method results, quarterly counts and complete research JSON remain in an initially collapsed advanced-analysis section and the download. No method is silently selected or combined into a purchase recommendation.

Reasons include the actual count when below ten, method spread when available, retrospective fitted-row/window sensitivity, data lag and asking-versus-sale/unobserved-quality differences. Synthetic reference prices are constants; fractions are calculated from fixed fictional records and the input, not necessarily constant across inputs. Repeated bars follow the generation rule, not real market seasonality. Both the result and advanced charts carry these disclosures.

To enable real data, stop the existing server, set JHLL_ENABLE_REAL=1 in the launch shell, restart and select the real-data mode. Changing a different shell cannot reconfigure an already running process. A new AppTest exercises real-mode activation and existing model/data loading, reproducing the original functions for the Setagaya/Sangenjaya 70m², 2005, 2LDK, RC, ¥60m example. It has two recent comparables and five historical strict comparables and continues to abstain. No training occurs. This specific integration test is explicitly skipped where private local artifacts are absent.

Follow-up verification: all 126 tests passed in 23.125 seconds, including the real-data integration test without skips; local health returned 200. All 303 prior artifact hashes and original Task 005/006 code remain unchanged. No commit, push or deployment.
