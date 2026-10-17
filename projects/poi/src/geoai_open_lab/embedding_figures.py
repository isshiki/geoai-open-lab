"""Six reproducible SVG figures from locally verified embedding outputs."""
import json
from pathlib import Path
import pandas as pd
from .region_figures import text
from .clustering_figures import rect,line,COLORS,document


def save_embedding_figures(out):
    out=Path(out);m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    dim=m['selected_dimension'];metrics=pd.read_csv(out/'dimension_metrics.csv')
    ranks=[pd.read_csv(out/f'ranking_{mode}.csv').head(10) for mode in ('A','B',f'C{dim}')]
    paths=[]
    def save(name,title,subtitle,body):
        svg=document(title,subtitle,body,m).replace('集計・作図 2026-10-16','集計・作図 2026-10-17')
        p=out/(name+'.svg');p.write_text(svg,encoding='utf8');paths.append(p)
    body=''
    rows=[('A  従来の8特徴','密度・6カテゴリ群・集中度','robust標準化 → 重み付きEuclidean'),
          ('B  961カテゴリ','primaryの件数 → TF-IDF → L2正規化','細かな構成の向きで比較（コサイン距離）'),
          (f'C  {dim}次元Embedding','B → TruncatedSVD → L2正規化','圧縮したベクトルを検索・分類へ使う')]
    for i,(title,detail,note) in enumerate(rows):
        y=210+i*175;body+=rect(60,y-35,12,125,COLORS[i])+text(95,y,title,32,font_weight='bold')
        body+=text(95,y+46,detail,26)+text(95,y+85,note,23)
    body+=text(60,760,'同じ656駅・1km四方。B/Cには登録密度・POI名・チェーン名を直接入れません。',24)
    save('representations','街をベクトルで表す3方式','「近い」の定義が違うため、方式間の距離値を直接比べません。',body)
    body=''
    for j,(title,table) in enumerate(zip(['A：従来8特徴','B：詳細カテゴリ',f'C：SVD {dim}次元'],ranks)):
        x=70+j*510;body+=text(x,190,title,29,font_weight='bold')
        for i,r in enumerate(table.itertuples()):
            y=244+i*48
            # Region IDs distinguish same-name station groups, notably Ikebukuro.
            body+=text(x,y,f'{i+1:2}  {r.station_name}',26)
            body+=text(x+285,y,r.region_id.replace('n02-',''),18)
    body+=text(70,765,'右の番号：固定した駅グループID末尾。同名駅も統合規則を変更しません。',23)
    save('neighbors','吉祥寺の近傍トップ10','自駅と吉祥寺AOIに重なる駅を除外。候補駅同士の重複は残ります。',body)
    body=''
    labels=[('explained_variance','説明分散'),('b_retention_mean','Bの近傍保持'),('split_mean','半分ずつの一致'),('seed_mean','seed変更の一致')]
    for j,(field,title) in enumerate(labels):
        x=70+j*385;body+=text(x,205,title,25)
        for i,r in enumerate(metrics.itertuples()):
            y=265+i*105;v=getattr(r,field)
            body+=text(x,y,f'{r.dimension}次元',21)+rect(x,y+13,290*v,28,COLORS[j])
            body+=text(x+300,y+36,f'{v:.1%}',21)
    body+=text(70,735,f'半分ずつの一致：圧縮しないBは {m["split_b_mean"]:.1%}。Cは候補すべて下回る。',26)
    body+=text(70,775,'保持・一致＝上位10駅の共通数÷10の平均。各バーは0〜100%。説明分散は別指標。',21)
    save('dimensions','次元数を増やすと、何が残るか','POI分割は同じPOIを全駅で同じ半分へ割り当て、IDF・SVDも再学習。',body)
    a=pd.read_csv(out/'assignments.csv');s=pd.read_csv(out/'cluster_summary.csv')
    scale=min(930/(a.x.max()-a.x.min()),510/(a.y.max()-a.y.min()));body=''
    for r in a.itertuples():
        x=75+(r.x-a.x.min())*scale;y=725-(r.y-a.y.min())*scale
        body+=f'<circle cx="{x}" cy="{y}" r="4" fill="{COLORS[r.cluster-1]}" fill-opacity=".7"/>'
    body+=text(75,190,'N ↑',24)
    for r in s.itertuples():
        y=245+(r.cluster-1)*130;body+=rect(1040,y-24,22,22,COLORS[r.cluster-1])
        body+=text(1080,y,f'C{r.cluster}：{r.count}駅',29)+text(1080,y+45,r.representatives.split(' / ')[0],25)
    body+=text(1040,670,f'旧分類とのARI：{m["cluster_ari"]:.3f}',25)+text(1040,713,'ARIは正解率ではない',22)
    body+=line(80,760,80+10000*scale,760)+text(80,790,'10 km / EPSG:6677',18)
    save('clusters','Embeddingでも3群に分類する',f'{dim}次元でK-means、k=3。点は駅代表点。C番号は密度中央値順で優劣を表さない。',body)
    axes=pd.read_csv(out/'axis_categories.csv');body=''
    for j,axis in enumerate([1,2,3]):
        x=65+j*510;body+=text(x,190,f'潜在軸 {axis}',29,font_weight='bold')
        subset=axes[axes.axis==axis]
        for side,y0 in [('positive',245),('negative',495)]:
            body+=text(x,y0,'係数の大きい側' if side=='positive' else '係数の小さい側',22)
            for i,r in enumerate(subset[subset.side==side].itertuples()):
                body+=text(x,y0+37+i*36,f'{r.category}',20)
                body+=text(x+450,y0+37+i*36,f'{r.loading:+.3f}',20,text_anchor='end')
    body+=text(65,777,'軸に街の性格を表す名前は付けません。符号は反転可能で、因果的な効果ではありません。',21)
    save('latent_axes','潜在軸の中身をカテゴリで確認','SVD成分係数の上下各5カテゴリ。第1軸の小さい側も正の係数になり得ます。',body)
    body=text(75,230,f'961カテゴリ → {dim}次元',62,font_weight='bold')
    body+=text(75,325,'街の見え方は変わる。',48)+text(75,400,'でも、安定性が上がるとは限らない。',42)
    row=metrics[metrics.dimension==dim].iloc[0]
    body+=text(75,520,f'細分類の近傍保持　{row.b_retention_mean:.1%}',39)
    body+=text(75,590,f'POI分割の一致　B {m["split_b_mean"]:.1%} → C {row.split_mean:.1%}',39)
    body+=text(75,710,'東京都内656駅・保存済みPOIで、圧縮の意味と限界を検証',28)
    save('cover_1600x900','街をベクトルで表すと何が変わる？','Pythonで地域Embeddingを試してみた',body)
    return paths
