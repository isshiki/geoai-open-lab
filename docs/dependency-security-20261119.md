# Notebook依存のセキュリティ更新（2026-11-19）

POI・駅の縄張りの独立したuv環境で、Soup Sieve 2.10を4.0、Tornado 6.5.10を6.6.1へ更新した。Soup Sieveの4.0は4.0.0と同じ版の表記。対象はGitHub Dependabotの7種類・2ロックファイル分の14件。

- Soup Sieve：3種類、各テーマで高2・中1。最小修正版は各指摘で3.0.2または4.0.0。[4.0.0が必要な指摘](https://github.com/isshiki/geoai-open-lab/security/dependabot/10)。
- Tornado：4種類、各テーマで中2・低2。最小修正版は6.6または6.6.1。[6.6.1が必要な指摘](https://github.com/isshiki/geoai-open-lab/security/dependabot/16)。

## 変更範囲と互換性

両テーマのnotebooksグループへ `soupsieve>=4.0` と `tornado>=6.6.1` を明記。Beautiful Soup・nbconvert・Jupyter経由の依存に対する安全な下限として指定する。

Soup Sieve 4.0の配布メタデータがPython 3.11.5以上を要求するため、両テーマのrequires-pythonを `>=3.11.5` へ引き上げた。3.11.0～3.11.4は対象外となる。元の `>=3.11` で解決すると旧Python向けにBeautiful Soup 4.6.3へ下がるため、その解決は採用しなかった。

最終lockfileのパッケージ版を更新前と全件比較し、版が変わったのはSoup Sieve・Tornadoだけと確認。Beautiful Soup 4.15.0と他パッケージ版は維持。使用中のPythonは両テーマとも3.14.0。

## 検証

| 対象 | 結果 |
| --- | --- |
| POI既存テスト | 205件成功。既存MAUP出力を隔離するrun_crs_tests.pyを使用 |
| 駅の縄張り既存テスト | 14件成功 |
| POI Notebook 15 | 元の6コードセルを全実行、エラー出力なし |
| 駅の縄張りNotebook 01 | 元の4コードセルを全実行、固定入力の検査を含め成功 |
| HTML変換 | nbconvertで両方成功。Soup Sieveを使うBeautiful SoupのCSSセレクタで見出し・表を検査。POIは3表、駅の縄張りは12表 |
| 依存整合 | 両環境のuv pip check成功 |
| 公開Notebook | 原本のSHA-256不変 |

Notebook実行は各テーマの専用Pythonをkernel specで明示。POIの出力先だけ検証用のメモリ内準備セルで切り替え、既存結果を上書きしない。駅の縄張りは既存結果を読む。実行済みNotebook・HTML・ログは各テーマのGit管理外 `data/cache/security-20261119/` に保存。

最初の制限環境ではカーネル開始前に待機したため、対象の検証プロセスだけ終了し、権限付きで再試行して成功した。Windowsのイベントループ補助スレッドとローカルカーネル通信に関する警告は記録されたが、実行・変換エラーはなかった。

全Notebookの再実行、Jupyterサーバーの外部公開設定、攻撃コードによる脆弱性再現試験は行っていない。この検証は修正版への更新と代表Notebookの互換性を確認するもの。

## 再実行

各テーマで `uv sync --locked --all-groups` を実行する。POIのテストは `uv run --no-sync python scripts/run_crs_tests.py`、駅の縄張りは `uv run --no-sync python -m unittest discover -s tests -v`。既存の制限環境ではTEMP/TMPをテーマ内のGit管理外フォルダへ指定する。

今回の更新コマンドは `uv lock --upgrade-package soupsieve==4.0 --upgrade-package tornado==6.6.1`。新しいデータの取得・既存分析値の変更は行わない。依存更新以外の既存未コミット変更は今回のコミットへ含めない。
