# geoai-open-lab

**This repository uses only publicly obtainable data. No proprietary company data is included.**

個人ブログと連動する、都市GeoAI / Location Intelligenceの公開実験リポジトリです。公開データを取得・再現できるコードと手順を育てます。最初の実験は、接続・地域のPOI取得・カフェ抽出を短いコードで追える初心者向けの [Foursquare Open Source PlacesのNotebook](notebooks/01_foursquare_places.ipynb) です。[実行手順](docs/foursquare.md)と[実際の検証状況](docs/foursquare-validation.md)を確認してください。

## テーマ

POIオープンデータ、商圏分析、Location Intelligence、都市・地域特徴量、機械学習、Embedding / Region Embedding、類似地点・類似商圏検索、Spatial RAG、LLM + GIS、GeoAI Agentを扱います。

## セットアップ

Python 3.11以上とuvを使用します。リポジトリのルートで実行してください。

```powershell
git clone https://github.com/isshiki/geoai-open-lab.git
cd geoai-open-lab
$env:UV_CACHE_DIR = Join-Path $PWD 'data/cache/uv'
uv sync --locked
New-Item -ItemType Directory -Force data/raw, data/cache | Out-Null
uv run --locked python -c "import geoai_open_lab, duckdb; print(duckdb.sql('SELECT 42 AS answer').fetchone())"
```

`uv.lock` は依存関係の固定に使用します。`.venv/` と `data/` はGit管理外です。新しいcloneでは `data/` がないため上記手順で作成します。上記の環境確認には認証は不要です。Foursquare実験では個人用Portal tokenとNotebook依存グループが必要です。詳細は [実行手順](docs/foursquare.md) を参照してください。

## 構成

```text
AGENTS.md              AIエージェントの公開安全性・会社との境界ルール
docs/data-policy.md    データ利用条件と再現性の記録方針
notebooks/            出力を除去した実験Notebook
src/geoai_open_lab/    再利用するPythonコード
configs/aoi/          公開可能な対象地域設定
data/raw/             ローカルの取得データ（Git管理外）
data/cache/           ローカルキャッシュ（Git管理外）
```

## 最初の実験と拡張

最初は **Foursquare Open Source PlacesをDuckDB / Pythonから取得・確認する** 記事連動実験です。個人用Places Portal tokenを使い、PlacesとCategoriesのsnapshotを個別に固定して、吉祥寺の小さなAOIを確認します。利用条件、認証の準備、実行方法、件数の解釈は [Foursquare実験手順](docs/foursquare.md) を参照してください。生データと実行済みNotebookはGit管理外の `data/` にのみ保存します。

拡張は Foursquare → Overture Maps Places → OpenStreetMap → 同一地域の3データ比較 → POIカテゴリ統一 → POI名寄せ / Entity Resolution → 地域特徴量 → 類似地点検索 → Region Embedding → Spatial RAG / GeoAI Agent の順を想定します。将来はe-Stat、国勢調査、国土数値情報なども追加します。

ブログ記事を公開したら、関連する実験・再現コマンド・固定したデータの版と相互リンクします。

## 公開データと会社資産の境界

**会社GeoAI（非公開）→ この個人リポジトリは禁止、このリポジトリ（公開）→ 会社側の参照・業務利用は可**という一方向ルールです。会社のコード、データ、文書、プロンプト、設定、非公開のロジックやノウハウは持ち込みません。詳細は [AGENTS.md](AGENTS.md) と [データポリシー](docs/data-policy.md) を参照してください。

生データ・秘密情報・DB・キャッシュはコミットせず、再現用コードと手順を公開します。Git追加・コミットの前に必ず対象ファイルの内容とサイズを確認してください。

## ライセンス

本リポジトリのコードとオリジナルドキュメントは [Apache License 2.0](LICENSE) で提供します。**外部データセットは各提供者の独自ライセンスに従います。Apache 2.0でデータを再許諾するものではありません。**

## Overture Maps Places

第2の実験は [Overture Notebook](notebooks/02_overture_places.ipynb) です。固定release 2026-09-23.0をDuckDBで読み、同じ吉祥寺AOIをLIMITなしで取得します。[実行方法](docs/overture.md) / [検証結果](docs/overture-validation.md)。データ間の比較・網羅性評価は行いません。

## OpenStreetMap

第3の実験は [OpenStreetMap Notebook](notebooks/03_openstreetmap_poi.ipynb) です。OSMnx 2.1.1とpublic Overpassで同じ吉祥寺AOIの8キー条件のPOI候補を取得し、`amenity=cafe`を抽出します。APIキーは不要です。[実行方法](docs/openstreetmap.md) / [検証結果](docs/openstreetmap-validation.md)。保存済み応答から再処理でき、他データとの比較・共通カテゴリ化は行いません。
