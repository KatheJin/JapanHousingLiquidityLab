# Task 008 最終監査 / Final Review

## 日本語

監査日：2026-11-08。基準コミット：`0cb1ed3`。**探索的研究として提出可能。既存の実運用参考モデルへの置換は支持しない。** 全データの再ダウンロード、研究モデルの再学習、Commit、Pushは実施していない。

### 確認した事項

1. **入力の完全性**：2018Q1～2022Q4の20バッチ、85,236行。各マニフェストの出典URL、四半期、取得時刻、件数、ZIP/CSV SHA-256を実ファイルと照合。ZIP内CSVと保存CSVのバイト列も一致。全バッチは東京都・中古マンション等・不動産取引価格情報、CP932、既存と同じ21列。結合後の元フィールドも全行照合し、新旧140,888行を保持した。既存55,652行も不変。出典は [MLIT 不動産情報ライブラリ](https://www.reinfolib.mlit.go.jp/realEstatePrices/)。今回の監査は保存資料の整合性確認であり、公式サイトから独立に再取得した照合ではない。
2. **取得日と公開日**：取得時刻は2026-11-08のZIP保存時刻に基づく。実際の初回公開日は不明のままnullであり、取得日で置換していない。過去の改訂や初回公開版との差は確認できない。
3. **品質**：374行の四半期別フィールド欠損集計を再計算し一致。重複フラグは削除ではない。2021Q4の面積「2,000㎡以上」1行は原記録を保持し、正確な単価ターゲットを作れないため学習対象だけから除外。モデル対象140,887行。
4. **時間分割**：38起点・窓長組合せ、中央値基準を含む303,914予測行について、元レコード、ターゲット、全評価ID、学習期間・件数、学習／評価の非重複を確認。学習窓は常に評価四半期の直前で終了。Pipelineの補完・符号化・標準化は各学習集合でfitされる。特徴変換の全体適用は学習しない決定的変換であり、未来の平均や中央値を使わない。匿名の同一建物・関連取引の依存は排除できない。
5. **評価値**：全foldのRidge MAE、全行の中央値基準予測、共通期MAE/MAPEと支持率、過去4四半期OOF残差に基づく経験誤差幅を再計算。共通評価は同じ4,962行。2026Q1/Q2は既にTask 004で見た標本であり、新しい独立テストではない。実公表時点の版が不明なので厳密な公開時点回測でもない。
6. **歴史相対価格**：109行のOOF比較レコードが元の前向き予測と一致し、全件で学習終了期が取引期より前。自分自身の学習残差はこのOOF比較には使わない。一方、A/B/C/Dの当てはめ感度診断と旧Task 006には学習内評価が含まれる。その件数と「独立性能ではない」という注記は適切であり、OOF結果と混同しない。

### 共通評価期の実際の区間

| 評価期 | 学習窓 | 学習期間 | 学習行数 | 評価行数 |
|---|---:|---|---:|---:|
| 2026Q1 | 3年 | 2023Q1～2025Q4 | 50,690 | 3,404 |
| 2026Q1 | 5年 | 2021Q1～2025Q4 | 86,381 | 3,404 |
| 2026Q1 | 8年 | 2018Q1～2025Q4 | 135,925 | 3,404 |
| 2026Q2 | 3年 | 2023Q2～2026Q1 | 50,058 | 1,558 |
| 2026Q2 | 5年 | 2021Q2～2026Q1 | 85,079 | 1,558 |
| 2026Q2 | 8年 | 2018Q2～2026Q1 | 135,255 | 1,558 |

Q2の学習にQ1が入るのは今回のrolling-origin設計であり、Task 004の固定独立テストを再現する設計ではない。3/5/8年の共通期MAEは238,345 / 248,993 / 262,831円/㎡、MAPEは21.08 / 21.22 / 21.77%。比較候補10件以上の支持は17.03 / 28.21 / 39.16%に増えるが、固定Ridgeの予測改善は示されない。

### 35%・70%・10%の再現

保存済みTask 005モデルから再計算し、元40行の出力・分解を再現した。原単価14/40、時間なし属性調整28/40、時間入りモデルの属性成分29/40、属性＋時間4/40。係数再推定で1行増え、時間成分で25行が閾値を超える。

代表例（2023Q1、CSV行1908）：132万円/㎡ × exp(-0.155321 年齢補正 -0.125089 駅分数補正) = 99.7226万円/㎡。13四半期の時間倍率1.322303で131.8635万円/㎡となり、掲載120万円/㎡を上回る。これは当てはめた線形時間項の影響であり、実際の同一品質価格上昇を実証しない。

自己当てはめを避ける前向き比較では、同じ40行でも3年窓4/40=10%、5年窓9/40=22.5%。8年窓の利用可能例は1行のみ。モデル感度、掲載対成約の差、情報の遅れ、未観測属性を考慮し、価格競争力は引き続き**判断不能**。経験誤差幅は信頼できる校正済み予測区間ではなく、割合は将来の購入確率でもない。

### 確認済み問題の修正

`temporal.py` の出力キー `independent_historical_relative_comparisons` は探索的OOFを独立テストと誤読させるため、今後の出力では `forward_oof_historical_relative_comparisons` に修正した。数式、モデル、閾値、選択記録、実験数値は変更していない。旧 `reports/task008-temporal-v1/robustness.json` は元のキーを含む原記録として保存し、読み手には上記の意味を適用する。READMEと研究文書にこの互換性上の注意を記載した。

### テスト・保全・提出範囲

- 全自動テスト：`python -m unittest discover -s tests -v`、**66件成功**。本監査でモデルの完全再学習は行っておらず、保存予測の整合性・集計・旧モデルの再予測を検証した。
- CLI確認：既存メイン、expansion、expansion import、expansion audit、temporalの5つのhelp入口が正常終了。auditの実入力による再実行も成功。import/temporalの完全再実行は行っていない。
- 旧成果146ファイルのSHA-256は一致。Task 001～007の追跡対象ソース・文書は不変（READMEへのTask 008リンク追加を除く）。既存モデル・実験を上書きしていない。
- data/reports/models配下の実ファイルは全てGit無視対象。追跡済みファイルにもこれらのディレクトリの入力・出力はない。Git無視規則自体は変更不要。`git add -f`で無視を解除しない。
- ローカル証跡：`reports/task008-final-review/audit.json`、`decomposition/`、`tests.txt`。Gitに含めない。
- 監査用Gitパス照合ではWindowsの改行変換による比較失敗を修正し、NUL区切りで再確認した。これはリポジトリの無視規則の不具合ではない。

推奨提出ファイルは下記7件だけ。生CSV/ZIP、モデル、reports配下の詳細出力は対象外。

```text
README.md
docs/task008.md
docs/task008-final-review.md
japan_housing_liquidity_lab/expansion.py
japan_housing_liquidity_lab/temporal.py
tests/test_expansion.py
tests/test_temporal.py
```

次段階では、未使用の後続公開期を取得する前に仕様と判断基準を固定し、地域・価格帯別の系統誤差と相対比率の安定性を検証する。今回の結果だけで旧参考モデルを置き換えない。

## English

Review date: 2026-11-08; baseline commit `0cb1ed3`. **Suitable for submission as exploratory research; not sufficient to replace existing production references.** No full download, research-model retraining, commit or push was performed.

### Integrity and temporal validity

All 20 added quarterly batches (2018Q1–2022Q4; 85,236 rows) match their manifests, ZIP/CSV SHA-256 hashes, archive bytes, counts, periods and scope. They contain Tokyo used-condominium transaction-price information, with CP932 encoding and the same 21 fields as the older dataset. Every original field was compared with the merged data; all 140,888 records, including the existing 55,652, remain intact. This verifies saved-source integrity, not a separate reacquisition from MLIT.

Acquisition timestamps derive from the downloaded ZIP file times on 2026-11-08. Actual first-publication dates remain unknown/null. Revisions and differences from original release vintages cannot be established. All 374 quarterly field-quality rows were recomputed. The single bounded-area record remains retained but cannot supply an exact unit-price target, leaving 140,887 model-eligible rows. Duplicate flags do not remove records.

The review checked all 38 folds and 303,914 prediction rows, including baseline rows, against original IDs/targets, complete training windows, row counts and nonoverlapping validation sets. Training always ends before the evaluated quarter. Imputation, encoding and scaling fit only on each training subset; the stateless feature transform does not estimate future statistics. Anonymous related properties can still create dependence.

The table above gives the six actual common-period splits. Q2 incorporates Q1 in training under rolling-origin validation; this is not a replication of Task 004's fixed test. All three windows evaluate identical 4,962 rows. Fold MAEs, baseline predictions, common-period metrics/support and preceding-four-quarter OOF empirical error radii were independently recomputed. Since 2026Q1/Q2 were already viewed in Task 004, these are exploratory results, not fresh independent tests or strict publication-as-of backtests.

Common-period three/five/eight-year MAEs remain ¥238,345 / ¥248,993 / ¥262,831 per m², with MAPEs 21.08% / 21.22% / 21.77%. Support from at least ten strict comparables rises from 17.03% to 28.21% to 39.16%, without improved accuracy for this fixed Ridge specification.

### Decomposition and self-evaluation

Re-prediction using the saved Task 005 model reproduced all 40 original comparisons and their decomposition: raw 14/40=35%; no-time attributes 28/40=70%; the timed model's attribute component 29/40=72.5%; attributes plus time 4/40=10%. Refitted coefficients add one below-threshold record; the time component moves 25 above the asking threshold.

For the documented 2023Q1 example, ¥1.32m/m² becomes ¥0.997226m after age and station adjustments, then ¥1.318635m after the 13-quarter time multiplier 1.322303—above the ¥1.2m asking threshold. This explains a fitted linear time effect, not proven constant-quality appreciation.

All 109 historical OOF comparison rows match the forward predictions and use training strictly before each transaction quarter. They avoid direct self-fitting. The legacy Task 006 calculation and the A/B/C/D fitted-sensitivity diagnostics still include training observations, with overlaps explicitly recorded; those diagnostics are not independent performance estimates. On the same 40 records, forward three-year and five-year comparisons yield 10% and 22.5%. Only one comparable supports the full eight-year history. Competitiveness remains **undetermined**. Empirical ranges are not reliably calibrated prediction intervals, and historical fractions are not future purchase probabilities.

### Correction, validation and submission

One confirmed terminology issue was corrected: future JSON output renames `independent_historical_relative_comparisons` to `forward_oof_historical_relative_comparisons`. The old `robustness.json` remains unchanged as an experiment record; its legacy key means exploratory forward OOF, not independent testing. Formulas, models, thresholds, selected records and numerical results are unchanged. README and research documentation explain the key change.

All **66 automated tests passed**. Five CLI help entry points succeeded, and the real-data adjustment audit was rerun. Full import/training was intentionally not repeated. All 146 prior artifact hashes match; tracked Task 001–007 source and documentation are unchanged except for Task 008 additions to README. All files in data/reports/models are ignored and none are tracked. No ignore-rule change was needed. The review harness's Windows newline path-comparison issue was resolved with NUL-delimited Git input; it was not a repository defect.

Submit only the seven files listed in the Japanese section. Local detailed evidence in `reports/task008-final-review/`, raw CSV/ZIP files and models remain excluded. Freeze the next protocol and acceptance criteria before obtaining an unused later release, and investigate regional/price-band bias and ratio stability before considering any production replacement.
