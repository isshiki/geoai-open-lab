"""Source-backed SVG figures. Walking reachability is shown as road segments, not hulls."""
import json
import numpy as np
import pandas as pd
from .walking_range import OUT
from .region_figures import text,COLORS
from .clustering_figures import rect

NAMES=['ranges','composition','distance_zoom','conditions','cover_1600x900']
LABELS={'square':'1km四方','circle':'半径500m','walk5':'徒歩5分（400m）','walk10':'徒歩10分（800m）'}
PALETTE={'square':'#0072b2','circle':'#b36b00','walk5':'#008461','walk10':'#993d89'}
GROUPS=['restaurant','cafe','bar','fashion','beauty','food_store','other','missing']
JP=['食事','カフェ','バー','衣料','美容等','食品小売','その他','欠損']

def figures():
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'));center=np.array(m['center'])
    f=pd.read_csv(OUT/'pois.csv');roads=pd.read_csv(OUT/'roads.csv');reachable=pd.read_csv(OUT/'reachable.csv')
    summary=pd.read_csv(OUT/'summary.csv').set_index('condition');examples=json.loads((OUT/'examples.json').read_text(encoding='utf8'))
    output=[]
    def save(name,title,subtitle,body):
        footer=[f"Overture {m['release']}（取得 {m['poi_acquisition_utc'][:10]}）| POI登録数・営業中店舗数ではない",
                f"© OpenStreetMap contributors / ODbL | 2026-10-01版 | https://www.openstreetmap.org/copyright | 取得 {m['road_source']['source_acquired_utc'][:10]}",
                '駅：国土数値情報 N02-25（CC BY 4.0）加工 | FSQ由来：Apache-2.0・同梱NOTICE | 加工2026-10-22']
        svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic","Meiryo",sans-serif;fill:#203b47}</style>'
        svg+=rect(0,0,1600,900,'#f8fafb')+text(50,65,title,34,font_weight='bold')+text(1540,65,'masahiko.info',24,text_anchor='end',fill='#71828b')+text(50,110,subtitle,22)
        svg+=body+''.join(text(50,814+i*28,t,17) for i,t in enumerate(footer))+'</svg>'
        path=OUT/(name+'.svg');path.write_text(svg,encoding='utf8');output.append(path)
    def panel(condition,x,y,size):
        # All panels share a 2km square frame and north-up projection.
        def xy(a,b):return x+(a-center[0]+1000)/2000*size,y+(1000-b+center[1])/2000*size
        body=rect(x,y,size,size,'#ffffff')
        for r in roads.itertuples():
            if max(abs(r.x1-center[0]),abs(r.x2-center[0]),abs(r.y1-center[1]),abs(r.y2-center[1]))>1000:continue
            a,b=xy(r.x1,r.y1);c,d=xy(r.x2,r.y2)
            body+=f'<path d="M{a},{b} L{c},{d}" stroke="#dbe1e5" fill="none" stroke-width=".7"/>'
        color=PALETTE[condition]
        if condition=='square':body+=f'<rect x="{x+size/4}" y="{y+size/4}" width="{size/2}" height="{size/2}" fill="none" stroke="{color}" stroke-width="3"/>'
        elif condition=='circle':body+=f'<circle cx="{x+size/2}" cy="{y+size/2}" r="{size/4}" fill="none" stroke="{color}" stroke-width="3"/>'
        else:
            for r in reachable[reachable.minutes.eq(5 if condition=='walk5' else 10)].itertuples():
                a,b=xy(r.x1,r.y1);c,d=xy(r.x2,r.y2);body+=f'<path d="M{a},{b} L{c},{d}" stroke="{color}" stroke-width="2"/>'
        for r in f[f[condition]].itertuples():
            a,b=xy(r.x,r.y);body+=f'<circle cx="{a}" cy="{b}" r="1.2" fill="{color}" opacity=".5"/>'
        body+=text(x+size-15,y+25,'北↑',17,text_anchor='end')+f'<circle cx="{x+size/2}" cy="{y+size/2}" r="5" fill="#111" stroke="white"/>'
        body+=text(x+10,y+size-12,'黒点：駅代表点 ／ 図幅2km',16)
        return body
    body=''
    for i,c in enumerate(LABELS):
        x=45+i*390;body+=text(x,170,LABELS[c],26,font_weight='bold')+text(x,210,f"{int(summary.loc[c,'poi_count']):,}件",30)
        body+=panel(c,x,245,350)
    body+=text(60,650,'点＝対象POI。徒歩圏は道路ノード間の概略線で表示。面積を持つポリゴンは作りません。',24)
    body+=text(60,695,f"駅の道路接続：{m['source_snap_m']:.1f}m。駅・POIの接続距離も400m / 800mに含めます。",24)
    body+=text(60,740,'駅出口・改札や実際の歩行経路を確認した結果ではありません。',24)
    save('ranges','同じ駅でも「周辺」の形は変わる','吉祥寺駅代表点からの4条件を、同じ縮尺・北上で比較',body)
    body=''
    for i,c in enumerate(LABELS):
        y=190+i*135;count=int(summary.loc[c,'poi_count']);body+=text(60,y,LABELS[c],26)+text(60,y+38,f'{count:,}件',28)
        body+=rect(340,y-25,320*count/summary.poi_count.max(),33,PALETTE[c])
        x=730
        for j,g in enumerate(GROUPS):
            share=summary.loc[c,g+'_share'];w=750*share;color=COLORS[{'other':'__OTHER__','missing':'__MISSING__'}.get(g,g)]
            body+=rect(x,y-25,w,45,color)
            if share>=.05:body+=text(x+w/2,y+5,f'{share:.0%}',18,text_anchor='middle',fill='white')
            x+=w
        body+=text(730,y+55,f"食事 {summary.loc[c,'restaurant_share']:.1%} ／ カフェ {summary.loc[c,'cafe_share']:.1%}",22)
    for j,g in enumerate(GROUPS):
        x=60+j*185;body+=rect(x,735,17,17,COLORS[{'other':'__OTHER__','missing':'__MISSING__'}.get(g,g)])+text(x+25,751,JP[j],21)
    save('composition','件数とカテゴリ構成を分けて読む','左：POI登録数 ／ 右：各条件の全登録数を分母とした構成比',body)
    body='';example=next((r for r in examples if r['example']=='square_not_walk10'),examples[0])
    path=np.array(example['path']);lo=path.min(axis=0)-60;hi=path.max(axis=0)+60;span=max(hi-lo);middle=(lo+hi)/2
    def zoomxy(a,b):return 70+(a-middle[0]+span/2)/span*590,160+(span/2-b+middle[1])/span*590
    for r in roads.itertuples():
        if min(r.x1,r.x2)<middle[0]-span/2 or max(r.x1,r.x2)>middle[0]+span/2 or min(r.y1,r.y2)<middle[1]-span/2 or max(r.y1,r.y2)>middle[1]+span/2:continue
        a,b=zoomxy(r.x1,r.y1);c,d=zoomxy(r.x2,r.y2);body+=f'<path d="M{a},{b} L{c},{d}" stroke="#cbd4dc" fill="none"/>'
    for j,(a,b) in enumerate(zip(path,path[1:])):
        x1,y1=zoomxy(*a);x2,y2=zoomxy(*b);dash='stroke-dasharray="7 4"' if j in [0,len(path)-2] else ''
        body+=f'<path d="M{x1},{y1} L{x2},{y2}" stroke="#993d89" stroke-width="4" {dash}/>'
    x1,y1=zoomxy(*path[0]);x2,y2=zoomxy(*path[-1]);body+=f'<path d="M{x1},{y1} L{x2},{y2}" stroke="#0072b2" stroke-width="2" stroke-dasharray="3 6"/>'
    body+=f'<circle cx="{x1}" cy="{y1}" r="7" fill="#111"/><circle cx="{x2}" cy="{y2}" r="7" fill="#993d89"/>'
    body+=text(760,200,'1km四方に入るが、徒歩10分では対象外',27,font_weight='bold')
    for j,t in enumerate([f"直線：{example['straight_m']:.0f}m",f"接続を含む道路距離：{example['road_distance_m']:.0f}m",f"POI側の接続：{example['connector_m']:.1f}m",'青の点線：直線距離','紫の実線：道路 ／ 紫の破線：接続','代表点から計算。入口の実測ではありません。','差集合のうち直線距離が最短の接続済みPOI。','線路等が原因とは、この図だけで断定しません。']):body+=text(760,265+j*55,t,23)
    save('distance_zoom','直線で近くても、道路では回り道になる','固定道路網の計算例。道路はノード間の概略線。背景タイルは使用していません。',body)
    body=''
    for j,t in enumerate(['条件','判定','登録数','到達道路延長']):body+=text([60,440,1070,1280][j],185,t,26,font_weight='bold')
    for i,c in enumerate(LABELS):
        y=260+i*105;body+=text(60,y,LABELS[c],25)+text(440,y,{'square':'東西・南北 各500m','circle':'直線距離 ≤ 500m','walk5':'接続を含む距離 ≤ 400m','walk10':'接続を含む距離 ≤ 800m'}[c],24)+text(1070,y,f"{int(summary.loc[c,'poi_count']):,}",27)
        body+=text(1280,y,f"{summary.loc[c,'road_length_m']/1000:.2f}km" if c.startswith('walk') else '対象外',26)
    body+=text(60,700,'道路延長は往復を重複せず、到達可能な辺の一部分も計上。接続線は含みません。',24)
    body+=text(60,750,'徒歩80m/分を仮定。待ち時間・坂・階段の負荷・改札・混雑は含みません。',24)
    save('conditions','範囲の条件を先に決める','「駅勢圏の正解」ではなく、今回の問いに対する定義',body)
    body=panel('walk10',60,175,520)
    body+=text(650,210,'駅周辺は半径500mでよい？',40,font_weight='bold')
    body+=text(650,270,'Python × OpenStreetMap',30)
    for i,c in enumerate(LABELS):body+=rect(650,320+i*78,12,46,PALETTE[c])+text(685,350+i*78,f"{LABELS[c]}：{int(summary.loc[c,'poi_count']):,}件",30)
    body+=text(650,690,'用途を決めて、範囲を比べる。',32,font_weight='bold')+text(650,745,'実際の徒歩時間・需要を保証するものではありません。',23)
    save('cover_1600x900','駅周辺の範囲を比べる','吉祥寺1駅のPOI登録を、固定範囲と道路到達距離で比較',body)
    return output

if __name__=='__main__':figures()
