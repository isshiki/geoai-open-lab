# 地域Embedding：記事引き継ぎ

仮タイトル：**街をベクトルで表すと何が変わる？　Pythonで地域Embeddingを試してみた**

2026-10-17実装・実測。記事執筆・公開は未実施。[検証記録](embedding-validation.md)が数値の正本。
[設計](embedding-design.md) / [採用次元の理由](embedding-selection.md) / [実行方法](embedding.md)。

## 読者に伝える主結果

961の細分類を64次元へ圧縮して、従来とは異なる近傍・分類を得た。ただしBの近傍保持は63.9%、POI半分ずつの一致はB 30.2%に対しC 26.8%。
**圧縮はできたが、より正しい類似や安定性の改善を確認したわけではない。** 正解ラベルがなく、外部評価なし。

問いを「細かいカテゴリを増やす意味（A対B）」と「圧縮する意味（B対C）」に分ける。
AとBでは密度・集中度を直接入れるかも異なるため、順位変化すべてをSVDの効果としない。

## 3方式のトップ10

| 順位 | A：従来8特徴 | B：詳細カテゴリ | C：64次元 |
| --- | --- | --- | --- |
| 1 | 町田 (n02-004387) | 町田 (n02-004387) | 町田 (n02-004387) |
| 2 | 自由が丘 (n02-004196) | 立川南 (n02-003649) | 中目黒 (n02-004014) |
| 3 | 立川南 (n02-003649) | 立川北 (n02-003617) | 立川北 (n02-003617) |
| 4 | 下北沢 (n02-003908) | 立川 (n02-003634) | 立川南 (n02-003649) |
| 5 | 高円寺 (n02-003573) | 北千住 (n02-003260) | 立川 (n02-003634) |
| 6 | 立川北 (n02-003617) | 池袋 (n02-003390) | 学芸大学 (n02-004094) |
| 7 | 代官山 (n02-003985) | 中目黒 (n02-004014) | 北千住 (n02-003260) |
| 8 | 立川 (n02-003634) | 池袋 (n02-003379) | 東池袋 (n02-003432) |
| 9 | 京橋 (n02-003792) | 下北沢 (n02-003908) | 池袋 (n02-003390) |
| 10 | 北千住 (n02-003260) | 渋谷 (n02-003922) | 西荻窪 (n02-003579) |

A–B共通6駅、A–C共通5駅、B–C共通7駅。立川3グループや池袋の複数IDを別々の街の発見と数えない。
町田は3方式とも1位。中目黒はA20→B7→C2位、学芸大学は38→15→6位、西荻窪は65→16→10位。自由が丘は2→13→16位。
Cで入った学芸大学・東池袋・西荻窪は、Bに対する入替例。Aに対する入替と混同しない。

### 入替をカテゴリと密度から読む

吉祥寺の登録密度3,591に対し、学芸大学1,212、西荻窪1,295件/km²でもCで近傍になった。B/Cは件数全体の規模をL2正規化し、カテゴリ構成の方向を比べる。
密度のみの上位10は三越前・京成上野・明治神宮前・神泉・築地・神保町・湯島・小伝馬町・新富町・新宿御苑前。A/B/Cの上位10と共通0駅。

`neighbor_categories.csv`の内積分解では、中目黒のC類似度に和食0.4342、バー0.0935、美容室0.0679、衣料0.0505、カフェ0.0463等が寄与する。
学芸大学では和食0.4930・バー0.0988、西荻窪では和食0.4903・バー0.1098等。これは因果的な順位説明でも、カテゴリの重要度を一つずつ操作した実験でもない。
961列でも件数の多い和食の寄与が強い。TF-IDFが全カテゴリを均等にするという誤解を避ける。

### 8特徴ではまとめていた違い

従来の6カテゴリ群外にも、`rental_kiosk`・ATM・駐車場・宅配ロッカー・事業所などがある。
潜在軸2の大きい側はrental_kiosk/ATM/駐車場/コンビニ/宅配ロッカー、小さい側は和食/バー/restaurant等だった。
潜在軸3ではイベント企画・professional_service・事業所と、美容室・バー等が異なる側へ現れた。
これは従来の「その他」で見えなかった方向を記述できる例。ただし地域の真の生活様式や都市機能を発見したとは言わない。
元の8特徴で近い駅同士について細分類差が人間の認識と合うかは、まだ外部検証していない。

## 3クラスタの比較

ARI **0.2880**、新しい駅数は130/293/233。吉祥寺は新C3。クラスタ番号は旧分類と意味が対応するとは限らない。
C1代表：落合南長崎・西大井・東あずま。全体平均との差は和食・バーが低く、rental_kiosk・parkが高い。
C2代表：ときわ台・京成曳舟・糀谷。美容室・rental_kiosk・駐車場等が高い。
C3代表：向原・東池袋・浜町。和食・バー・restaurant等が高い。
これは平均TF-IDFの差で、構成比のポイント差ではない。番号は密度中央値順。仮称も今回は付けない。
旧C3の165駅は新C2へ9、新C3へ156。旧C1の244駅は新C1へ109、新C2へ129、新C3へ6。
最大一致対応後236駅が変更。変更例は鳩ノ巣・奥多摩・沢井・御嶽（旧2→新1）、竹ノ塚（旧3→新2）。
Silhouette(cosine) 0.1784、DB 2.4247。分離が明快とは言えず、前回と異なる空間の指標の勝敗で選ばない。

## 安定性と、改善しなかった点

- SVDseed変更の上位10一致は平均96.5%。これだけでデータ変動に頑健とは言えない。
- POI半分ずつの一致はC 26.8%、B 30.2%。主Cでは改善なし。
- POI<50の地域はB/Cとも約7.0%。少数データで順位を断定しない。
- 313駅へ重複抑制して学習すると、全駅平均保持76.0%、吉祥寺8/10。主分析の語彙は固定した条件付き検査。
- 近接駅は同じPOIを共有。POI分割は全駅で共通化したが、656駅を独立標本とは扱わない。
- 961→64列へ圧縮できたこと自体は確認。メモリ・サービス速度の改善や、推薦品質の向上は実証していない。
- 稀少カテゴリを落とし、POI名・チェーン・空間配置・人口・交通・人流は使わない。

## PCAとの違い

前回PCAは8特徴を2次元で見せる表示用で、分類は8次元。
今回は961カテゴリのTF-IDFをTruncatedSVDで64次元へ圧縮し、そのベクトルを検索・分類へ投入。
数学的には両方とも特異値分解と関係する線形法。PCAは中心化、今回SVDは非中心化。外部モデルや深層学習は使わない。

## 記事掲載用コード

`projects/poi/`を作業ディレクトリにし、固定入力を持つuv環境で実行する。コード公開だけでデータまで同梱されるわけではない。

```python
from geoai_open_lab.region_embedding import run_embedding
metrics, result, out = run_embedding(dimension=64)
```

内部でSHA/AOI/前回結果を確認し、3方式・次元・seed・POI分割・重複の評価とmanifest保存を行う。
核心部分は次の構成（説明用。countsはprimary件数行列、語彙df>=5を確認済み）。

```python
from sklearn.feature_extraction.text import TfidfTransformer
from sklearn.decomposition import TruncatedSVD
from sklearn.preprocessing import normalize
b = TfidfTransformer(smooth_idf=True, sublinear_tf=False).fit_transform(counts)
svd = TruncatedSVD(n_components=64, n_iter=10, random_state=42)
z = normalize(svd.fit_transform(b))
```

## 図・実行結果

- [representations.png](../data/cache/embedding/tokyo-v1/representations.png)：8特徴・961カテゴリ・64次元は、近さの定義が異なる。 同名SVGも保存。
- [neighbors.png](../data/cache/embedding/tokyo-v1/neighbors.png)：吉祥寺の上位10駅。右のIDで同名駅を区別する。 同名SVGも保存。
- [dimensions.png](../data/cache/embedding/tokyo-v1/dimensions.png)：圧縮次元を増やすと保持は改善するが、POI分割の一致はBを下回る。 同名SVGも保存。
- [clusters.png](../data/cache/embedding/tokyo-v1/clusters.png)：64次元で3群に分類した駅代表点。前回分類の正解・不正解を示すものではない。 同名SVGも保存。
- [latent_axes.png](../data/cache/embedding/tokyo-v1/latent_axes.png)：潜在軸1〜3の係数上下各5カテゴリ。軸名は付けず、符号の任意性に注意。 同名SVGも保存。
- [cover_1600x900.png](../data/cache/embedding/tokyo-v1/cover_1600x900.png)：街の見え方は変わるが、安定性が上がるとは限らない。 同名SVGも保存。

[実行結果HTML](../data/cache/embedding/tokyo-v1/08_region_embedding.html)。すべてローカルのGit管理外。
本文は3方式→トップ10→カテゴリ寄与→次元・安定性→分類→限界の順を推奨。図の取得日・加工日・出典・署名を残す。POI単位のデータ、詳細件数表、Embeddingをブログへ貼らない。
Foursquare NOTICE/Apache本文は同じ成果物フォルダ。記事へ図を転載する際も[出典条件](region-feature-sources.md)に従う。

## 公開コードURL

- [Notebook](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/notebooks/08_region_embedding.ipynb)
- [実装](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/src/geoai_open_lab/region_embedding.py)
- [検証](https://github.com/isshiki/geoai-open-lab/blob/main/projects/poi/docs/embedding-validation.md)

## 残る問い

圧縮が役立つ用途は何か、主カテゴリ偏重を変えたときの結果はどうなるか、人による類似評価と合うか。
これらは今回未検証。TFの変更・他データ追加・商圏判断を今回の成果に含めず、次の目的を決めてから別の仕様として扱う。
