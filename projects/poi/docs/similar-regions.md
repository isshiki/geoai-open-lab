# 類似地域検索：実行と計算方法

[Notebook 06](../notebooks/06_similar_regions.ipynb) / [分析前設計](similar-regions-design.md) / [検証](similar-regions-validation.md) / [記事引き継ぎ](similar-regions-article-handoff.md)

東京都内の656駅グループを、駅中心1km四方・schema version 1の15列へ変換した。吉祥寺の3,591件・全数値とPOI ID集合は前回に一致。類似度は密度・種類の構成・集中度の3ブロックによる。クラスタリング・Embedding・ブログ公開は実施していない。

## 固定入力と再現

`configs/similar_regions.toml`に入力ディレクトリとmanifestのSHA-256を固定する。latest検索はしない。公開cloneに入力データは含まれない。

- N02 ZIPは既存の`data/raw/region_features/station/N02-25_GML.zip`。
- N03 ZIPは`data/raw/similar_regions/N03-20260101_13_GML.zip`。同リポジトリの駅の縄張りテーマ内に保存された公式原データを再利用し、コードや算出済み駅位置は流用しない。N03元取得UTCは未確認、受領記録は2026-10-04T06:55:16.298181+00:00、今回の再利用確認は取得manifestに記録。
- 公式取得元：[N02 ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/N02/N02-25/N02-25_GML.zip) / [N03 ZIP](https://nlftp.mlit.go.jp/ksj/gml/data/N03/N03-2026/N03-20260101_13_GML.zip)。入力ハッシュと利用条件は[固定設計](similar-regions-design.md)。
- Places入力：`data/raw/similar_regions/20261015T080101Z-tokyo/places.parquet`。
- 取得release `2026-09-23.0`、schema v2.0.0、UTC `2026-10-15T08:01:26.347545+00:00`。
- Parquet SHA-256 `77f385ecf6cfcddf9eb8415ba6db76472cd72f4a7b7a61ec446b90a0a99869e8`。
- manifest SHA-256 `45b0911399926a00efb99a56363b3e288b66ef244a4cd38bdd672a4b36d2eec0`。

`projects/poi/`で既存のlockfileに従い`uv sync --locked --group notebooks --group osm`を実行する。今回依存追加・lockfile変更なし。httpfs/spatialは既存拡張をLOADし、見つからなければ停止する。

```powershell
# 明示的な再取得が必要な場合だけ（同releaseが取得不能なら停止）
.venv/Scripts/python.exe -m geoai_open_lab.acquire_tokyo_places
# 保存済みの固定入力で集計・比較。Notebookもこの処理を使う
.venv/Scripts/python.exe -m geoai_open_lab.tokyo_region_features
.venv/Scripts/python.exe -m unittest discover -s tests -v
.venv/Scripts/python.exe -m jupyter lab notebooks/06_similar_regions.ipynb
# 固定入力で通し実行し、出力なしの公開Notebookとは別にHTMLを保存
.venv/Scripts/python.exe scripts/execute_similar_notebook.py
```

再取得時は新しい実行IDを生成する。利用する入力とmanifestを確認して設定の固定値を明示的に更新し、再照合する。古い設定へ自動差し替えしない。取得処理は外接矩形を一度読み、原データの完全一致重複のみ除去する。異なる内容の同一IDは停止。全駅正方形への割当はEPSG:6677で行い、境界を含める。全取得範囲の正常終了を必須とするが、実世界のPOI網羅性の保証ではない。

## 集計と距離

既存`region_profile`・`summarize_grid`・カテゴリ設定を再利用。駅ごとに250m16区画、500m4区画を整数添字で作り、浮動小数点のceilによる極小端区画を防ぐ。内部境界は東・北、外周を含めて各POIを1区画へ割り当てる。従来方式との合成テストと吉祥寺の全値照合を実施する。

密度と集中度のlog1p、全有効駅の中央値・IQR、カテゴリ各1/√6、ユークリッド距離を使用。今回は0件駅なし、全656駅を標準化に使用。その他・欠損率・登録数・最大密度は距離に入れない。IQR=0は停止。未知・未取得・0件を混ぜない。

吉祥寺自身とAOIが重なる井の頭公園を主順位から除き、654候補。候補同士の重複は除外しない。立川・立川南・立川北のような近接候補は独立した街の発見ではない。同名別グループもそのまま残す。同距離はregion_id順。

各二乗距離の3ブロック寄与率は合計1（距離0では未定義）。寄与率は似ている確率ではなく、残る差の内訳。主3ブロックの名目重みを均すが、相関や実際の分散を等しくするものではない。

## 出力と図

`data/cache/similar_regions/tokyo-v1/`に、全駅15列、全格子、駅監査、全方式の順位・寄与率・順位差、重複監査、感度比較、manifestを保存する。`audit_rank`は吉祥寺のみ除く順位、`rank`は吉祥寺との重複も除いた主候補の順位。相対的な順位差は各CSVの`rank_change_from_main`。

図は`save_similarity_figures(output_dir)`でSVG6枚を作成する。PNGは既存のPlaywrightとブラウザがある環境で`node scripts/render_similarity_figures.cjs`を実行する。必要なら`BROWSER_EXECUTABLE`でブラウザ実行ファイルを指定する。依存の自動インストールは行わない。1600×900、出典・署名付き。

全CSV・SVG・PNG・HTML・実行済みNotebook・manifestはGit管理外。文書内の集計表、再現コード、出力なしNotebookを公開する。[公開条件](similar-regions-design.md#出典と公開条件2026-10-15確認)に従い図を記事へ渡す。N03境界線は図へ転載せず、位置図はN02由来の駅代表点で描く。外部タイルやフォントは取得していない。
