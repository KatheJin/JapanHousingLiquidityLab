# Phase 4 最終審査 / Final review

## 日本語

初期および改善版の実験は変更せず保持する。三軒茶屋の厳格一致1件と幅広ケースの厳格一致9件は `reports/phase4-search-improvement/` にある当時の観測結果であり、本審査で取得件数を置き換えていない。

HTTP301の限定再検証ではrobots/規約のHTTP200後、元の詳細が301を返し、Locationは同一SUUMOの建物ライブラリー `/library/tf_13/sc_13112/to_1001018786/?bs=011`、Serverはnginxだった。転送先を追跡しなかった。これは別の安定した住戸掲載IDへの移転と確認できず、建物資料への誘導である。成約・下架の証明ではない。記録はGit無視の `reports/phase4-final-review/redirect-review.json`。既存のrobots/規約/共有間隔を維持し、自動リダイレクトは有効化しない。

進行中には「状態と結果を更新」で確定済みsnapshotの部分結果、ページ/候補/詳細/HTTP件数を読み直せる。自動ポーリングや無限再試行は行わない。「検索を一時停止／待機を解除」はこの按需タスクだけに作用し、長期collectorを停止しない。待機中はHTTPなしでpaused、実行中はpause_requestedとして、共有間隔待機中または通信間の安全な位置でpausedになる。進行中のHTTP応答は中断せず、既存のタイムアウトまで待つ。返った正常応答は保存する。ウィンドウを閉じるだけではworkerは止まらない。

再開は既存run/jobsと累計予算を使い、完了詳細を再取得しない。失敗や中断・一時停止を消失と解釈しない。旧DB観測・厳格一致・近似候補は別のまま。結果の対象条件を表示し、新しい入力が不正な時に以前のタスクをその入力の結果として残さない。`render_task(task_id,key_prefix='')` により、住宅フォームを再入力せず既存タスクを表示可能。

最終完全テスト224件成功、skip 0、119.754秒。10提出候補の秘密情報検査、303旧成果ハッシュ、旧SQLite/PG観測の保持検査が成功。

## English

The original and improved live experiments are preserved: one strict Sangenjaya match and nine strict matches in the broader case remain the recorded observations under the ignored `reports/phase4-search-improvement/` directory, not refreshed inventory claims.

A bounded 301 check obtained HTTP200 for robots/terms and HTTP301 for the original detail. Location points to SUUMO's building library `/library/tf_13/sc_13112/to_1001018786/?bs=011`; Server was nginx. It was not followed. This is not a verified relocation to another stable unit listing ID and is not evidence of sale or withdrawal. Evidence remains ignored at `reports/phase4-final-review/redirect-review.json`. Access rules and global pacing remain enforced; automatic redirects remain disabled.

Refreshing progress now reads committed partial snapshots while a worker runs. There is no polling daemon or endless retry. Pause affects only the requested on-demand task: queued/waiting requests become paused without HTTP, while active requests become pause_requested and pause during pacing or between network calls. In-flight HTTP is allowed to finish or reach the existing timeout; successful responses are retained. Closing the browser alone does not stop the worker. Resume preserves the same run, cumulative budgets and completed jobs. No disappearance is inferred. Strict/approximate/older observations stay separate, and the task's property conditions are visible. Invalid new form inputs do not retain an unrelated previous task as their result. The reusable `render_task(task_id,key_prefix='')` displays an existing task without another property form.

Final full suite: 224 passed, zero skips, 119.754 seconds. Secret scanning covered all ten staged files; 303 old artifact hashes and original SQLite/PostgreSQL observations remained intact.
