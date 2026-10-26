# POI記事の引き継ぎ

## POI影響範囲の部分追試（Notebook 15）

[記事引き継ぎ](urban-function-article-handoff.md) / [検証](urban-function-validation.md)。固定・適応半径の比較を追加。住宅候補1件で3機能推定は成立せず、商業6群と緑地等の限定モデルとして検証。一般向けの「街の機能境界が分かった」という記事にはしない。入力不足と外部一致の限界を扱う技術記事候補。未執筆・未公開。

## 座標系入門（Notebook 14）

**地図の座標系入門　緯度経度・投影法・EPSGをPythonで理解する** の[記事資料](crs-article-handoff.md) / [検証](crs-validation.md) / [Notebook](../notebooks/14_crs.ipynb)。測地線・6677の500m抽出3,481件、3857は3,111件。世界の面積比較と合成密度例、用途別の選び方を掲載。国連決議A/RES/80/307をメルカトル禁止や万能図法の指定と表現しない。既存結果は変更せず、記事は未執筆・未公開。

テーマID：`poi`。記事の順序は [ロードマップ](roadmap.md)、再現条件と実測値は各実験の検証記録を根拠とする。

2026-10-04、フォルダ移行のローカル検証済み。下記をブログ側のリンク更新先とする。mainの公開版と照合して更新する。

| 資料 | 旧パス | 新パス |
| --- | --- | --- |
| Notebook 01〜04 | `notebooks/` | `projects/poi/notebooks/` |
| 取得・比較の手順と検証 | `docs/{foursquare,overture,openstreetmap,poi-comparison}*.md` | `projects/poi/docs/` の同名ファイル |
| Pythonソース | `src/geoai_open_lab/` | `projects/poi/src/geoai_open_lab/` |
| AOI | `configs/aoi/kichijoji.toml` | `projects/poi/configs/aoi/kichijoji.toml` |

旧Notebookと手順・検証docには移動案内を残す。ブログ側のリンク更新を確認するまで削除しない。ラボCodexは計算と検証、記事ChatGPTは原稿と構成、ブログCodexはサイトへの組込みと表示を担当する。共有先チャット・ブログリポジトリ・記事URLは未特定で、自動送信やサイト変更は行っていない。

図版の署名は [masahiko.info](https://masahiko.info/) をタイトルと同じ高さの右上へ薄いグレーで表示する。データ出典は独立して表示。生成図版はGit管理外dataに保存し、記事へ渡す前に出典・利用条件・表示を確認する。

移行時の解析条件・カテゴリ定義・snapshotは維持する。Foursquareの初回サンプル500件・カフェ37件は地域全体の店舗数ではない。比較記事の全件取得とは区別する。3ソースの優劣や真の網羅率をこの比較から断定しない。

## 地域特徴量記事：公開済み（2026-10-15）

[記事用の数値・図・構成案・注意点](region-features-article-handoff.md)を用意した。[Notebook 05](../notebooks/05_region_features.ipynb) / [再現方法](region-features.md) / [検証](region-features-validation.md)。実装と実行は完了。[『POIデータから作る「地域特徴量」　Pythonで吉祥寺駅周辺を数値化してみた』](https://blog.masahiko.info/entry/2026/10/15/140624)を2026年10月15日に公開した。保存済みOverture単独・吉祥寺駅周辺1km四方の実験であり、街同士の比較は次段階。

吉祥寺自体の紹介ではなく、街を比較可能な数値プロフィールへ変換する基礎回。「『吉祥寺』みたいな街を探す」ための土台を作るが、今回だけで吉祥寺らしさや他地域との比較を結論づけない。

東京都内の駅を同じ条件で一括集計する作業は、類似地域検索の実装工程として扱う。独立記事にするだけの発見が出るまでは、別の記事テーマとして増やさない。記事順序と次回以降のタイトルは[ロードマップ](roadmap.md)を正本とする。

地域特徴量の主成果は「1地域＝1行」の数値プロフィールです。吉祥寺駅周辺1km四方について15列を生成し、格子集計は算出根拠として保持しています。Notebook 05は生の特徴量を示し、Notebook 06では固定した採用列・標準化による類似検索を検証しています。

## 次の記事：類似地域検索（2026-10-15）

[類似地域検索の記事引き継ぎ](similar-regions-article-handoff.md)に対象656駅・主トップ10・感度・図とコードを整理した。実装と実測は完了し、[『「吉祥寺」に似た街はどこ？ POIデータで東京都内656駅周辺を比べてみた』](https://blog.masahiko.info/entry/2026/10/15/203743)を2026年10月15日に公開した。東京都内駅の一括集計はこの記事の実装工程であり、独立記事を増やさない。

## クラスタリングの記事（2026-10-16）

[記事引き継ぎ](clustering-article-handoff.md)に3群の特徴・代表駅、k選択、seed/Ward/重複抑制の感度と図のパスを記録。[『POIデータで街をクラスタリング Pythonで東京都内656駅周辺を分類してみた』](https://blog.masahiko.info/entry/2026/10/16/233348)を2026年10月16日に公開した。類似検索の「吉祥寺との距離」と今回の「基準点なしの分割」を区別する。Region Embeddingは下記のとおり実測済み。

## 地域Embedding（2026-10-17）

保存済み656駅で961カテゴリのTF-IDFと64次元SVDを比較。近傍保持63.9%、POI分割の一致はB 30.2%に対しC 26.8%、前回分類とのARIは0.2880。安定性改善は確認できなかった。[『街をベクトルで表すと何が変わる？ Pythonで地域Embeddingを試してみた』](https://blog.masahiko.info/entry/2026/10/17/162343)を2026年10月19日に公開した。

[Notebook 08](../notebooks/08_region_embedding.ipynb) / [方法](embedding.md) / [検証](embedding-validation.md) / [記事引き継ぎ](embedding-article-handoff.md)。

## AOIサイズ感度の記事（公開予約済み）

[記事引き継ぎ](aoi-sensitivity-article-handoff.md)を基に、『POIで街を数値化して分かったこと　分析範囲で「似た街」はどう変わる？』を2026年10月20日11:50（日本時間）に公開予約済み。公開後にURLと表示を確認して追記する。

## 駅周辺の範囲定義（Notebook 11）

[記事資料](walking-range-article-handoff.md)と[計算方法](walking-range.md)を追加。仮タイトル『駅周辺は半径500mでよい？ PythonとOpenStreetMapで徒歩圏を比べてみた』。固定道路網で吉祥寺4条件の実測・図版を作成。記事は未執筆・未公開。既存Notebook 09/10とは独立した検証。

## 駅周辺の範囲定義：656駅の補足（Notebook 11b）

[補足記事資料](walking-sensitivity-article-handoff.md)と[検証記録](walking-sensitivity-validation.md)。全駅の四方対道路800mのJ中央値0.782818、吉祥寺0.940357は96.57百分位。全駅値と和集合30件以上の図の値を区別します。Notebook 11の記事へ補足するか独立記事にするかは未決定。既存11の結果と記事資料を変更せず保持します。

## 最新の記事構成：駅周辺を定義する3方式の使い分け

[こちらの記事引き継ぎ](station-range-methods-article-handoff.md)を今回の執筆用正本とする。新宿の3方式の地図、吉祥寺との対照、全656駅の統計、目的別インフォグラフィックを用いる。Notebook 11・11bの元資料は検証履歴として保持し、以前の「吉祥寺の高一致」を今回の主例にしない。


## 標準地域メッシュ（Notebook 12、2026-10-23）

[Notebook 12](../notebooks/12_regional_mesh.ipynb) / [方法・出典](../docs/regional-mesh.md) / [検証](../docs/regional-mesh-validation.md) / [記事引き継ぎ](../docs/regional-mesh-article-handoff.md)。既存250m人口36区画を500mの9区画へ集約し、2020年人口28,487人と固定POI登録4,057件を共通コードで結合。対象は駅中心1km四方と交差する完全メッシュ、約2.353km²。記事は未執筆・未公開。MAUP・範囲定義の次に共通統計単位を学び、EPSGの詳説へつなぐ。新規取得なし。

## メッシュ入門2本特集（2026-10-23）

1. **地図のメッシュ入門　標準地域メッシュ・H3・S2・独自グリッドをPythonで比較**：[Notebook 13](../notebooks/13_mesh_systems_comparison.ipynb) / [方法](../docs/mesh-systems.md) / [検証](../docs/mesh-systems-validation.md) / [記事資料](../docs/mesh-systems-article-handoff.md)。9方式のセルとOGC DGGSの位置付けを区別する。
2. **日本の標準地域メッシュ入門　1km・500m・250mメッシュをPythonで扱う**：[記事資料](../docs/regional-mesh-article-handoff.md)。階層・コード・境界を主題にし、人口とPOIの結合を最後の応用へ置く。

両記事は未執筆・未公開。Notebook番号は実装順。Notebook 12とcommit eeeb173の実装・人口28,487人・POI登録4,057件・kichijoji-v1成果物は変更せず保持する。新図版はテーマ内data/cache/mesh_systems/comparison-v1およびregional_mesh/guide-v1へ分離。地理データの追加取得はなく、比較用Pythonライブラリだけを専用mesh-systemsグループへ追加した。
