"""Code-native SVG illustrations and measured maps for Notebook 12."""
from html import escape
import json
import pandas as pd
from pyproj import Transformer
from .regional_mesh import OUT, mesh_polygon, encode_mesh


def text(x,y,value,size=26,anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">{escape(str(value))}</text>'


def rect(x,y,w,h,fill='#eef4f8',stroke='#466075'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}" stroke="{stroke}" stroke-width="2"/>'


def save(name,title,subtitle,body):
    footer=text(45,817,'人口：総務省統計局「令和2年国勢調査に関する地域メッシュ統計」を加工（2020-10-01）',18)
    footer+=text(45,846,'POI：Overture Maps Foundation / Foursquare（Apache-2.0・NOTICE）2026-09-23.0、取得2026-10-15',18)
    footer+=text(45,875,'駅：国土数値情報N02-25（CC BY 4.0）を加工。図の作成・変更：2026-10-23／人口とPOIは時点・意味が異なる',17)
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic",Meiryo,sans-serif;fill:#203b47}</style>'
    svg+=rect(0,0,1600,900,'#fff','#fff')+text(45,65,title,34)+text(1540,65,'masahiko.info',23,'end')+text(45,115,subtitle,24)+body+footer+'</svg>'
    (OUT/(name+'.svg')).write_text(svg,encoding='utf8')


def map_body(table,meta,overlay=False):
    shapes=[mesh_polygon(str(c),True) for c in table.mesh_code]
    xmin=min(p.bounds[0] for p in shapes);ymin=min(p.bounds[1] for p in shapes)
    xmax=max(p.bounds[2] for p in shapes);ymax=max(p.bounds[3] for p in shapes)
    scale=min(900/(xmax-xmin),580/(ymax-ymin))
    xy=lambda x,y:(70+(x-xmin)*scale,755-(y-ymin)*scale)
    body='';labels=''
    maximum=table.population_2020.max()
    for row,p in zip(table.itertuples(),shapes):
        points=' '.join(f'{xy(x,y)[0]:.3f},{xy(x,y)[1]:.3f}' for x,y in p.exterior.coords)
        t=row.population_2020/maximum
        color=f'rgb({int(240-150*t)},{int(247-100*t)},{int(251-35*t)})'
        body+=f'<polygon points="{points}" fill="{color}" stroke="#344b60" stroke-width="2"/>'
        cx,cy=xy(p.centroid.x,p.centroid.y)
        labels+=text(cx,cy-25,row.mesh_code,21,'middle')+text(cx,cy+8,f'{row.population_2020:,}人',29,'middle')
        if overlay:labels+=text(cx,cy+44,f'POI {row.poi_count:,}件',25,'middle')
    if overlay:
        points=pd.read_parquet(OUT/'poi_assignments.parquet')
        trans=Transformer.from_crs(4326,6677,always_xy=True)
        px,py=trans.transform(points.lon.to_numpy(),points.lat.to_numpy())
        for x,y in zip(px,py):
            x,y=xy(x,y)
            body+=f'<circle cx="{x:.3f}" cy="{y:.3f}" r="1.6" fill="#a23900" fill-opacity="0.55"/>'
    sx,sy=xy(meta['station']['center_x'],meta['station']['center_y'])
    body+=f'<path d="M {sx-9} {sy} h 18 M {sx} {sy-9} v 18" stroke="#b04700" stroke-width="5"/>'
    # Exact old projected AOI, shown only as a reference outline.
    ax,ay=xy(meta['station']['center_x']-500,meta['station']['center_y']+500)
    body+=f'<rect x="{ax}" y="{ay}" width="{1000*scale}" height="{1000*scale}" fill="none" stroke="#b04700" stroke-width="3" stroke-dasharray="9 6"/>'
    body+='<g style="paint-order:stroke;stroke:white;stroke-width:3px;stroke-linejoin:round">'+labels+'</g>'
    body+=text(1030,195,'北 ↑  / EPSG:6677',25)
    lines=['同じ9桁コードで結合',f'500mメッシュ：{len(table)}区画',f'人口：{int(table.population_2020.sum()):,}人',f'POI登録：{int(table.poi_count.sum()):,}件',f'全体面積：約{table.area_km2.sum():.3f}km²','濃い青ほど人口が多い','茶色の点：POIの登録位置' if overlay else '数値は各区画に表示','＋ 吉祥寺駅の代表点','破線：既存の1km四方','境界で切らず区画全体を採用']
    for i,line in enumerate(lines):body+=text(1030,260+i*47,line,24)
    body+=f'<path d="M 70 780 h {500*scale}" stroke="#203b47" stroke-width="5"/>'+text(80+500*scale,785,'500m',19)
    return body


def render():
    table=pd.read_csv(OUT/'mesh500.csv',dtype={'mesh_code':str})
    meta=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    body=''
    for i,(label,n,sub) in enumerate([('第3次：約1km',1,'8桁'),('2分の1：約500m',2,'9桁'),('4分の1：約250m',4,'10桁')]):
        x=70+i*510;body+=text(x,210,label,29)+text(x,260,sub,28)
        for a in range(n):
            for b in range(n):body+=rect(x+a*360/n,310+b*360/n,360/n,360/n,'#dfedf5')
        body+=text(x,725,f'同じ親区画を{n*n}区画に分割',24)
        if i<2:body+=text(x+405,480,'→',50)
    save('hierarchy','地域メッシュは、同じ区画を細かく分ける','模式図。緯度・経度の間隔で決まるため、メートル単位の厳密な正方形ではありません。',body)
    code=encode_mesh(meta['station']['latitude'],meta['station']['longitude'],10)
    chunks=[(code[:4],'第1次','緯度×1.5の整数部','経度の整数部−100'),(code[4:6],'第2次','南→北 0〜7','西→東 0〜7'),(code[6:8],'第3次','南→北 0〜9','西→東 0〜9'),(code[8],'500m','1:南西 / 2:南東','3:北西 / 4:北東'),(code[9],'250m','500m区画を','同じ規則で4分割')]
    body=text(60,200,'吉祥寺駅代表点のコードを分解',30)
    for i,(v,label,a,b) in enumerate(chunks):
        x=55+i*310;body+=rect(x,260,285,350)+text(x+142,340,v,53,'middle')+text(x+20,410,label,29)+text(x+20,480,a,21)+text(x+20,525,b,21)
    body+=text(60,690,'左から4桁 → 6桁 → 8桁 → 9桁 → 10桁。末尾1桁を落とすと250mから500mへ。',28)
    body+=text(60,750,'先頭のゼロを保持するため、コードは数値ではなく文字列で扱います。',26)
    save('code','メッシュコードは「場所の住所」','2分の1地域メッシュは、e-Stat定義書では「4次（500m）メッシュ」とも表記。',body)
    save('population','500mメッシュへ、2020年人口を合計する','各区画の250mメッシュ4個を合計。今回の36個はすべて記録があり、秘匿・合算フラグは0。',map_body(table,meta))
    save('population_poi','人口とPOIを、同じ500mメッシュへ重ねる','色は人口、各区画の「POI」は登録数。人の住む数と施設の登録数を同じものとして扱いません。',map_body(table,meta,True))
    body=rect(60,180,710,550)+rect(830,180,710,550)
    for x,title,lines in [(90,'標準地域メッシュ',['全国共通の緯度・経度の区画','メッシュコードで公的統計を結合','駅は区画の中央とは限らない','500mは、おおよその大きさ','時点・測地系・定義の照合が必要']), (860,'駅中心の範囲',['正方形：駅ごとに同じ条件で比較','円：駅からの直線的な近さ','道路距離：道路を通る到達しやすさ','目的に応じて境界が変わる','公的統計のコードとは直接一致しない'])]:
        body+=text(x,245,title,32)
        for i,line in enumerate(lines):body+=text(x,330+i*67,line,27)
    body+=text(70,775,'どちらも唯一正しい街の範囲ではない。今回は共通コードによる結合を学ぶ。',29)
    save('purpose','標準の区画と、駅中心の範囲は目的が違う','MAUPや道路到達圏の再検証は行わず、データをつなぐ共通単位を確認します。',body)
    body=rect(60,195,440,300)+rect(580,195,440,300)+rect(1100,195,440,300)
    for x,a,b,c in [(85,'250m人口',f"{meta['children_count']}区画を合計",'2020年国勢調査'),(605,'500mコード',f"{meta['mesh_count']}区画で結合",'Pythonで共通のキーへ'),(1125,'POI登録数',f"{meta['poi_count']:,}件を割当",'Overture固定release')]:
        body+=text(x,270,a,36)+text(x,355,b,31)+text(x,440,c,25)
    body+=text(520,360,'→',44)+text(1040,360,'←',44)
    body+=text(80,590,f"人口 {meta['population_2020']:,}人 ｜ POI {meta['poi_count']:,}件",48)+text(80,660,'同じメッシュコードなら、異なるデータを並べられる。',35)
    body+=text(80,740,f"吉祥寺周辺の{meta['mesh_count']}区画／約{meta['area_km2']:.3f}km²。人口は2020年、POIは2026年。",27)
    save('cover_1600x900','地域メッシュとは？ Pythonで人口とPOIを重ねる','500mメッシュを、統計をつなぐ共通の区画として使ってみる。',body)
    return [OUT/(n+'.svg') for n in ('hierarchy','code','population','population_poi','purpose','cover_1600x900')]


if __name__=='__main__':render()
