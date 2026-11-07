# Task 005 最終監査 / Final review

## 日本語

2026-11-08にコード、保存予測、現行モデル、入力を照合。新モデル・調整・Task006は実施していない。

| 方法 | 開発学習 | n | 開発評価 | 現行参照学習 | n |
|---|---|---:|---|---|---:|
| 全履歴・時間なし | 2023Q1–2024Q4 | 33775 | 2025Q1–Q4 | 2023Q1–2026Q2 | 55652 |
| 直近・時間なし | 2024Q1–Q4 | 16998 | 2025Q1–Q4 | 2025Q3–2026Q2 | 13593 |
| 全履歴・時間あり | 2023Q1–2024Q4 | 33775 | 2025Q1–Q4 | 2023Q1–2026Q2 | 55652 |

開発の学習截止は全て2024Q4、評価截止2025Q4（16915件）。現行学習截止2026Q2。
3手法を同じ設定で再生し、保存予測との最大差は4.66e-10円/㎡。学習・評価行の交差は各0。
2025Q3–2026Q2モデルは2025開発評価に使われていない。過去の結果を漏洩として無効化する根拠はない。
ただし、全データは2026-11-08に取得した現行版で公開日不明。これは取引時期分割の開発検証であり、
2025当時に入手可能だった情報だけのas-of評価、または未使用独立テストと呼ぶのは無効。匿名データの同一物件再取引は識別不能。

入力は60000000円、70㎡、85.714万円/㎡。世田谷区・三軒茶屋・徒歩時間10分・2005年築を正しく変換。
2026Q2基準で房齢21年、2LDK、RC、時間整数13。町名空欄は町名条件なし。挂牌価格をモデル特徴には使っていない。
全履歴135.393万円/㎡×70=9477.486万円、直近152.519万円/㎡×70=10676.333万円、
時間あり158.877万円/㎡×70=11121.380万円。元JSONと完全一致。

現行候補の絞込み件数: 直近13593 → 世田谷区621 → 三軒茶屋52 → 面積56–84㎡で5 → 房齢11–31年で2。
2件は2026Q1の70㎡・築29年・128.571万円/㎡、2026Q2の80㎡・築22年・175万円/㎡。
両方3LDKで、入力の2LDKと一致していない。距離・間取り・構造は厳密な可比フィルタではなく、2件を同一物件品質とは見なせない。
2件の中央値151.786万円/㎡は機械学習推定ではない。モデルは全学習標本の特徴関係から予測し、2件だけへ回帰したものではない。
全履歴/直近/時間調整の違いによる価格差の因果分解はしていない。低挂牌価格だけで割安・欠陥・入力誤りを断定しない。
少標本、未観測品質、丸め、131日の市場時差、未校正の誤差範囲から「无法可靠判断」を維持。

カバー4843/16915=28.6314%、未カバー12072。これは固定2024プールの2025開発分布に限る。
全手法比較のMAEは272379/255890/236603円、可比中位202845円はカバー部分のみ。
同じ4843件では全履歴226541、直近206978、時間あり190870円/㎡。比較母集団を混同しない。
カバー率は信頼確率ではない。改善案: 許諾データ蓄積、駅の一意IDと表記正規化、欠損/地域別カバー監視、
今後の公開版管理と事前登録した評価。最低件数や面積・房齢条件は変更していない。

経験的範囲は2025絶対log残差の90百分位を現行再学習モデルへ移植しただけで、
独立校正・条件付き被覆・現市場被覆の保証なし。『90%の確率で真価が入る区間』という意味ではない。
現行JSONと文書はこれを保証区間と呼んでいない。再学習済みモデルについて2025誤差を独立評価と引用してはならない。

変更は既存説明の可比期間曖昧さの修正、本監査文書、回帰テストのみ。製品コード・閾値・モデル・実験記録は変更なし。
Task004と既存Task005実験ファイルのSHA-256を前後比較。証拠はreports/task005-final-review/。

## English

Code, saved predictions, current artifacts and the example were audited on 2026-11-08. No new method, tuning or Task006 work.
The table above separates development fitting from current-reference refitting. Development uses 2023Q1–2024Q4 (33775 rows),
except the recent model uses only 2024 (16998). All evaluate 2025 (16915). Current fits use all 55652 rows through 2026Q2,
except recent uses 2025Q3–2026Q2 (13593). The latter was NOT used for 2025 evaluation.
All three development fits replay saved predictions within 4.66e-10 JPY/m²; training/evaluation row intersections are zero.
There is no evidence requiring invalidation for train/evaluation contamination. However this current vintage was acquired in November 2026;
unknown publication dates prevent claiming historical as-of validity. The exposed 2025 set is not an independent test, and anonymous property identity is unresolved.

Example: JPY 60 million / 70m² = JPY 857143/m². Setagaya, Sangen-jaya, 10 minutes, 2005 construction, age 21 at 2026Q2,
2LDK and RC are correctly handled. Blank town imposes no town constraint. Asking price is not a prediction feature.
References reproduce the saved JSON exactly: about JPY 94.775m, 106.763m and 111.214m.
The filters reduce 13593 recent records to 621 city, 52 station, 5 area and 2 age matches.
Those two trades are 2026Q1 (70m², age29, JPY1285714/m²) and 2026Q2 (80m², age22, JPY1750000/m²).
Both are 3LDK rather than the example's 2LDK; layout/distance/structure are not strict comparable filters.
The ML references come from broad training samples, not a model fitted to these two trades. Their historical median is descriptive only.
No causal decomposition explains the three-method spread. Two records, unobserved quality, rounding, 131-day lag and uncalibrated error ranges justify abstention.

Comparable coverage is 4843/16915 = 28.6314%; 12072 abstentions. It applies to the fixed 2024 pool evaluating 2025, not rolling/current market coverage.
On the SAME covered rows, MAE is 226541 (all), 206978 (recent), 190870 (time) versus 202845 for comparables.
Coverage is not a reliability probability. Improve authorized data volume, station identity/normalization, missingness and local coverage monitoring,
publication-vintage tracking and preregistered validation; do not weaken filters merely to increase apparent confidence.

Empirical ranges transfer the 2025 90th-percentile absolute log error to refitted models; they are not independently calibrated current-market intervals,
conditional coverage guarantees or a 90% probability statement about the property's true value. Existing JSON/docs correctly disclaim this.
Current refitted models themselves have no untouched evaluation. No original metrics, raw data, models or thresholds were changed.
Only clarify the ambiguous comparable-window wording and add audit documentation/regression tests. Protected file hashes are checked before/after.
