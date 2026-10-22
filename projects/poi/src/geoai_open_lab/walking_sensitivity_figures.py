"""Offline SVG article figures; all displayed statistics read from audited tables."""
import json
import numpy as np
import pandas as pd
from .walking_sensitivity import OUT, load_results, CONTROLS
from .region_figures import text
from .clustering_figures import rect

NAMES=['distributions','count_composition','controls','examples','cover_1600x900']
LABELS={'square':'1km四方','straight400':'直線400m','straight500':'直線500m','straight800':'直線800m','road400':'道路400m','road500':'道路500m','road800':'道路800m'}
BLUE='#0072b2'; ORANGE='#b66b00'; GREEN='#008461'


def line(x1,y1,x2,y2,color='#cbd5db',width=2):
    return f'<path d="M{x1},{y1} L{x2},{y2}" fill="none" stroke="{color}" stroke-width="{width}"/>'


def circle(x,y,r,color):return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}"/>'


def figures():
    audit,counts,pairs,distributions=load_results()
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    d=distributions[distributions.cohort.eq('union_ge30')]
    def save(name,title,subtitle,body):
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic","Meiryo",sans-serif;fill:#203b47}</style>'
        svg+=rect(0,0,1600,900,'#f8fafb')+text(45,65,title,33,font_weight='bold')+text(1540,65,'masahiko.info',23,text_anchor='end',fill='#71828b')+text(45,110,subtitle,21)
        footer=[f"Overture {m['release']}（取得 {m['poi_acquired_utc'][:10]}、補完 {m['supplement_acquired_utc'][:10]}）| POI登録数・営業中店舗数ではない",
                '© OpenStreetMap contributors / ODbL | 2026-10-01版（取得10-03）| https://www.openstreetmap.org/copyright',
                '駅：N02-25（CC BY 4.0）加工 | FSQ由来：Apache-2.0・同梱NOTICE | 加工2026-10-22']
        svg+=body+''.join(text(45,816+i*27,s,17) for i,s in enumerate(footer))+'</svg>'
        (OUT/(name+'.svg')).write_text(svg,encoding='utf8')
    body=''
    for tick in np.arange(0,1.01,.2):
        x=545+tick*720;body+=line(x,165,x,705)+text(x,735,f'{tick:.1f}',20,text_anchor='middle')
    body+=text(1340,152,'中央値 / 駅数',21)
    for i,r in enumerate(d.itertuples()):
        y=200+i*65;color=BLUE if i<3 else (ORANGE if i<6 else GREEN)
        body+=text(45,y+7,LABELS[r.first]+' → '+LABELS[r.second],23)
        body+=line(545+720*r.jaccard_min,y,545+720*r.jaccard_max,y,color,2)
        body+=line(545+720*r.jaccard_p10,y,545+720*r.jaccard_p90,y,color,12)+circle(545+720*r.jaccard_median,y,7,'#203b47')
        k=pairs[(pairs.region_id=='n02-003584')&(pairs['first']==r.first)&(pairs['second']==r.second)].iloc[0]
        x=545+720*k.jaccard;body+=f'<path d="M{x},{y-12} l9,12 l-9,12 l-9,-12 Z" fill="#a83257"/>'
        body+=text(1340,y+7,f'{r.jaccard_median:.3f} / {r.valid_stations}',23)
    body+=text(45,774,'細線：最小–最大　太線：P10–P90　黒丸：中央値　赤菱形：吉祥寺　／ Jaccard = 共通数 ÷ 和集合数',21)
    save('distributions','距離の変更と、範囲定義の変更を分ける','各比較の和集合30件以上・有効駅。上6行は距離上限のみ、下2行は定義の比較。',body)
    body=''
    for i,(a,b) in enumerate([('straight500','road500'),('square','road800')]):
        sub=pairs[(pairs['first']==a)&(pairs['second']==b)&pairs.valid&~pairs.low_poi]
        body+=text(60+i*780,175,LABELS[a]+' と '+LABELS[b],27,font_weight='bold')
        # Joint scatter: count difference vs composition total variation, common scales across panels.
        for tick in [-6000,-3000,0,3000,6000]:
            x=100+i*780+(tick+6000)/12000*620;body+=line(x,220,x,660)+text(x,695,str(tick),18,text_anchor='middle')
        for tick in [0,.25,.5,.75,1]:
            y=660-tick*440;body+=line(100+i*780,y,720+i*780,y)+text(85+i*780,y+5,f'{tick:.2f}',18,text_anchor='end')
        assert sub.count_difference.abs().max()<=6000
        for r in sub.itertuples():
            if np.isfinite(r.composition_tvd):body+=circle(100+i*780+(r.count_difference+6000)/12000*620,660-r.composition_tvd*440,3.3,BLUE if i==0 else GREEN)
        med=sub.composition_tvd.median();body+=text(100+i*780,735,f'構成差TVD中央値 {med:.3f} ／ n={len(sub)}',23)
    body+=text(45,775,'横軸：第2条件 − 第1条件の登録数　縦軸：構成差TVD（0=同じ、1=完全に異なる）',22)
    save('count_composition','件数の違いと、カテゴリ構成の違い','1点＝1駅グループ。既存6群＋その他＋欠損。和集合30件以上・接続可能駅。',body)
    body=text(55,170,'対照駅（事前固定）',25)+text(435,170,'道路への接続',23)+text(760,170,'直線500 / 道路500',23)+text(1170,170,'四方 / 道路800',23)
    for i,suffix in enumerate(CONTROLS):
        rid='n02-'+suffix;r=audit[audit.region_id==rid].iloc[0];y=225+i*63
        body+=line(50,y+20,1510,y+20)+text(55,y,r.station_name,27)+text(435,y,f'{r.source_connector_m:.1f}m',25)
        for x,(a,b) in zip([760,1170],[('straight500','road500'),('square','road800')]):
            p=pairs[(pairs.region_id==rid)&(pairs['first']==a)&(pairs['second']==b)].iloc[0]
            label=f'J={p.jaccard:.3f}' if p.valid else '接続上限超過'
            if p.low_poi:label+='（低件数）'
            body+=text(x,y,label,23)
    body+=text(55,775,'東京は n02-003766。対照駅は結果から選んでいません。接続100m超の駅の道路比較は未定義。',21)
    save('controls','同じ条件でも、駅によって一致度は異なる','全駅表を残し、事前に固定した8駅を省略せず表示。JはJaccard係数。',body)
    selected=json.loads((OUT/'examples.json').read_text(encoding='utf8'))
    stations=[dict(region_id='n02-003584',station_name='吉祥寺',selection='基準')]+selected
    body=''
    for i,s in enumerate(stations):
        x0=55+i*520;y0=245;size=455
        r=audit[audit.region_id==s['region_id']].iloc[0]
        t=pd.read_parquet(OUT/'stations'/f"{s['region_id']}.parquet")
        p=pairs[(pairs.region_id==s['region_id'])&pairs['first'].eq('square')&pairs['second'].eq('road800')].iloc[0]
        body+=text(x0,165,s['station_name']+'（'+{'基準':'基準','low':'最小','high':'最大'}[s['selection']]+'）',27,font_weight='bold')+text(x0,205,f'J={p.jaccard:.3f} ／ 和集合{p.union:,}件',23)
        body+=rect(x0,y0,size,size,'white')
        for q in t[t.square|t.road800].itertuples():
            color=GREEN if q.square and q.road800 else (BLUE if q.square else ORANGE)
            body+=circle(x0+(q.dx+800)/1600*size,y0+(800-q.dy)/1600*size,1.9,color)
        margin=size*300/1600
        body+=f'<rect x="{x0+margin}" y="{y0+margin}" width="{size*1000/1600}" height="{size*1000/1600}" fill="none" stroke="{BLUE}" stroke-width="2"/>'
        body+=circle(x0+size/2,y0+size/2,5,'#000')+text(x0+size-10,y0+25,'北↑',19,text_anchor='end')
        body+=text(x0,735,f'四方のみ{p.n_first-p.shared} ／ 道路のみ{p.n_second-p.shared}',22)
    body+=text(55,775,'緑：共通　青：四方のみ　橙：道路のみ　黒：駅代表点 ／ 各図1.6km幅。原因はこの図だけでは断定しない。',20)
    save('examples','全駅から規則で選んだ、高一致・低一致の例','正方形対道路800m、和集合30件以上。最小・最大を選び、同率はID順。',body)
    r=d[d['first'].eq('square')&d['second'].eq('road800')].iloc[0]
    same=d[d['first'].eq('straight500')&d['second'].eq('road500')].iloc[0]
    k=pairs[pairs.region_id.eq('n02-003584')&pairs['first'].eq('square')&pairs['second'].eq('road800')].iloc[0]
    body=text(70,195,'吉祥寺の「ほぼ同じ」は、他の駅でも同じ？',36,font_weight='bold')
    for x,value,label,color in [(70,f'{k.jaccard:.3f}','吉祥寺：四方 vs 道路800m',GREEN),(590,f'{r.jaccard_median:.3f}','全体の中央値：同じ比較',BLUE),(1110,f'{same.jaccard_median:.3f}','直線500m vs 道路500m',ORANGE)]:
        body+=rect(x,245,430,225,'white')+text(x+25,335,value,68,fill=color,font_weight='bold')+text(x+25,415,label,22)
    body+=text(70,545,f'656駅を確認 → 道路比較 {m["valid_road_stations"]}駅有効',34)
    body+=text(70,605,f'四方と道路800m：P10–P90 = {r.jaccard_p10:.3f}–{r.jaccard_p90:.3f}',30)
    body+=text(70,665,'距離の大きさと範囲の定義を分けて検証',32,font_weight='bold')
    body+=text(70,730,'道路到達圏は正解ではない。MAUPの反証でもない。',28)
    body+=text(70,775,'Jaccard＝共通するPOI数 ÷ 両条件の和集合POI数。中央値は和集合30件以上。',21)
    save('cover_1600x900','駅周辺の範囲を変えると、どこまで一致する？','固定OSM道路網 × 保存済みOverture Places ／ Notebook 11の独立した補足検証',body)
    return [OUT/(n+'.svg') for n in NAMES]

if __name__=='__main__':figures()
