# Task 009 最終監査 / Final Review

## 日本語

2026-11-08、基準コミット `03eac49`。結論：**歴史的な記述分析として提出可能。通勤可否・現在の割安順位・因果効果は判断しない。** 大型機能、新規モデル、データ再取得、Commit/Pushは実施していない。

### 修正した実際の問題

1. **省略された比較開始期**：終了期だけを過去に指定しても、開始期がデータ内の最新期を基準にしていた。指定終了期から遡る6四半期へ修正。例：終了2024Q4、開始省略なら2023Q3。終了も省略したときだけデータ内最新期を使う。存在しない期・途中の欠落期は引き続き拒否する。
2. **閉区間の一致条件**：価格・面積フィルタ自体は両端を含むが、入力検証が同じ上下限を拒否していた。同じ正の金額・面積での一致指定を許可し、逆転範囲・非有限値・非正の上限は拒否。必須項目の不足も明示的な入力エラーとした。
3. **交通方式の表現不足**：JSONに `transport_modes` を追加。CLIは従来どおり `--query` でJSONを読む。以下の4識別子を受け付けるが、経路計算機能を追加したわけではない。

| JSON値 | 方式 | 現在の出力 |
|---|---|---|
| `public_transport` | 公共交通 | 未対応・検証済み経路データなし |
| `private_car` | 自家用車 | 同上 |
| `bicycle` | 自転車 | 同上 |
| `mixed` | 複合交通 | 同上。区間の組合せ・乗換時間は未定義 |

省略時は従来の公共交通を意図した `['public_transport']`。複数指定は独立した方式要求であり、自動的に交通手段を組み合わせない。各方式の `door_to_door_minutes` と `within_limit` はnull、`status` は `unsupported_no_verified_route_data`。全体の `constraints_applied=false` を維持する。未知識別子や空リストは拒否する。

```json
{
  "transport_modes": ["public_transport", "private_car", "bicycle", "mixed"],
  "max_commute_minutes": 45
}
```

これは既存の予算JSONに追加する項目例。`max_walk_minutes` は最寄駅アクセスという住宅条件であり、車・自転車・複合交通を指定しても別の通勤時間には変換しない。明示された住宅条件はそのまま適用し、通勤条件を満たしたとは表示しない。

### 確認済み事項

- **価格・面積・年齢・徒歩・期**：円総額と円/㎡を区別。年齢は取引年－建築年で、現在年齢ではない。未知の必要属性は適合扱いにしない。最寄駅30～60分は上限45分に不適合、60分に適合。取引期間も両端を含む。区間の中点を観測時間としない。
- **支持度の段階**：予算表は期間選択後、価格・面積・年齢・徒歩・間取り・構造・地域のAND条件を適用し、その残存行に30件の閾値を適用する。属性調整の30行／固定住宅像10行も残存行で計算。全履歴の636駅地域という数を、予算条件下の支持に転用していない。100行のうち条件一致29行という回帰試験でも統計を拒否する。
- **実データ再計算**：140,888行から独立した式で再選択し、2025Q1～2026Q2の21,877行、例示条件一致3,842行を確認。地域・駅別の件数と価格・面積・年齢中央値は保存済みv2結果と一致。支持は32行政区・8駅地域。元例の期・上下限は明示されているため、今回の修正で数値は変わらない。
- **駅名**：空欄を含む611種類、既知610駅名。226駅名は複数行政区に出現する。「市区町村＋正規化駅名」の875既知組合せと欠損群1つを分けている。実データでNFKCが変更した表記は `浅草(つくばＥＸＰ)` → `浅草(つくばEXP)`。括弧を保持し、単なる `浅草` とは統合しない。同じ行政区内の同名駅・複数路線や駅別名は鉄道IDなしには解決できず、鉄道駅単位の確定集計とは呼ばない。
- **2026Q2**：期が存在することは完全収録の証明ではない。2026年はQ1/Q2のみ、Q2も追加・修訂され得る。`complete_population=false`、公開日不明、限界説明を確認。欠落期をゼロ取引にしない。
- **属性診断**：既存Ridgeの事後的な住宅属性感度を示すだけで、同一場所・アクセス・取引期を保持する。地域の参考価格差を真の住宅品質や通勤効果の因果差としない。学習行を含むため独立性能ではない。2018～2022年へ外挿せず、旧モデルを変更しない。
- **通勤**：最寄駅アクセスは鉄道乗車・待ち・乗換・自動車・自転車・目的地アクセスを含む通勤時間ではない。現行の住宅条件一致は通勤制約付きの推薦ではない。JSONの未知値を0分や制約達成に置換しない。

### テスト・成果保全

`python -X utf8 -m unittest discover -s tests -v`：**87件成功**。前回80件に7件追加。実CLI試験は4方式の入力と、analysis/budget両JSONの同一の未知状態を確認。今回の実データ再計算は予算選択・支持度・原統計に限定し、全歴史集計の再生成やモデル再学習はしていない。

Task 001～008の既存236成果ファイル、および本監査開始時点の全270 data/reportsファイルはSHA-256一致。追跡済みの旧ソース・研究文書も不変で、READMEのTask 009案内追加以外に旧追跡ファイルの変更なし。原CSV、ZIP、モデル、大型成果は既存Git無視規則内にあり、data/reports/models配下の追跡ファイルはない。ステージ済み変更、Commit、Pushなし。

旧 `reports/location-009-v2/` は初期実行のディレクトリ名で、内部の出力版 `task009-v1` は保存した。今後のCLI出力版は `task009-v2`。旧JSONに交通方式情報を後付けせず、監査証跡と4方式の契約例を `reports/location-009-final-review/` に独立保存した。ディレクトリのv2と出力スキーマ版を混同しない。

推奨提出は以下6ファイルのみ。監査の生データ、テストログ、詳細JSON/CSVは提出しない。

```text
README.md
docs/task009.md
docs/task009-final-review.md
examples/location-budget.json
japan_housing_liquidity_lab/location.py
tests/test_location.py
```

## English

Review date: 2026-11-08; baseline `03eac49`. **Suitable for historical descriptive research, not commute feasibility, current-value ranking or causal interpretation.** No large feature, new model, download, commit or push was introduced.

### Confirmed corrections

The default history start now anchors to the requested end quarter rather than the dataset's latest quarter. An end of 2024Q4 with no start yields 2023Q3. Missing/unavailable quarters remain rejected. Equal positive price/area bounds now work consistently with inclusive filters; reversed ranges, invalid numbers and nonpositive upper bounds fail. Missing required JSON fields return explicit input errors.

The query adds `transport_modes`: `public_transport`, `private_car`, `bicycle`, `mixed`; omission defaults to public transport for legacy queries. This is a capability contract, not a route planner. Every requested mode returns `unsupported_no_verified_route_data`, null `door_to_door_minutes` and null `within_limit`; the overall `constraints_applied` remains false. Multiple entries request separate modes, and `mixed` does not synthesize legs or transfers. Unknown tokens/empty lists are rejected. CLI reads the field through `--query`.

The example fragment above extends an existing budget query. Explicit `max_walk_minutes` remains a nearest-station housing condition regardless of transport mode; it is never converted to a car, bicycle or full commute estimate.

### Findings

Budget, area, age-at-transaction, access intervals and transaction periods use the intended units and inclusive limits. Required unknown attributes fail matching. Interval upper bounds prevent a 30–60 minute record from passing a 45-minute access cap. Sample thresholds are applied after period and all housing conditions, including the adjustment-support gate. A 100-row group reduced to 29 matches correctly withholds statistics.

Independent arithmetic on all 140,888 records reproduces the example: 21,877 period rows, 3,842 matches, 32 supported municipalities and eight supported municipality/station groups. Group counts and price/area/age medians match preserved results. The example explicitly sets dates and bounds, so the fixes do not change these numbers.

There are 610 known station-name strings plus blank; 226 names occur in more than one municipality. The 875 known municipality/name groups remain separate. The only observed normalization change is full-width EXP in `浅草(つくばＥＸＰ)`; its parenthetical qualifier is retained, preventing merger with plain Asakusa. Within-municipality homonyms, aliases and line identities remain unresolved without railway IDs.

2026Q2 presence does not establish complete collection; Q2 can be supplemented/revised and 2026 covers only Q1/Q2. Unknown release dates and incomplete-population warnings remain explicit. Missing quarters are not zero transactions.

Attribute adjustment remains retrospective fitted sensitivity with location, access and trade quarter held fixed. It includes training records and is not independent predictive evidence, a true quality difference or a causal commuting effect. It does not extrapolate the saved model into 2018–2022. Nearest-station access does not include waiting, rail travel, transfers, driving/cycling or destination access. Housing matches are not verified commute-constrained recommendations.

### Validation and submission

All **87 tests passed**, adding seven regression tests to the prior 80. The real CLI test covers all four modes and consistent unknown states in both output JSON files. Real-data rechecking targeted budget selection, support and raw statistics; full historical tables/models were not rebuilt.

All 236 Task 001–008 artifact hashes and all 270 data/report hashes captured before this review match. Existing tracked code/research documents are unchanged except the Task 009 README additions. Raw data, archives, models and large reports remain ignored, with no tracked files under data/reports/models. Nothing was staged, committed or pushed.

The preserved `reports/location-009-v2/` directory contains the original `task009-v1` output schema. Future CLI output uses schema `task009-v2`; directory and schema versions are distinct. New review evidence, checked budget tables and the four-mode contract example are stored separately in ignored `reports/location-009-final-review/`. Submit only the six files listed above.
