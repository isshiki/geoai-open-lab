"""Article figures for three station-range definitions, all data kept local."""
import json
import numpy as np
import pandas as pd
from .station_range_methods import OUT,METHODS,STATIONS,ws
from .region_figures import text
from .clustering_figures import rect
from .walking_sensitivity_figures import line,circle

NAMES=['shinjuku_maps','station_comparison','purpose','distributions','cover_1600x900']
LABELS={'square':'1km四方','straight500':'直線500mの円','road500':'道路距離500m'}
COLORS={'square':'#0072b2','straight500':'#b66b00','road500':'#008461'}


def figures():
    manifest=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    for name,h in manifest['output_sha256'].items():assert ws.digest(OUT/name)==h
    counts=pd.read_csv(OUT/'conditions.csv');pairs=pd.read_csv(OUT/'comparisons.csv');dist=pd.read_csv(OUT/'distributions.csv')
    audit=pd.read_csv(ws.OUT/'stations.csv');station=audit[audit.region_id.eq(STATIONS[0])].iloc[0]
    f=pd.read_parquet(ws.OUT/'stations'/f'{STATIONS[0]}.parquet')
    roads=pd.read_csv(OUT/'shinjuku_roads.csv');reachable=pd.read_csv(OUT/'shinjuku_reachable500.csv')
    def save(name,title,subtitle,body):
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic","Meiryo",sans-serif;fill:#203b47}</style>'
        svg+=rect(0,0,1600,900,'#f8fafb')+text(45,65,title,33,font_weight='bold')+text(1540,65,'masahiko.info',23,text_anchor='end',fill='#71828b')+text(45,110,subtitle,21)+body
        footer=['Overture 2026-09-23.0（取得10-15、補完10-17）| POI登録数・営業中店舗数ではない',
                '© OpenStreetMap contributors / ODbL | 2026-10-01版 | https://www.openstreetmap.org/copyright',
                '駅：N02-25（CC BY 4.0）加工 | FSQ由来：Apache-2.0・同梱NOTICE | 加工2026-10-22']
        svg+=''.join(text(45,816+i*27,t,17) for i,t in enumerate(footer))+'</svg>'
        (OUT/(name+'.svg')).write_text(svg,encoding='utf8')
    def count(rid,method):return int(counts[(counts.region_id==rid)&counts.condition.eq(method)].poi_count.iloc[0])
    def pair(rid,a,b):return pairs[(pairs.region_id==rid)&pairs['first'].eq(a)&pairs['second'].eq(b)].iloc[0]
    body=''
    for i,method in enumerate(METHODS):
        x0=55+520*i;y0=245;size=440;color=COLORS[method]
        def xy(x,y):return x0+(x-station.x+600)/1200*size,y0+(600-y+station.y)/1200*size
        body+=text(x0,170,LABELS[method],28,font_weight='bold')+text(x0,215,f'{count(STATIONS[0],method):,}件',32)
        body+=rect(x0,y0,size,size,'white')
        for r in roads.itertuples():
            if max(abs(r.x1-station.x),abs(r.x2-station.x),abs(r.y1-station.y),abs(r.y2-station.y))>600:continue
            a,b=xy(r.x1,r.y1);c,d=xy(r.x2,r.y2);body+=line(a,b,c,d,'#d2dce1',.7)
        if method=='square':body+=f'<rect x="{x0+size/12}" y="{y0+size/12}" width="{size*5/6}" height="{size*5/6}" fill="none" stroke="{color}" stroke-width="3"/>'
        if method=='straight500':body+=f'<circle cx="{x0+size/2}" cy="{y0+size/2}" r="{size*5/12}" fill="none" stroke="{color}" stroke-width="3"/>'
        if method=='road500':
            for r in reachable.itertuples():
                a,b=xy(r.x1,r.y1);c,d=xy(r.x2,r.y2);body+=line(a,b,c,d,color,1.8)
        for r in f[f[method]].itertuples():
            a,b=xy(r.x,r.y);body+=circle(a,b,1.7,color)
        body+=circle(x0+size/2,y0+size/2,5,'#111')+text(x0+size-10,y0+25,'北↑',19,text_anchor='end')
    for i,(a,b) in enumerate([('square','straight500'),('square','road500'),('straight500','road500')]):
        r=pair(STATIONS[0],a,b)
        body+=text(55+520*i,725,f'{LABELS[a]} × {LABELS[b]}',21)+text(55+520*i,765,f'Jaccard {r.jaccard:.3f}（共通{r.shared:,}件）',23)
    save('shinjuku_maps','新宿を「周辺」とする3つの定義','同じ縮尺・北上・図幅1.2km。点＝採用POI、黒点＝駅代表点。道路はノード間の概略線。',body)
    body=''
    for i,(rid,name) in enumerate(zip(STATIONS,['新宿（主例）','吉祥寺（対照）'])):
        x=65+780*i;body+=text(x,175,name,32,font_weight='bold')
        for j,method in enumerate(METHODS):body+=text(x,220+j*35,f'{LABELS[method]}：{count(rid,method):,}件',24)
        for j,(a,b) in enumerate([('square','straight500'),('square','road500'),('straight500','road500')]):
            r=pair(rid,a,b);y=365+j*105
            body+=text(x,y,LABELS[a]+' / '+LABELS[b],23)+rect(x,y+18,600,22,'#e3e9ec')+rect(x,y+18,600*r.jaccard,22,COLORS[b])
            body+=text(x,y+72,f'J={r.jaccard:.3f}　件数差 {r.count_difference:+,}　TVD={r.composition_tvd:.3f}',23)
    body+=text(65,735,'棒の長さ：Jaccard（0～1）。件数差は第2条件−第1条件。TVDは8分類の構成差（0=同じ）。',21)
    body+=text(65,778,'両駅とも11bの事前指定対照駅。今回の主例選択は追加検証結果を踏まえた説明用の選択。',21)
    save('station_comparison','駅によって、方式への感度は異なる','新宿だけを全体の代表にせず、吉祥寺と全656駅の分布も合わせて読む。',body)
    body=''
    headings=['大量の駅を同条件で比較','駅からの直線的な近さ','徒歩での到達しやすさ']
    notes=[['固定面積で集計・格子化しやすい','角は中心から約707m離れる','商圏や徒歩圏とは限らない'],['中心からの距離条件が明快','道路の迂回・接続は表さない','500m円は約0.785km²'],['歩ける道路上の距離で判定','駅・POIの接続距離も含める','道路データと出発点に依存']]
    for i,method in enumerate(METHODS):
        x=45+i*520;color=COLORS[method];body+=rect(x,155,490,535,'white')+text(x+25,205,headings[i],27,font_weight='bold')+text(x+25,250,LABELS[method],28)
        cx=x+245;cy=355
        if method=='square':
            body+=rect(cx-60,cy-60,120,120,color)
        elif method=='straight500':body+=circle(cx,cy,60,color)
        else:
            for dx,dy,ex,ey in [(-100,0,100,0),(0,-60,0,60),(-65,0,-65,55),(55,0,55,-45)]:body+=line(cx+dx,cy+dy,cx+ex,cy+ey,color,6)
        body+=circle(cx,cy,7,'#111')+text(x+25,465,'概念図（実際の地図ではない）',18)
        for j,note in enumerate(notes[i]):body+=text(x+25,525+j*55,note,23)
    body+=text(60,735,'用途に合わせる目安であり、唯一の対応ではない。円も同半径なら大量比較に使える。',23)
    body+=text(60,778,'道路距離を正解にしない。出口・地下通路・通行条件は未確認。時間換算には歩行速度の仮定が必要。',21)
    save('purpose','駅周辺を定義する3方式の使い分け','何を知りたいかを先に決める。形・面積・道路接続の違いを条件として明示する。',body)
    body=''
    for i,r in enumerate(dist[dist.cohort.ne('union_lt30')].itertuples()):
        y=190+i*88;label='全656駅' if r.cohort=='all' else '和集合30件以上'
        body+=text(45,y,LABELS[r.first]+' / '+LABELS[r.second],22)+text(45,y+30,f'{label}（n={r.valid_stations}）',20)
        body+=line(690, y,1290,y,'#d4dde3',2)+line(690+600*r.jaccard_min,y,690+600*r.jaccard_max,y,COLORS[r.second],2)
        body+=line(690+600*r.jaccard_p10,y,690+600*r.jaccard_p90,y,COLORS[r.second],12)+circle(690+600*r.jaccard_median,y,7,'#203b47')
        body+=text(1350,y+8,f'{r.jaccard_median:.3f}',26)
    for tick in [0,.25,.5,.75,1]:body+=text(690+600*tick,735,f'{tick:g}',20,text_anchor='middle')
    body+=text(45,780,'Jaccard：細線は最小–最大、太線はP10–P90、黒丸は中央値。右端も中央値。',23)
    save('distributions','3つの比較を、同じ形式で656駅に適用','全駅と和集合30件以上を分ける。正方形と円の比較には面積差も含まれる。',body)
    body=text(70,195,'何を知りたいかで、駅周辺の範囲を選ぶ',37,font_weight='bold')
    for i,method in enumerate(METHODS):
        x=70+i*510;body+=rect(x,245,450,300,'white')+text(x+25,300,LABELS[method],31,font_weight='bold')+text(x+25,385,f'{count(STATIONS[0],method):,}件',58)+text(x+25,460,headings[i],23)+rect(x+25,505,390,9,COLORS[method])
    r=pair(STATIONS[0],'straight500','road500');k=pair(STATIONS[1],'straight500','road500')
    body+=text(70,625,f'直線500m × 道路500m：新宿 J={r.jaccard:.3f} ／ 吉祥寺 J={k.jaccard:.3f}',31)
    body+=text(70,695,'道路距離は正解ではなく、目的に応じた選択肢。',31,font_weight='bold')
    body+=text(70,765,'新宿のPOI登録数。Jaccard＝共通数÷和集合数。駅代表点は実際の出口ではない。',22)
    save('cover_1600x900','駅周辺を定義する3方式の使い分け','正方形・円・道路距離を、新宿を主例に比べる。',body)
    return [OUT/(n+'.svg') for n in NAMES]

if __name__=='__main__':figures()
