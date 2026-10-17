"""Seven reproducible SVG figures from locally verified embedding outputs."""
import json
from pathlib import Path
import pandas as pd
from .region_figures import text
from .clustering_figures import rect,line,document

METHOD_COLORS = {"A":"#0072b2", "B":"#d55e00", "C":"#009e73"}
METHOD_NAMES = {"A":"A：前回の8特徴量", "B":"B：961カテゴリのTF-IDF", "C":"C：64次元の地域Embedding"}
# Group colors deliberately differ from method A/B/C colors.
COLORS = ["#7956a5", "#a15b75", "#697378"]

def arrow(x,y,dx=1):
    return f'<path d="M{x},{y} h{dx*24} m{-dx*8},-8 l{dx*8},8 l{-dx*8},8" stroke="#69818d" stroke-width="3" fill="none"/>'

def tiles(x,y,color,n=8):
    return "".join(rect(x+j*30,y,24,42,color) for j in range(n))

def poi_icon(x,y):
    body=rect(x,y,260,70,"#eef2f4")
    for j,label in enumerate(["食","店","美","他"]):
        body+=rect(x+12+j*62,y+14,48,42,"#dce5ea")+text(x+36+j*62,y+43,label,23,text_anchor="middle")
    return body



def save_embedding_figures(out):
    out=Path(out);m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    dim=m['selected_dimension'];metrics=pd.read_csv(out/'dimension_metrics.csv')
    ranks=[pd.read_csv(out/f'ranking_{mode}.csv').head(10) for mode in ('A','B',f'C{dim}')]
    paths=[]
    def save(name,title,subtitle,body):
        svg=document(title,subtitle,body,m).replace('集計・作図 2026-10-16','集計・作図 2026-10-17')
        p=out/(name+'.svg');p.write_text(svg,encoding='utf8');paths.append(p)
    # 1 station = one row; blocks are schematic, never invented measured values.
    body=''
    for j,mode in enumerate(('A','B','C')):
        x=60+j*515;color=METHOD_COLORS[mode];number={'A':8,'B':961,'C':dim}[mode]
        body+=rect(x,175,480,490,'#ffffff')+rect(x,175,480,8,color)
        body+=text(x+24,235,METHOD_NAMES[mode],25,font_weight='bold',style='fill:'+color)
        body+=text(x+240,365,str(number),88,font_weight='bold',text_anchor='middle',style='fill:'+color)
        body+=text(x+240,415,'個の数値 / 1駅',29,text_anchor='middle')
        body+=tiles(x+35,465,color)+text(x+290,496,'…' if mode!='A' else '',30)
        notes={'A':['密度・6カテゴリ群・集中度','前回記事の比較方式'],
               'B':['細かなカテゴリを重み付け','圧縮せず比較する'],
               'C':['BをSVDで圧縮・L2正規化','数値の向きで比較する']}
        for k,t in enumerate(notes[mode]):body+=text(x+24,565+k*45,t,27)
    body+=text(60,735,'同じ656駅・1km四方。色付きの小箱は列の模式図です。',26)
    body+=text(60,775,'AとBは入力が異なる比較、BとCは圧縮の比較。距離の数値を方式間で比べません。',23)
    save('representations','1駅を、何個の数値で表す？','A＝青 / B＝オレンジ / C＝緑を、記事全体で統一します。',body)
    # Set membership is computed by ID, not station name (two Ikebukuro groups).
    sets=[set(t.region_id) for t in ranks];all_three=set.intersection(*sets);bc=sets[1]&sets[2]
    assert len(all_three)==5 and len(bc)==7
    body=''
    for j,(mode,table) in enumerate(zip(('A','B','C'),ranks)):
        x=60+j*515;color=METHOD_COLORS[mode]
        body+=rect(x,157,480,50,color)+text(x+18,192,METHOD_NAMES[mode],24,style='fill:white',font_weight='bold')
        for i,r in enumerate(table.itertuples()):
            y=243+i*43; memberships=sum(r.region_id in group for group in sets)
            if r.region_id in all_three:tag='ABC共通';fill='#e5ecef'
            elif r.region_id in bc:tag='BC共通';fill='#f0f3f5'
            elif memberships==1:tag='単独';fill='#fff'
            else:tag='AB共通';fill='#fff'
            body+=rect(x,y-27,480,39,fill)+text(x+12,y,f'{i+1}  {r.station_name}',27,font_weight='bold' if r.region_id in all_three else 'normal')
            body+=text(x+284,y,r.region_id.replace('n02-',''),17)+text(x+370,y,tag,20,font_weight='bold')
    body+=text(60,710,'ABC共通：町田・立川南・立川北・立川・北千住（5駅）',27,font_weight='bold')
    body+=text(60,749,'BC共通7駅＝上の5駅＋中目黒・池袋(003390)。単独＝1方式だけに登場。',24)
    body+=text(60,783,'Aは前回記事の方式。数字はID末尾。同名駅・候補同士の重複を別の街の発見と数えない。',21)
    save('neighbors','吉祥寺に似ている上位10駅を比べる','自駅と吉祥寺の1km四方に重なる駅は除外。集合の共通数は駅グループIDで確認。',body)
    body=''
    labels=[('explained_variance','説明分散',['元データの違いを','どの程度表せたか']),
            ('b_retention_mean','上位駅の保持率',['圧縮前Bの上位10駅が','圧縮後Cに何駅残ったか']),
            ('split_mean','分割一致率',['POIを半分ずつに分けても','上位10駅はどの程度共通か'])]
    for j,(field,title,notes) in enumerate(labels):
        x=65+j*515;body+=text(x,190,title,32,font_weight='bold')
        for k,note in enumerate(notes):body+=text(x,232+k*32,note,24)
        for i,r in enumerate(metrics.itertuples()):
            y=307+i*70;v=getattr(r,field)
            body+=text(x,y+23,f'{r.dimension}次元',23)+rect(x+112,y,265*v,29,METHOD_COLORS['C'])
            body+=text(x+450,y+24,f'{v:.1%}',24,text_anchor='end')
    body+=rect(65,600,1470,68,'#fff')+text(85,644,'分割一致率の比較',26)
    body+=text(470,644,f'B：{m["split_b_mean"]:.1%}',30,style='fill:'+METHOD_COLORS['B'])
    row=metrics[metrics.dimension==dim].iloc[0]
    body+=text(760,644,f'C（64次元）：{row.split_mean:.1%}',30,style='fill:'+METHOD_COLORS['C'])
    body+=text(65,713,'安定性＝POIを半分ずつにしても、似ている上位駅の結果が再現されるか。',26)
    body+=text(65,752,'ここでは上位10駅の共通数÷10を平均。順位の並びが完全一致する割合ではありません。',23)
    body+=text(65,784,f'バーは0〜100%。緑はC。乱数seed変更での上位駅一致は64次元で{row.seed_mean:.1%}（別の確認）。',21)
    save('dimensions','64個の数値で、何がどれだけ残る？','説明分散も保持率も「正解率」ではありません。圧縮で失う違いもあります。',body)
    a=pd.read_csv(out/'assignments.csv');s=pd.read_csv(out/'cluster_summary.csv')
    scale=min(930/(a.x.max()-a.x.min()),510/(a.y.max()-a.y.min()));body=''
    for r in a.itertuples():
        x=75+(r.x-a.x.min())*scale;y=725-(r.y-a.y.min())*scale
        body+=f'<circle cx="{x}" cy="{y}" r="4" fill="{COLORS[r.cluster-1]}" fill-opacity=".7"/>'
    body+=text(75,190,'N ↑',24)
    for r in s.itertuples():
        y=245+(r.cluster-1)*130;body+=rect(1040,y-24,22,22,COLORS[r.cluster-1])
        body+=text(1080,y,f'群{r.cluster}：{r.count}駅',29)+text(1080,y+45,r.representatives.split(' / ')[0],25)
    body+=text(1040,670,f'旧分類とのARI：{m["cluster_ari"]:.3f}',25)+text(1040,713,'ARIは正解率ではない',22)
    body+=line(80,760,80+10000*scale,760)+text(80,790,'10 km / EPSG:6677',18)
    save('clusters','Embeddingでも3群に分類する',f'{dim}次元でK-means、k=3。点は駅代表点。群番号は密度中央値順。A・B・Cの方式色とは別。',body)
    axes=pd.read_csv(out/'axis_categories.csv');body=''
    for j,axis in enumerate([1,2,3]):
        x=65+j*510;body+=text(x,190,f'潜在軸 {axis}',29,font_weight='bold')
        subset=axes[axes.axis==axis]
        for side,y0 in [('positive',245),('negative',495)]:
            body+=text(x,y0,'係数の大きい側' if side=='positive' else '係数の小さい側',22)
            for i,r in enumerate(subset[subset.side==side].itertuples()):
                body+=text(x,y0+37+i*36,f'{r.category}',20)
                body+=text(x+450,y0+37+i*36,f'{r.loading:+.3f}',20,text_anchor='end')
    body+=text(65,777,'軸名は付けません。符号は反転可能。rental_kioskの具体的な対象は未確認です。',21)
    save('latent_axes','潜在軸の中身をカテゴリで確認','SVD成分係数の上下各5カテゴリ。第1軸の小さい側も正の係数になり得ます。',body)
    # Explanatory flow, with explicit schematic labels and no invented observations.
    body=''
    cards=[(60,165,'1  駅周辺にあるPOI',['食事・お店・サービスなど']),
           (570,165,'2  カテゴリ別に数える',['961種類のカテゴリ別件数']),
           (1080,165,'3  TF-IDFで重み付け',['どの駅にも多いカテゴリの影響を','弱め、その駅で目立つものを強める']),
           (1080,470,'4  TruncatedSVD',['元の情報をなるべく残しながら','961列を64列へ圧縮する']),
           (570,470,'5  64個の数値で表現',['L2正規化で長さをそろえる']),
           (60,470,'6  似た駅を探す',['数値の並びの向きが近い駅を検索'])]
    for x,y,title,notes in cards:
        body+=rect(x,y,460,253,'#ffffff')+text(x+20,y+40,title,27,font_weight='bold')
        for k,note in enumerate(notes):body+=text(x+20,y+184+k*31,note,22)
    body+=poi_icon(100,240)
    body+=tiles(610,250,METHOD_COLORS['B'])+text(870,282,'… 961列',24)
    for j,w in enumerate([85,180,125]):body+=rect(1120,235+j*28,w,18,METHOD_COLORS['B'])
    body+=text(1320,295,'模式図',20)
    body+=text(1130,590,'961列 → 64列',39,style='fill:'+METHOD_COLORS['C'])
    body+=tiles(610,555,METHOD_COLORS['C'])+text(870,587,'… 64個',24)
    body+=text(95,575,'吉祥寺 → 1位 町田',31,style='fill:'+METHOD_COLORS['C'])
    body+=arrow(530,290)+arrow(1040,290)
    body+='<path d="M1310,425 v30 m-8,-8 l8,8 l8,-8" stroke="#69818d" stroke-width="3" fill="none"/>'
    body+=arrow(1068,590,-1)+arrow(558,590,-1)
    body+=text(60,761,'地域Embedding：街の特徴を比較できる数値の並び。小箱・棒は仕組みを示す模式図。',24)
    body+=text(60,790,'TF-IDFは相対的な重み付け。多いカテゴリが必ず小さくなるわけではありません。',21)
    save('embedding_flow','POIから「街の数値プロフィール」へ','街の特徴を、比較や検索に使える数値の並びへ変換します。',body)
    body=''
    for j,(title,mode) in enumerate([('駅周辺のPOI',None),('961列の表','B'),('64個の数値','C'),('似た駅を検索','C')]):
        x=60+j*390;color=METHOD_COLORS.get(mode,'#647f8c')
        body+=rect(x,200,330,235,'#fff')+rect(x,200,330,7,color)+text(x+20,252,title,29,font_weight='bold')
        if j==0:body+=poi_icon(x+25,285)
        elif j<3:body+=tiles(x+25,295,color)+text(x+25,389,'TF-IDF' if j==1 else 'SVD ＋ L2正規化',25)
        else:body+=text(x+25,312,'吉祥寺 → 町田',30)+text(x+25,370,'1位',45,font_weight='bold',style='fill:'+color)
        if j<3:body+=arrow(x+345,320)
    body+=text(60,493,'町田は A・B・C すべてで1位',38,font_weight='bold')
    for j,mode in enumerate(('A','B','C')):
        x=60+j*515;color=METHOD_COLORS[mode]
        body+=text(x,546,METHOD_NAMES[mode],25,style='fill:'+color,font_weight='bold')
        body+=text(x,590,'2位 '+ranks[j].iloc[1].station_name,32)
    body+=text(60,659,'表現方法を変えると、順位も変わる。',37,font_weight='bold')
    body+=text(60,712,'圧縮しても、安定性が上がるとは限らなかった。',34)
    body+=text(60,764,f'POI半分ずつの上位10駅の一致：B {m["split_b_mean"]:.1%} → C {row.split_mean:.1%}（小箱は模式図）',25)
    save('cover_1600x900','街をベクトルで表すと何が変わる？','POIカテゴリから街を64個の数値へ変換し、吉祥寺に似た駅を検索。',body)
    return paths
