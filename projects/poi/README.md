# POI：取得・比較から地域特徴量へ

**This repository uses only publicly obtainable data. No proprietary company data is included.**

個人ブログと連動する、都市GeoAI / Location Intelligenceの公開実験リポジトリです。公開データを取得・再現できるコードと手順を育てます。最初の実験は、接続・地域のPOI取得・カフェ抽出を短いコードで追える初心者向けの [Foursquare Open Source PlacesのNotebook](notebooks/01_foursquare_places.ipynb) です。[実行手順](docs/foursquare.md)と[実際の検証状況](docs/foursquare-validation.md)を確認してください。

## テーマ

POIオープンデータ、商圏分析、Location Intelligence、都市・地域特徴量、機械学習、Embedding / Region Embedding、類似地点・類似商圏検索、Spatial RAG、LLM + GIS、GeoAI Agentを扱います。

## セットアップ

Python 3.11以上とuvを使用します。`projects/poi/` で実行してください。

```powershell
git clone https://github.com/isshiki/geoai-open-lab.git
cd geoai-open-lab/projects/poi
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
uv sync --locked
New-Item -ItemType Directory -Force data/raw, data/cache | Out-Null
uv run --locked python -c "import geoai_open_lab, duckdb; print(duckdb.sql('SELECT 42 AS answer').fetchone())"
```

`uv.lock` は依存関係の固定に使用します。`.venv/` と `data/` はGit管理外です。新しいcloneでは `data/` がないため上記手順で作成します。上記の環境確認には認証は不要です。Foursquare実験では個人用Portal tokenとNotebook依存グループが必要です。詳細は [実行手順](docs/foursquare.md) を参照してください。

## 構成

```text
../../AGENTS.md        AIエージェントの公開安全性・会社との境界ルール
../../docs/data-policy.md データ利用条件と再現性の記録方針
notebooks/            出力を除去した実験Notebook
src/geoai_open_lab/    再利用するPythonコード
configs/aoi/          公開可能な対象地域設定
data/raw/             ローカルの取得データ（Git管理外）
data/cache/           ローカルキャッシュ（Git管理外）
```

## 最初の実験と拡張

最初は **Foursquare Open Source PlacesをDuckDB / Pythonから取得・確認する** 記事連動実験です。個人用Places Portal tokenを使い、PlacesとCategoriesのsnapshotを個別に固定して、吉祥寺の小さなAOIを確認します。利用条件、認証の準備、実行方法、件数の解釈は [Foursquare実験手順](docs/foursquare.md) を参照してください。生データと実行済みNotebookはGit管理外の `data/` にのみ保存します。

次は地域特徴量→類似地点検索→クラスタリング→Region Embeddingです。カテゴリ共通化は必須工程から外し、統合が必要になったときに検討します。[記事ロードマップ](docs/roadmap.md) / [記事引き継ぎ](docs/article-handoff.md)。

2026-10-19更新：保存済みOvertureと吉祥寺AOIを使った地域特徴量の実装・検証が完了しました。3,591件を駅中心の250m16区画・500m4区画で集計しています。[記事『POIデータから作る「地域特徴量」　Pythonで吉祥寺駅周辺を数値化してみた』](https://blog.masahiko.info/entry/2026/10/15/140624)を2026年10月15日に公開しました。[Notebook 05](notebooks/05_region_features.ipynb) / [方法](docs/region-features.md) / [検証](docs/region-features-validation.md) / [記事資料](docs/region-features-article-handoff.md)。駅の縄張りによるチェーン出店状況の比較は後続候補とし、個別アプリは分析と評価が整い、操作する用途が明確になった場合に別プロジェクトで検討します。各記事でのサービス新設は必須にしません。詳細・完了条件は [今後のタスクプラン](docs/roadmap.md#今後のタスクプラン2026-10-19更新) を参照してください。

ブログ記事を公開したら、関連する実験・再現コマンド・固定したデータの版と相互リンクします。

## 公開データと会社資産の境界

**会社GeoAI（非公開）→ この個人リポジトリは禁止、このリポジトリ（公開）→ 会社側の参照・業務利用は可**という一方向ルールです。会社のコード、データ、文書、プロンプト、設定、非公開のロジックやノウハウは持ち込みません。詳細は [AGENTS.md](../../AGENTS.md) と [データポリシー](../../docs/data-policy.md) を参照してください。

生データ・秘密情報・DB・キャッシュはコミットせず、再現用コードと手順を公開します。Git追加・コミットの前に必ず対象ファイルの内容とサイズを確認してください。

## ライセンス

本リポジトリのコードとオリジナルドキュメントは [Apache License 2.0](LICENSE) で提供します。**外部データセットは各提供者の独自ライセンスに従います。Apache 2.0でデータを再許諾するものではありません。**

## Overture Maps Places

第2の実験は [Overture Notebook](notebooks/02_overture_places.ipynb) です。固定release 2026-09-23.0をDuckDBで読み、同じ吉祥寺AOIをLIMITなしで取得します。[実行方法](docs/overture.md) / [検証結果](docs/overture-validation.md)。データ間の比較・網羅性評価は行いません。

## OpenStreetMap

第3の実験は [OpenStreetMap Notebook](notebooks/03_openstreetmap_poi.ipynb) です。OSMnx 2.1.1とpublic Overpassで同じ吉祥寺AOIの8キー条件のPOI候補を取得し、`amenity=cafe`を抽出します。APIキーは不要です。[実行方法](docs/openstreetmap.md) / [検証結果](docs/openstreetmap-validation.md)。保存済み応答から再処理でき、他データとの比較・共通カテゴリ化は行いません。

## 同じ吉祥寺AOIで3データを比較

第4の実験は [POI比較Notebook](notebooks/04_poi_comparison.ipynb) です。Foursquareは比較用にCOUNTと照合した全件を取得し、Overture・OSMは保存済み結果を再利用します。属性presenceと保守的な一致候補を確認します。網羅率・精度・優劣は評価しません。[実行方法](docs/poi-comparison.md) / [検証結果](docs/poi-comparison-validation.md)。候補表と手動確認サンプルはGit管理外です。

## 配置変更時の認証

環境変数 `FSQ_OS_PLACES_TOKEN` を優先します。`.env` はこのプロジェクト直下を使用します。移行前の利用者のため、プロジェクト直下に `.env` がない場合のみ、リポジトリルートの既存 `.env` を読み込めます。値のコピーや表示は不要です。

地域特徴量の主成果は「1地域＝1行」の数値プロフィールです。吉祥寺駅周辺1km四方について15列を生成し、格子集計は算出根拠として保持しています。Notebook 05は生の特徴量を示し、Notebook 06では固定した採用列・標準化による類似検索を検証しています。

## 東京都内の駅から「吉祥寺」に似た街を探す

2026-10-15、N02-25の656駅グループを同じ1km四方・15列で集計し、密度・構成・集中度の距離を検証しました。主順位は町田・自由が丘・立川南が上位。密度だけのトップ10とは共通0件で、条件変更への依存も報告します。吉祥寺とAOIが重なる駅は除外しますが、候補駅同士の重複は残ります。街の優劣や住みやすさを示しません。

[Notebook 06](notebooks/06_similar_regions.ipynb) / [方法](docs/similar-regions.md) / [固定設計](docs/similar-regions-design.md) / [検証](docs/similar-regions-validation.md) / [記事引き継ぎ](docs/similar-regions-article-handoff.md) / [公開記事](https://blog.masahiko.info/entry/2026/10/15/203743)。クラスタリングは次節で実測済み、Embeddingも次節の記録で実測済みです。

## 地域特徴量のクラスタリング

2026-10-16、同じ656駅の固定特徴量でk=3〜8を比較し、主結果を3群（244・247・165駅）としました。seed間ARI最小0.9749ですが、重複AOIを抑制した313駅で学習すると全駅のARIは0.2707。自然に分離した街種や、街の優劣を示すものではありません。データ追加取得なし。[解説記事](https://blog.masahiko.info/entry/2026/10/16/233348)を公開済みです。

[Notebook 07](notebooks/07_region_clustering.ipynb) / [方法](docs/clustering.md) / [設計](docs/clustering-design.md) / [選択理由](docs/clustering-selection.md) / [検証](docs/clustering-validation.md) / [記事引き継ぎ](docs/clustering-article-handoff.md)。Region Embeddingは2026-10-17に実測済みです。

## 地域Embedding（2026-10-17）

保存済み656駅で961カテゴリのTF-IDFと64次元SVDを比較。近傍保持63.9%、POI分割の一致はB 30.2%に対しC 26.8%、前回分類とのARIは0.2880。安定性改善は確認できなかった。[解説記事](https://blog.masahiko.info/entry/2026/10/17/162343)を公開済みです。

[Notebook 08](notebooks/08_region_embedding.ipynb) / [方法](docs/embedding.md) / [検証](docs/embedding-validation.md) / [記事引き継ぎ](docs/embedding-article-handoff.md)。

2026-10-17図版改訂：分析結果を固定し、POIからEmbeddingへの説明図・A/B/C比較・指標の読み方を初心者向けに改善しました。[記事資料](docs/embedding-article-handoff.md)。

## 対象範囲への感度（2026-10-17）

[Notebook 09](notebooks/09_aoi_sensitivity.ipynb)で、同じ656駅の正方形AOIを半幅500/600/700/800mに変更。500mの旧結果を再現し、全条件で800m基準の候補集合を使用しました。500→800mの上位10共通数は全駅平均A 2.24（完全区画版）・B 3.31・C 3.19駅。Cの分類ARIは0.610、所属変更97駅。追加取得は同releaseの不足48件だけ。Aは完全250m区画で集中度を算出。旧Aの1.97駅も監査用に保持し、B/Cは変更していません。

[計算方法](docs/aoi-sensitivity.md) / [固定仕様](docs/aoi-sensitivity-design.md) / [検証](docs/aoi-sensitivity-validation.md) / [記事資料](docs/aoi-sensitivity-article-handoff.md)。記事は2026-10-20 11:50（日本時間）に公開予約済みです。

## MAUP実験（2026-10-22）

[Notebook 10](notebooks/10_maup.ipynb)：吉祥寺駅中心の固定4km四方・8,750件を5方式で分割。全体平均密度は同じでも分布・相関が変わるかを検証。Notebook 09とは独立。[記事引き継ぎ](docs/maup-article-handoff.md)。記事は未執筆・未公開。

## 駅周辺の範囲定義（2026-10-22）

[Notebook 11](notebooks/11_walking_range.ipynb)：吉祥寺の1km四方3,591件、半径500m3,481件、徒歩5分2,141件、徒歩10分3,794件。徒歩10分と正方形のJaccardは0.940357。80m/分・駅/POI接続100m上限の条件付き比較で、唯一の駅勢圏を決めるものではありません。[方法](docs/walking-range.md) / [検証・記事資料](docs/walking-range-article-handoff.md)。

道路はeki-walkで作成済みのGeofabrik関東2026-10-01版を再利用し、ライブAPIを使わず再現性を確保。© OpenStreetMap contributors / [ODbL 1.0](https://www.openstreetmap.org/copyright)。元PBF SHA-256: `5e0b1bec8d8754a18db3950c6a39e4921e8c19069106a1ac038731f3d250ca83`。初回は`--road-dir`と`--osm-pbf`でローカル入力を指定し、以降はGit管理外の部分キャッシュを使います。道路の図示はノード間の概略線。既存Notebook 09/10と既存結果は変更せず、記事は未公開です。

## 駅周辺の範囲定義：656駅の補足（Notebook 11b）

[Notebook 11b](notebooks/11b_walking_sensitivity.ipynb)を独立して追加。全656駅の四方対道路800mはJaccard中央値0.782818、吉祥寺0.940357は96.57百分位。同じ500mの直線対道路は中央値0.666667。距離上限と定義方法を分け、低POI数の駅も別表で報告します。[事前設計](docs/walking-sensitivity-design.md) / [検証](docs/walking-sensitivity-validation.md) / [記事資料](docs/walking-sensitivity-article-handoff.md)。既存11・固定入力を維持、新規取得なし。
