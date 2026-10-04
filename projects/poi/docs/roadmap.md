# POI記事と実装のロードマップ

2026-10-04、記事担当ChatGPTの整理をユーザーから受領。以下の「完了」はユーザー提供の執筆状況で、記事URLや公開状態を本リポジトリで再確認した意味ではない。記事番号とNotebook番号は別管理する。

| 記事・テーマ | 執筆状況 |
| --- | --- |
| POIオープンデータ比較：Foursquare・Overture・OpenStreetMap | 完了との共有 |
| Foursquare Open Source Placesを使ってみる | 完了との共有 |
| Overture Maps Placesを使ってみる | 完了との共有 |
| OpenStreetMapを使ってみる | 完了との共有 |
| Foursquare・Overture・OpenStreetMapを実測比較 | 完了との共有 |
| Qiita：POIオープンデータ入門・違いと選び方 | 完了との共有 |
| POIデータから地域特徴量を作る：街を数値で表してみる | 次 |
| 吉祥寺に似ている街はどこ？ | 次候補 |
| 東京の駅をAIで分類する：POI・人口・交通からクラスタリング | 後続 |
| 「街」をEmbeddingする：地域Embedding | 後続 |
| チェーン店舗分析・商圏類似度、White-space / Void、出店候補地評価 | 発展 |
| Spatial RAG / LLM × GIS、GeoAI Agent | 長期 |

本線は取得→比較→地域特徴量→類似地点→クラスタリング→Embedding。カテゴリ共通化を必須工程にはしない。複数ソースの統合やEntity Resolutionが必要になった際に検討する。今後のテーマをここで記録することは、その実装・データ取得を開始する承認ではない。

駅の縄張りランキングは `station-territory` の独立テーマであり、このシリーズの実験05として扱わない。原稿・リンク・図版の連携は [記事引き継ぎ](article-handoff.md) にまとめる。
