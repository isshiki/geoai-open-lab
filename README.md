# geoai-open-lab

**This repository uses only publicly obtainable data. No proprietary company data is included.**

個人ブログと連動する公開GeoAI / Location Intelligenceラボです。目的別のプロジェクトに、コード・Notebook・文書・テストをまとめています。

| プロジェクト | 内容 | 状態 |
| --- | --- | --- |
| [POI](projects/poi/README.md) | Foursquare・Overture・OSMの取得と比較、地域特徴量・東京都内駅の類似検索 | 地域特徴量からEmbeddingまで4記事を公開、AOI感度記事は2026-10-20公開予約済み |
| [駅の縄張り](projects/station-territory/README.md) | 東京23区の歩行道路網による駅の範囲とランキング | 移行・再現検証済み（公開条件確認は別途） |
| [商圏・アクセスモデル](projects/retail-spatial-models/README.md) | 公開売上によるHuff検証と、独立したアクセス評価 | 将来候補・計画のみ（データ採用未確定） |

実装済みの各プロジェクトのディレクトリで `uv sync --locked` を実行します。依存とlockfileは独立しています。計画のみのテーマには実行環境をまだ作りません。リポジトリ共通の実験番号は使わず、Notebookの番号は各テーマ内の実行順です。

POIの入口：[Foursquare](projects/poi/notebooks/01_foursquare_places.ipynb) / [Overture](projects/poi/notebooks/02_overture_places.ipynb) / [OpenStreetMap](projects/poi/notebooks/03_openstreetmap_poi.ipynb) / [3データ比較](projects/poi/notebooks/04_poi_comparison.ipynb)。[地域特徴量](projects/poi/notebooks/05_region_features.ipynb) / [記事資料](projects/poi/docs/region-features-article-handoff.md)。[類似地域検索](projects/poi/notebooks/06_similar_regions.ipynb) / [検証](projects/poi/docs/similar-regions-validation.md)。旧Notebook・docパスには移動案内を残しています。

[構成・記事連携](docs/project-organization.md) / [POI記事ロードマップ](projects/poi/docs/roadmap.md) / [データポリシー](docs/data-policy.md) / [エージェント規則](AGENTS.md)

会社の非公開資産を本リポジトリへ持ち込みません。公開された本リポジトリを会社側から参照することは、ライセンスに従って可能です。生データ・秘密情報・生成物はGit管理外の `data/` に保存します。

オリジナルコード・文書は [Apache-2.0](LICENSE)。外部データには各提供元の条件が適用されます。

地域特徴量の主成果は「1地域＝1行」の数値プロフィールです。吉祥寺駅周辺1km四方について15列を生成し、格子集計は算出根拠として保持しています。Notebook 05は生の特徴量を示し、Notebook 06では固定した採用列・標準化による類似検索を検証しています。

[地域特徴量のクラスタリング](projects/poi/notebooks/07_region_clustering.ipynb) / [検証](projects/poi/docs/clustering-validation.md) / [記事資料](projects/poi/docs/clustering-article-handoff.md)。3群は選択したPOI特徴による粗い分類で、重複AOIの抑制に依存します。

[地域Embedding](projects/poi/notebooks/08_region_embedding.ipynb) / [検証](projects/poi/docs/embedding-validation.md) / [記事資料](projects/poi/docs/embedding-article-handoff.md)。961カテゴリ→64次元を検証し、圧縮による安定性改善は確認できませんでした。[解説記事](https://blog.masahiko.info/entry/2026/10/17/162343)を公開済みです。

2026-10-17図版改訂：分析結果を固定し、POIからEmbeddingへの説明図・A/B/C比較・指標の読み方を初心者向けに改善しました。[記事資料](projects/poi/docs/embedding-article-handoff.md)。

[AOIサイズの感度検証](projects/poi/notebooks/09_aoi_sensitivity.ipynb)：同じ656駅で半幅500〜800mを比較。500→800mの上位10共通数は全駅平均A 2.24（完全区画版）・B 3.31・C 3.19駅、Cの分類ARIは0.610。最適商圏を決める実験ではありません。[検証](projects/poi/docs/aoi-sensitivity-validation.md) / [記事資料](projects/poi/docs/aoi-sensitivity-article-handoff.md)。記事は2026-10-20 11:50（日本時間）に公開予約済みです。

## MAUP実験（2026-10-22）

[Notebook 10](projects/poi/notebooks/10_maup.ipynb)：吉祥寺駅中心の固定4km四方・8,750件を5方式で分割。全体平均密度は同じでも分布・相関が変わるかを検証。Notebook 09とは独立。[記事引き継ぎ](projects/poi/docs/maup-article-handoff.md)。記事は未執筆・未公開。

POIテーマの[駅周辺の範囲定義](projects/poi/docs/walking-range-article-handoff.md)（Notebook 11）を検証しました。吉祥寺の1km四方3,591件、半径500m3,481件、徒歩5分2,141件、徒歩10分3,794件。固定道路はGeofabrik関東2026-10-01版、© OpenStreetMap contributors / ODbL 1.0。元PBF SHA-256: `5e0b1bec8d8754a18db3950c6a39e4921e8c19069106a1ac038731f3d250ca83`。入力・生成物はGit管理外、記事は未公開です。

## 駅周辺の範囲定義：656駅の補足検証

[Notebook 11b](projects/poi/notebooks/11b_walking_sensitivity.ipynb)で既存656駅を比較しました。四方対道路800mのJaccard中央値は全駅0.782818、吉祥寺0.940357は96.57百分位。同じ500mの直線対道路は中央値0.666667。Notebook 11と既存結果は維持し、新規取得なし。[検証](projects/poi/docs/walking-sensitivity-validation.md) / [記事資料](projects/poi/docs/walking-sensitivity-article-handoff.md)。記事は未公開です。

## 記事構成の更新：駅周辺を定義する3方式

新宿を主例、吉祥寺を対照とする[記事引き継ぎ](projects/poi/docs/station-range-methods-article-handoff.md)を追加しました。正方形・直線500m・道路500mを同じ形式で656駅に適用し、使い分けを説明します。[検証](projects/poi/docs/station-range-methods-validation.md)。Notebook 11・11bと保存済み結果は保持、記事は未公開です。
