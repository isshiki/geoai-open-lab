"""Offline, data-backed article SVGs. No analysis input or earlier output is changed."""
from html import escape
import json
import numpy as np
import pandas as pd
from shapely.geometry import Point
from .crs_experiment import OUT, GEOD, load_world, polygons, project, transformer, station

BLUE='#0072b2'; ORANGE='#c16b00'; GREEN='#008568'


def text(x,y,s,size=26,anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">{escape(str(s))}</text>'


def box(x,y,w,h,fill='#eef4f8'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="#bdced7"/>'


def save(name,title,sub,body,source='実測：固定POI・N02駅代表点・pyproj / 作成 2026-10-24'):
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic",Meiryo,sans-serif;fill:#203b47}</style>'
    svg+=box(0,0,1600,900,'white')+text(45,65,title,34)+text(1540,65,'masahiko.info',23,'end')+text(45,115,sub,24)
    svg+=body+text(45,842,source,18)+text(45,877,'表示・距離・面積で選び分ける。どの投影法も万能ではありません。',20)+'</svg>'
    (OUT/(name+'.svg')).write_text(svg,encoding='utf8')


def cards(name,title,sub,items):
    body=''
    for i,(heading,lines) in enumerate(items):
        x=45+i%2*775;y=158+i//2*210
        body+=box(x,y,735,183)+text(x+20,y+40,heading,29)
        for j,line in enumerate(lines):body+=text(x+20,y+84+j*35,line,24)
    save(name,title,sub,body)


def path(g,xy,fill,stroke='#ffffff',width=.5):
    paths=[]
    for p in polygons(g):
        d=''
        for ring in [p.exterior,*p.interiors]:
            pts=[xy(x,y) for x,y,*_ in ring.coords]
            d+='M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in pts)+'Z '
        paths.append(f'<path d="{d}" fill="{fill}" fill-rule="evenodd" stroke="{stroke}" stroke-width="{width}"/>')
    return ''.join(paths)


def world_figure():
    world=load_world();world=world[~world.ADMIN.eq('Antarctica')]
    # Natural Earth splits dateline-crossing countries; fail rather than draw a spurious long edge.
    for g in world.geometry:
        for p in polygons(g):
            coords=list(p.exterior.coords)
            if any(abs(a[0]-b[0])>180 for a,b in zip(coords[:-1],coords[1:])):raise ValueError('Unsplit dateline edge')
    areas=pd.read_csv(OUT/'world_areas.csv');body=''
    for i,(code,title) in enumerate([(4326,'緯度経度をそのまま表示'),(3857,'Webメルカトル'),(8857,'イコールアース')]):
        left=35+i*520;body+=box(left,158,500,630,'#f3f7fa')+text(left+18,200,title,26)+text(left+18,235,f'EPSG:{code}',23)
        shapes=[g if code==4326 else project(g,code) for g in world.geometry]
        xmin=min(g.bounds[0] for g in shapes);xmax=max(g.bounds[2] for g in shapes)
        ymin=min(g.bounds[1] for g in shapes);ymax=max(g.bounds[3] for g in shapes)
        scale=min(460/(xmax-xmin),390/(ymax-ymin));cx=left+250;cy=465
        xy=lambda x,y:(cx+(x-(xmin+xmax)/2)*scale,cy-(y-(ymin+ymax)/2)*scale)
        for (_,row),g in zip(world.iterrows(),shapes):
            color=GREEN if row.CONTINENT=='Africa' else ORANGE if row.ADMIN=='Greenland' else BLUE if row.ADMIN=='Japan' else '#c1cbd2'
            body+=path(g,xy,color)
        if code==4326:
            lines=['単位は「度」。面積計算には使わない','緯度・経度とも同じ縮尺で描画']
        else:
            ratios={r.region:r.projected_km2/r.geodesic_km2 for r in areas[areas.crs.eq(code)].itertuples()}
            lines=[f'地上面積比：Africa {ratios["Africa"]:.3f}倍',f'Greenland {ratios["Greenland"]:.3f}倍 / Japan {ratios["Japan"]:.3f}倍']
        for j,s in enumerate(lines):body+=text(left+15,714+j*35,s,20)
    save('world_projections','同じ世界でも、面積の見え方が変わる','緑：アフリカ　橙：グリーンランド　青：日本。各パネル内の相対面積を比較。',body,
         'Made with Natural Earth 5.1.1 (Public domain)。全パネルで南極を除外。粗い境界であり公式国土面積ではない。')


def poi_figure():
    cfg=station();cx,cy=cfg['center_x'],cfg['center_y'];lon,lat=cfg['longitude'],cfg['latitude']
    f=pd.read_csv(OUT/'poi_membership.csv');body=''
    az=np.linspace(0,360,721);lo,la,_=GEOD.fwd(np.full(len(az),lon),np.full(len(az),lat),az,np.full(len(az),500.))
    gx,gy=transformer(6677).transform(lo,la)
    from shapely.geometry import Polygon
    circles={'geodesic':Polygon(zip(gx,gy)),'6677':Point(cx,cy).buffer(500,quad_segs=512)}
    mx,my=transformer(3857).transform(lon,lat)
    from shapely.ops import transform
    circles['3857']=transform(transformer(6677,3857).transform,Point(mx,my).buffer(500,quad_segs=512))
    for i,(key,title,color) in enumerate([('geodesic','測地線距離 500m',GREEN),('6677','EPSG:6677 の500m',BLUE),('3857','EPSG:3857 の500m',ORANGE)]):
        left=35+520*i;body+=box(left,158,500,630,'#f8fafb')+text(left+20,200,title,27)+text(left+20,245,f'{int(f[key].sum()):,} 件',34)
        xy=lambda x,y:(left+250+(x-cx)*.38,485-(y-cy)*.38)
        body+=path(circles[key],xy,'none',color,3)
        for r in f[(abs(f.x-cx)<550)&(abs(f.y-cy)<550)].itertuples():
            px,py=xy(r.x,r.y);selected=bool(getattr(r,'geodesic')) if key=='geodesic' else bool(f.loc[r.Index,key])
            body+=f'<circle cx="{px:.2f}" cy="{py:.2f}" r="1.5" fill="{color if selected else "#cbd2d8"}"/>'
        x,y=xy(cx,cy);body+=f'<path d="M{x-8},{y}h16 M{x},{y-8}v16" stroke="#111" stroke-width="3"/>'
        body+=text(left+25,728,'＋ 駅代表点　色付き点：採用POI',21)+text(left+25,765,'同縮尺／上は6677の北（N）',21)
    o=pd.read_csv(OUT/'poi_overlap.csv');j=o.loc[o.b.astype(str).eq('3857'),'jaccard'].iloc[0]
    save('poi_500m','「500m」の計算方法で、採用するPOIが変わる',f'測地線と6677は一致。3857との共通率 Jaccard={j:.4f}。基図なし・位置は6677で統一。',body,
         'Overture 2026-09-23.0（取得2026-10-15、Foursquare等）／駅：国土数値情報N02-25加工。営業中店舗数ではない。')


def render():
    cards('overview','地球の位置を、計算できる座標へ','EPSGコードは座標参照系などを識別する番号。変換手順の名前ではありません。',[
        ('1 地球 → 楕円体・測地基準系',['地球の形を近似し、位置を測る基準を定める','例：WGS 84、JGD2011']),
        ('2 地理座標系 → 緯度・経度',['角度で地球上の位置を表す','例：EPSG:4326 / EPSG:6668']),
        ('3 投影法 → 平面への写し方',['球面・楕円体を平らな図へ写す','面積・形・距離をすべて保つことはできない']),
        ('4 投影座標系 → 平面上の位置',['基準系・投影法・原点・軸・単位を組み合わせる','例：東京都の今回の分析はEPSG:6677']),
        ('5 EPSGコードで指定 → 座標変換',['always_xy=True なら入力は経度、緯度','CRSのラベル変更だけでは数値は変換されない']),
        ('6 POI → 距離・面積・地域特徴量',['件数 ÷ 適切に求めた面積 = 登録密度','基準をそろえて比較・検索・クラスタリング'])])
    d=pd.read_csv(OUT/'distances.csv');east=d[d.point.eq('east500')].set_index('crs')
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    cards('coordinates','緯度経度・表示用・分析用を分ける','吉祥寺駅から測地線で東へ500m進めた点を、同じ基準点と比較。',[
        ('保存：緯度経度 EPSG:4326',['経度139.579810°、緯度35.703144°','角度の差をメートルとして読まない']),
        ('Web表示：EPSG:3857',[f'東へ500m → 平面では{east.loc[3857,"projected_m"]:.2f}m',f'地上距離との差 +{east.loc[3857,"error_pct"]:.2f}%']),
        ('東京の分析：EPSG:6677',[f'東へ500m → 平面では{east.loc[6677,"projected_m"]:.2f}m',f'地上距離との差 {east.loc[6677,"error_m"]:.3f}m']),
        ('CRSの指定と変換',['set_crs(4326)：元の座標の意味を指定','to_crs(6677)：その意味に従って数値を変換']),
        ('軸順にも注意',['always_xy=True → 経度、緯度／東、北','6677の公式軸順（北、東）とは区別']),
        ('往復誤差と位置精度は別',['往復誤差はこの点で0m（数値計算上）',f'選択された基準系変換の公称精度は{m["operation_accuracy_m"]:.0f}m'])])
    world_figure();poi_figure()
    density=pd.read_csv(OUT/'synthetic_density.csv');web=density[density.crs.eq(3857)].set_index('location')
    cards('features_flow','投影法は、GeoAIの手前で特徴量へ影響する','合成例：地上面積100km²・POI 1,000件（真の密度10件/km²）を3緯度に配置。',[
        ('POI座標 → 範囲へ割り当て',['距離や境界が変わると、採用POIが変わる','件数・カテゴリ構成にも影響しうる']),
        ('面積 → 登録密度',['面積が膨らむと、計算される密度は下がる','メートル単位の座標系でも要注意']),
        ('3857の面積で割った密度',[f'赤道 {web.loc["Equator","apparent_density"]:.2f} / 東京 {web.loc["Tokyo","apparent_density"]:.2f}',f'北緯65° {web.loc["High latitude","apparent_density"]:.2f} 件/km²']),
        ('8857の面積で割った密度',['3地点とも約10.00件/km²','等積でも距離・角度・形は万能ではない']),
        ('特徴量 → 比較・分類',['密度や集中度が変われば、結果も変わりうる','影響の大きさは入力と用途による']),
        ('TF-IDF・SVD・K-meansそのもの',['座標系は直接の入力ではない','ただし、前段のPOI集合・特徴量に依存'])])
    cards('selection','何をしたいか、から座標系を選ぶ','対象地域・単位・許容誤差を確認してから計算します。',[
        ('位置を保存・交換したい → 緯度経度',['提供元のCRSと軸順を確認','4326と6668を無条件に同じとしない']),
        ('Webの背景地図に重ねたい → 3857',['タイル表示に便利','画面上の長さ・面積を地上の値としない']),
        ('東京周辺の短い距離 → 6677等',['対象地域に適した平面座標系を選ぶ','適用範囲外へそのまま広げない']),
        ('広域の距離 → 楕円体の測地線',['pyproj.Geodで緯度経度から計算','道路距離や徒歩時間とは別の指標']),
        ('世界の面積比較 → 8857等',['等積図法、または測地面積で計算','距離・形・角度の保存とは別']),
        ('最後に → 基準をそろえて検証',['測地線・測地面積との誤差を調べる','CRS・入力版・許容誤差を記録'])])
    body=''
    for i,(label,value,color) in enumerate([('緯度経度','位置を保存',GREEN),('Web表示','EPSG:3857',ORANGE),('東京の分析','EPSG:6677',BLUE)]):
        x=55+i*515;body+=box(x,180,475,185)+text(x+25,233,label,32)+text(x+25,300,value,36)
    body+=text(800,426,'同じ「500m」でも、採用するPOIが違う',38,'middle')
    counts=pd.read_csv(OUT/'poi_summary.csv').set_index('method').poi_count
    for i,(label,key,color) in enumerate([('測地線・6677','6677',BLUE),('Webメルカトル','3857',ORANGE)]):
        y=490+110*i;w=counts[key]/counts['6677']*760
        body+=text(65,y+38,label,30)+f'<rect x="390" y="{y}" width="{w}" height="55" fill="{color}"/>'+text(1200,y+40,f'{counts[key]:,}件',38)
    body+=text(65,758,'位置 → 距離・面積 → 密度 → 地域特徴量・GeoAI',34)
    save('cover_1600x900','地図の座標系入門','緯度経度・投影法・EPSGをPythonで理解する',body,
         '吉祥寺の実測／Overture 2026-09-23.0・N02-25加工。POI登録数であり営業中店舗数ではありません。')


if __name__=='__main__':render()
