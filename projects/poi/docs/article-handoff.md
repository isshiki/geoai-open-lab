# POI記事の引き継ぎ

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
