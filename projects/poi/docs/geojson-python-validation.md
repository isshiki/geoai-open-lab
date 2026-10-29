# GeoJSON Python実測検証

2026-10-29。[記事資料と公式出典](geojson-python-article-handoff.md) / [Notebook 15](../notebooks/15_geojson.ipynb)。既存Notebook 01～14と既存結果は変更しません。

## 入力・環境

外部取得なし。Pythonコードで作った架空の3地物。正常GeoJSON SHA-256：`47fa1b5a67dcd718da2c28f9d762f5664d5ce53027051d0a57f30c2d6f9d8fa8`。
WGS 84経度緯度、Point `(139.767, 35.681)`。LineString・Polygonは実在する経路や施設の境界ではありません。Pointも既存の駅代表点を流用したものではありません。

Python 3.14.0 / GeoPandas 1.1.4 / Shapely 2.1.2 / GEOS 3.13.1 / pyogrio 0.13.0 / GDAL 3.12.4 / pandas 3.0.6 / pyproj 3.8.0。既存uv環境、依存変更なし。

## 確認結果

- 3地物のgeometry type、全座標、name・fictional・example_id属性が保存前後で一致。
- 7ケースを検証。json、from_features、read_file、shape後のis_valid、基本構造チェック、想定地域チェックを別々に記録。
- 未閉鎖リング：from_features/shapeは閉鎖座標を補完、今回のread_fileはGEOSException。補完前のJSONを基本チェックで検出。
- 経緯度逆転：2通りのGeoPandas読込とis_validは通過。今回の座標は緯度範囲違反で検出。
- 自己交差：読込は成功、Polygonのis_validはFalse。自動修復なし。
- 有効な数値範囲内でも東京から離れた点：構造・幾何チェックは通過、想定地域チェックだけが検出。
- 出力5方式のcrs有無・先頭座標を保存。`to_json(to_wgs84=True)`と`to_file(RFC7946='YES')`で旧crsメンバーなし。
- 出力JSON、CSVの再実行一致を検査。Notebookは全6コードセルを順次実行しHTMLを生成。公開Notebookに出力・実行番号・attachmentsなし。

検証はこの入力・バージョンに限ります。一般的な完全RFC準拠・すべてのgeometry・任意属性型の往復を保証しません。

## 検証コマンドと記録

`projects/poi/`で実行：

```powershell
uv --cache-dir data/cache/uv run --no-sync python -m unittest discover -s tests -p test_geojson_tutorial.py -v
uv --cache-dir data/cache/uv run --no-sync python scripts/execute_geojson_notebook.py
uv --cache-dir data/cache/uv run --no-sync python scripts/run_crs_tests.py
```

一時フォルダを制限する環境ではTEMP/TMPをテーマ内のGit管理外 `data/cache/geojson/tmp` に指定。全テストの既存MAUP出力はrun_crs_tests.pyが一時領域へ隔離します。

既存を含む全205テスト成功（新規12）。構造・座標・自己交差・補完・対象外形式・非有限値・投影座標からの保存・往復・再実行を確認しました。主要JSON/CSV4ファイルの再実行SHA-256一致、既存Notebook・成果物・依存設定412ファイルのハッシュ不変を確認しました。

SVG/PNG6組と800px縮小版、実行結果HTMLをブラウザ描画して目視確認。SVGテキストの画面外はみ出し検査も成功。検証ログ、生成物、保存前後のハッシュは `data/cache/geojson/python-v1/` に保存し公開しません。公開候補の文書リンク、Notebookの出力・実行番号・attachments、秘密情報パターン、1MiB以上の不要ファイル、data/混入の確認は成功。既存の座標系カバー関連3ファイルは今回のコミット対象から除外します。
