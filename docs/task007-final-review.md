# Task 007 最終レビュー / Final review

## 日本語

2026-11-08実施。統計の再取得・全再抽出・新モデル開発は行わず、既存出力、コード、PDF表紙と注記、Git対象を監査した。

### 確認した実際の掲載版

現在の45か月結果は、各月について保有する最新掲載版を選択する。次表はPDFの全掲載期間ではなく、実際に選ばれた観測の対応表。

| 選択された統計月 | 月数 | 掲載版 | 表紙に記載された公開日 |
|---|---:|---|---|
| 2023-01～2023-11 | 11 | MW_202312data.pdf | 2024-01-12 |
| 2023-12～2024-11 | 12 | MW_202412data.pdf | 2025-01-14 |
| 2024-12～2025-08 | 9 | MW_202512data.pdf | 2026-01-13 |
| 2025-09～2026-09 | 13 | MW_202609data.pdf | 2026-10-13 |

4ファイルのSHA-256と表紙公開日を再確認。統計月、掲載版公開日、取得日（2026-11-08）は異なる。45か月を45回の初回公表記録として扱わない。月次198、価格帯480の重複掲載セルに観測された値の差はないが、全履歴が未改訂だった証拠ではない。元の初回月報・途中の改訂・同一URL差し替え履歴は未確認。`--as-of` は掲載版公開日で制限するため安全側だが、当時存在した全情報を再現しない。公開日は所持する公式PDFの表紙を根拠とし、Webサーバの初回掲載時刻まで独立検証したものではない。

### 制度と価格帯

公式注記は2025年1月以降の成約登録適正化システム改修が成約件数へ影響する可能性を示す。2025年の132地域月について、前年との比較フラグと `contracts_yoy_comparable_pct=null` を確認。原変化率は残すが、真の需要増減と解釈しない。制度変更後同士でも影響解消を保証しない。成約を分母とする比率、成約価格帯の跨年比較にも同じ注意が必要。

価格帯は四半期の成約・新規登録フロー、四半期末在庫であり、月次季節性には投入していない。固定名目金額の帯には、市場全体の値上がり・値下がりにより似た住宅が隣接帯へ移る効果がある。高価格帯比率の上昇だけでは、高額住宅への需要構造変化を示せない。地域・品質・面積構成、登録価格と成約価格の違いも残る。新しい価格調整や需要モデルは追加していない。

### 修正した問題

1. 価格帯JSONの制約に、名目価格帯移行、月次季節性への転用禁止、2025年制度変更を明記。
2. 両REINS CLIが件数要約だけを表示して制約を省略していたため、標準出力JSONにも `limitations` を追加。
3. 日英文書に上記の説明と、重複掲載一致から改訂不存在を結論できない点を補足。

統計値・既存成果は変更していない。以前の `reports/reins-prices-007-v1/summary.json` は監査前の文言のまま保持するため、今回の補足警告 `reports/reins-007-review-final/interpretation_warnings.json` と本書を併読する。今後CLIで生成するJSONには警告が含まれる。

### 実行・Git・保存確認

- 全8 CLIの `--help` 起動成功。過去タスクの本番分析は再実行していない。
- 完全テスト：`python -m unittest discover -s tests -v`、50件成功。CLIで制約が失われない回帰テストを1件追加（2入口を検証）。
- 143個の既存 `data/`・`reports/` ファイルについてGit無視を確認。Git追跡対象と非無視の新規ファイルに、原PDF、CSV全統計、モデル、圧縮資料、1MB超のファイルはない。ドキュメントは出典付きの限定的研究摘要で、テスト表は合成値。
- Task 004～006等の既存成果64ファイルのハッシュ一致。過去タスクの追跡コード・研究文書に変更なし。Git無視規則は現状で十分なため変更しない。
- 生資料と整理統計の公開再配布は許諾を包括的に得たものではない。継続転載は公式条件に基づき事前連絡、加工図は出典を明記する。
- Commit/Pushは行っていない。監査機械記録とテストログは `reports/reins-007-review-final/` に保存。

## English

Reviewed on 2026-11-08 without reacquisition, full data re-extraction or new models. The table above maps the **actually selected** 45 reference months to source vintages and their cover publication dates. These are not first-release dates for each historical month. File hashes and cover dates match provenance. Cover dates are the official documentary basis, not an independent verification of the exact web-upload timestamp.

No changes were observed in 198 overlapping monthly cells or 480 overlapping price-band cells. This does not prove that the entire history was never revised: original first releases, intermediate revisions and same-URL replacements are not comprehensively archived. Publication-date filtering is conservative and prevents early use of the supplied later reports, but cannot reconstruct the full information available historically.

The official note identifies possible effects on contract counts from the January 2025 registration-system correction. All 132 regional 2025 YoY comparisons were checked: raw changes remain visible, crossing flags are true and comparable-change values are null. Comparisons within the post-change period are not guaranteed free of reporting effects. This also matters for quarterly contract bands and ratios using contracts as denominator.

Price-band contract/registration counts are quarterly flows; stock is measured at quarter-end. They do not feed monthly seasonality. Fixed nominal thresholds allow similar homes to migrate between bands as overall prices rise or fall, so changing shares cannot directly identify changing demand structure. Composition and registered-versus-contract-price differences also remain.

Confirmed omissions were fixed: price-band JSON now explicitly warns about nominal band migration, quarterly frequency and the 2025 system change; both REINS CLIs now expose analysis limitations in their stdout JSON instead of only printing counts. Bilingual documentation clarifies these limitations and the incomplete revision history. No statistical values or prior artifacts were changed. Existing pre-review JSON remains preserved; read it together with this review and the local `interpretation_warnings.json`. Future CLI-generated outputs include the warnings.

All eight CLI help entry points succeeded. The full suite passed **50 tests**, including one new regression test covering warning propagation through both REINS CLI entry points. All 143 existing data/report files were Git-ignored. Tracked and nonignored new candidates contain no raw PDFs, full CSV statistical tables, model/archive files or files over 1 MB. Documentation contains limited attributed research summaries and tests use synthetic tables. Hashes of all 64 pre-existing artifacts remained unchanged; Task 004–006 code, research documents and results were preserved. Existing ignore rules needed no changes. No commit or push was performed.

Continuous reproduction still requires contact under the official terms; attribution and adapted-chart credit remain necessary. These checks do not grant a blanket redistribution license. Machine audit and test logs are local under `reports/reins-007-review-final/`.
