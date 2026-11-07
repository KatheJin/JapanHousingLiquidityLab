# 研究計画 / Research plan

## 日本語

1. 現段階: オフライン環境、ローカル MLIT CSV の検査、合成データの生存分析とテスト。
2. 次段階: 許可された取引データによる価格基準の検討。対象地域、期間、物件種別を先に定義。
3. 将来: 許可された掲載観測を蓄積し、掲載終了のラベル規則と時系列検証を設計。
4. 追加研究: 相対価格や値下げ後の終了リスク。価格以外の交絡があるため、値下げの因果効果とは断定しない。

合成データではイベント時刻を平均90日の指数分布、独立な打ち切り時刻を30〜180日の一様分布から生成します。
観測期間は両者の最小値、イベントは終了が打ち切り以前に発生した場合に1です。価格はランダムな説明用列で、モデルには使いません。
Kaplan–Meier は同時刻のイベントを打ち切りより先に扱います。独立打ち切りを仮定する集団基準モデルです。
`1 - S(a+h)/S(a)` は年齢 a まで存続した集団の次の h 日間の終了リスクです。
追跡範囲外や S(a)=0 の場合は推定を拒否します。CLI の出力は a=0 の7日・30日リスクで、推定不能なら null です。
信頼区間、個別モデル、実データでの精度評価は今後の課題です。

実データでは初回観測を掲載開始と同一視せず、観測間の掲載終了は区間打ち切りとして検討します。
再掲載、撤回、データ欠落を区別し、学習・評価の期間と物件を分離して漏洩を防止します。
価格変更は観測時点で利用可能な値のみを使い、将来情報を特徴量に含めません。
将来の同期は取得時刻とモデル版を記録し、検証後に更新します。自動収集やオンライン学習は未実装です。

## English

1. Now: offline environment, local MLIT CSV inspection, synthetic survival analysis, and tests.
2. Next: study a price reference using authorized transaction data after defining region, period, and property type.
3. Later: accumulate authorized listing observations and define event labels and temporal validation.
4. Extension: relative pricing and post-reduction delisting risk. Confounding prevents interpreting association as a causal effect.

Synthetic event times follow an exponential distribution with a 90-day mean; independent censoring times are uniform over 30–180 days.
Observed duration is their minimum; the event indicator is one when the event occurs no later than censoring.
Prices are random illustrative fields and are not model inputs.
Kaplan–Meier handles tied events before censor removals and assumes independent censoring.
`1 - S(a+h)/S(a)` estimates next-h-day risk among listings surviving beyond age a.
The implementation rejects extrapolation beyond follow-up and conditioning where S(a)=0.
CLI output reports age-zero risks at 7 and 30 days, or null when unsupported.
Confidence intervals, individualized models, and real-data evaluation remain future work.

Do not equate first observation with listing start. Consider interval censoring when disappearance occurs between observations.
Separate relisting, withdrawal, and missing observations. Split evaluation by time and property to avoid leakage.
Only use prices available at prediction time. Future sync should preserve acquisition timestamps and model versions and validate before updating.
Automated acquisition and online learning are not implemented.
