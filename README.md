# geoai-open-lab

**This repository uses only publicly obtainable data. No proprietary company data is included.**

個人ブログと連動する公開GeoAI / Location Intelligenceラボです。目的別のプロジェクトに、コード・Notebook・文書・テストをまとめています。

| プロジェクト | 内容 | 状態 |
| --- | --- | --- |
| [POI](projects/poi/README.md) | Foursquare・Overture・OSMの取得と比較、地域特徴量・東京都内駅の類似検索 | 地域特徴量記事は下書き済み（未公開）、656駅の類似検索・クラスタリング・Embeddingを実測済み |
| [駅の縄張り](projects/station-territory/README.md) | 東京23区の歩行道路網による駅の範囲とランキング | 移行・再現検証済み（公開条件確認は別途） |
| [商圏・アクセスモデル](projects/retail-spatial-models/README.md) | 公開売上によるHuff検証と、独立したアクセス評価 | 将来候補・計画のみ（データ採用未確定） |

実装済みの各プロジェクトのディレクトリで `uv sync --locked` を実行します。依存とlockfileは独立しています。計画のみのテーマには実行環境をまだ作りません。リポジトリ共通の実験番号は使わず、Notebookの番号は各テーマ内の実行順です。

POIの入口：[Foursquare](projects/poi/notebooks/01_foursquare_places.ipynb) / [Overture](projects/poi/notebooks/02_overture_places.ipynb) / [OpenStreetMap](projects/poi/notebooks/03_openstreetmap_poi.ipynb) / [3データ比較](projects/poi/notebooks/04_poi_comparison.ipynb)。[地域特徴量](projects/poi/notebooks/05_region_features.ipynb) / [記事資料](projects/poi/docs/region-features-article-handoff.md)。[類似地域検索](projects/poi/notebooks/06_similar_regions.ipynb) / [検証](projects/poi/docs/similar-regions-validation.md)。旧Notebook・docパスには移動案内を残しています。

[構成・記事連携](docs/project-organization.md) / [POI記事ロードマップ](projects/poi/docs/roadmap.md) / [データポリシー](docs/data-policy.md) / [エージェント規則](AGENTS.md)

会社の非公開資産を本リポジトリへ持ち込みません。公開された本リポジトリを会社側から参照することは、ライセンスに従って可能です。生データ・秘密情報・生成物はGit管理外の `data/` に保存します。

オリジナルコード・文書は [Apache-2.0](LICENSE)。外部データには各提供元の条件が適用されます。

地域特徴量の主成果は「1地域＝1行」の数値プロフィールです。吉祥寺駅周辺1km四方について15列を生成し、格子集計は算出根拠として保持しています。Notebook 05は生の特徴量を示し、Notebook 06では固定した採用列・標準化による類似検索を検証しています。

[地域特徴量のクラスタリング](projects/poi/notebooks/07_region_clustering.ipynb) / [検証](projects/poi/docs/clustering-validation.md) / [記事資料](projects/poi/docs/clustering-article-handoff.md)。3群は選択したPOI特徴による粗い分類で、重複AOIの抑制に依存します。

[地域Embedding](projects/poi/notebooks/08_region_embedding.ipynb) / [検証](projects/poi/docs/embedding-validation.md) / [記事資料](projects/poi/docs/embedding-article-handoff.md)。961カテゴリ→64次元を検証し、圧縮による安定性改善は確認できませんでした。記事は未執筆・未公開です。
