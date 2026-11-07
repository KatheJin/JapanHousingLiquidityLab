# Task 002 — 取引価格の探索 / Transaction EDA

## 日本語

以下は初回試行の履歴。現在の範囲と取得状況は [更新](task002-update.md) を参照。

2026-11-08: 公式画面で東京都・中古マンション等・取引価格のみ・2023Q1〜2025Q4を指定。
50,690件と表示されたが、ファイル生成中の通知後、再試行でもファイルを受領できなかった。
実データの取得・品質確認・分析は未完了。テストは人工 CSV のみで、実 CSV のスキーマは未検証。

手動取得: https://www.reinfolib.mlit.go.jp/realEstatePrices/ で東京都、種類「中古マンション等」、
「不動産取引価格情報」のみを選び、「成約価格情報」を外す。2023年第1四半期〜2025年第4四半期を設定して
ダウンロード。生成中なら同条件で後から再試行し、ファイルを data/raw/tokyo_2023_2025.csv に保存。
取得日、条件、出典 URL をローカルに記録。画面件数は取得済み件数ではない。

```powershell
.\.venv\Scripts\python.exe -m japan_housing_liquidity_lab.transactions data/raw/tokyo_2023_2025.csv --output reports/tokyo-001
```

Task 001 の文字コード・欠損・ハッシュ検査を再利用。必須列不足は停止。対象地域・種類・期間を検査。
価格情報区分がある場合は取引価格のみ採用し、ない場合は未確認フラグを付与する。
正の数値価格と面積から円/㎡を計算。上限付き面積、範囲、欠損、ゼロは除外して理由を集計。
完全一致行はフラグのみで削除しない。丸められた同一値の別取引があり得るため。
全体の1.5 IQR 外れ値も保持し、市区町村別・四半期別の件数、最小、四分位、中央値、最大を出力。
四分位は線形補間。欠けた四半期を報告。既存出力先は上書きしない。

これは品質調整済み価格指数ではない。物件構成、地域、面積、築年の差と調査回答偏りがある。
丸められた価格・面積による概算単価であり、掲載期間や掲載終了リスクは推定できない。
図表、築年等による層別、実データの異常値感度分析は取得後の課題。
XIT001 は URL 構築のみ。認可キー、HTTP 通信、自動同期は未実装。

## English

The text below records the earlier attempt. See [update](task002-update.md) for current scope and acquisition status.

On 2026-11-08 the official UI showed 50,690 matches for Tokyo, used condominiums, transaction prices only,
2023Q1–2025Q4. It requested a later retry while generating the file; no CSV was received after retrying.
Acquisition, real-data quality checks and real findings remain incomplete. Tests use fabricated CSVs only.

At the official URL above select Tokyo, used condominiums, transaction prices only (uncheck contract prices),
and 2023Q1–2025Q4. Download; retry the same conditions later if generation is pending.
Save as data/raw/tokyo_2023_2025.csv and record acquisition date, filters and source locally. Run the command above.

Reuses Task 001 encoding, missingness and SHA-256 inspection. Missing required columns fail explicitly.
Filters geography, type and period; category is checked when present, otherwise marked unverified.
Positive numeric price divided by area gives JPY/m². Bounded areas, ranges, missing and nonpositive values
are rejected with counts. Exact duplicates and global 1.5-IQR outliers are flagged but retained.
Outputs municipality and quarter counts, min, interpolated quartiles, median and max, plus missing quarters.
Existing output directories are never replaced. Raw data and generated results remain ignored by Git.

These are composition-sensitive summaries, not a quality-adjusted index. Rounding and survey selection affect results.
No listing duration or delisting conclusions are possible. Charts, age stratification and real outlier sensitivity remain future work.
The XIT001 boundary only builds URLs; fetching is disabled pending an approved key and reviewed client.

Sources / 出典:
- https://www.reinfolib.mlit.go.jp/realEstatePrices/
- https://www.reinfolib.mlit.go.jp/realEstatePrices/manual/
- https://www.reinfolib.mlit.go.jp/help/apiManual/xit001
