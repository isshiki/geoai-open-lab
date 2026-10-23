"""Two introductory article figure sets; never writes Notebook 12's artifacts."""
import json
from html import escape
from pathlib import Path
from shapely.geometry import shape
from pyproj import Transformer
from .mesh_systems import ROOT, OUT, POINTS, run
from .standard_mesh_guide import encode

GUIDE=ROOT/'data/cache/regional_mesh/guide-v1'
COLORS=['#0072b2','#c16b00','#008568','#8b5ca6','#b64b58','#528491','#857224','#4f669e','#916540']


def text(x,y,s,size=26,anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}">{escape(str(s))}</text>'


def box(x,y,w,h,fill='#eef4f8',stroke='#b4c4cd'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" fill="{fill}" stroke="{stroke}"/>'


def save(out,name,title,sub,body,source='仕様：統計局・H3・S2・Microsoft・NGA・OGC。自作図／確認・作成 2026-10-23'):
    out.mkdir(parents=True,exist_ok=True)
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic",Meiryo,sans-serif;fill:#203b47}</style>'
    svg+=box(0,0,1600,900,'white','white')+text(45,65,title,34)+text(1540,65,'masahiko.info',23,'end')+text(45,115,sub,24)
    svg+=body+text(45,841,source,18)+text(45,876,'区画は用途に合わせて選択。商圏・生活圏の正解を示すものではありません。',19)+'</svg>'
    (out/(name+'.svg')).write_text(svg,encoding='utf8')


def cards(out,name,title,sub,items,source=None):
    body='';cols=2;h=178
    for i,(head,lines) in enumerate(items):
        x=45+(i%cols)*775;y=158+(i//cols)*210
        body+=box(x,y,735,h)+text(x+20,y+39,head,29)
        for j,line in enumerate(lines):body+=text(x+20,y+80+34*j,line,23)
    kwargs={} if source is None else {'source':source}
    save(out,name,title,sub,body,**kwargs)


def render():
    table=run();rows=json.loads((OUT/'cells.json').read_text(encoding='utf8'));tok=[r for r in rows if r['city']=='東京・吉祥寺']
    cards(OUT,'overview','「メッシュ」は、ひとつの規格ではない','統計・検索・表示・位置参照・分析では、区画を使う目的が違います。',[
        ('公的統計の共通区画',['標準地域メッシュ','コードを使って日本の統計を結合']),
        ('全球の階層インデックス',['H3・S2・Geohash','位置をIDへ変換して検索・集約']),
        ('Web地図の表示・配信',['XYZ・Quadkey','同じタイルを別のIDで表現']),
        ('位置を伝える参照グリッド',['MGRS','UTM / UPSに基づく位置参照']),
        ('目的に応じた分析区画',['独自の正方形・六角形','座標系・原点・幅を自分で固定']),
        ('概念と標準の枠組み',['OGC DGGS','個別のセルID方式とは区別する'])])
    trans=Transformer.from_crs(4326,6677,always_xy=True);lat,lon=POINTS['東京・吉祥寺'];cx,cy=trans.transform(lon,lat)
    body=''
    all_xy=[trans.transform(*p) for r in tok for p in shape(r['geometry']).exterior.coords]
    low=min(y-cy for x,y in all_xy); high=max(y-cy for x,y in all_xy)
    scale=120/(high-low); origin_y=50+high*scale
    for i,r in enumerate(tok):
        x=45+(i%3)*515;y=145+(i//3)*219;color=COLORS[i]
        body+=box(x,y,490,208)+text(x+15,y+30,r['scheme']+' / '+r['level'].split('・')[0],23)
        coords=[trans.transform(*p) for p in shape(r['geometry']).exterior.coords]
        pts=' '.join(f'{x+120+(px-cx)*scale:.2f},{y+origin_y-(py-cy)*scale:.2f}' for px,py in coords)
        body+=f'<polygon points="{pts}" fill="{color}" fill-opacity="0.22" stroke="{color}" stroke-width="2"/>'
        body+=f'<circle cx="{x+120}" cy="{y+origin_y}" r="4" fill="#202a32"/>'
        body+=text(x+255,y+95,f"{r['area_km2']:.4f} km²",25)+text(x+255,y+132,'黒点：共通の地点',20)
        body+=text(x+15,y+192,r['cell_id'],18)
    save(OUT,'boundaries','同じ地点でも、所属する区画は異なる','全パネル同縮尺・北が上。枠内の描画はEPSG:6677、面積はWGS84楕円体で計測。',body)
    body='';headers=['方式・選択レベル','実測 km²','直接の子数','近傍の定義','主な用途']
    xs=[55,535,765,955,1240]
    for x,h in zip(xs,headers):body+=text(x,170,h,23)
    uses=['統計結合','検索・集約','検索・被覆','位置索引','地図配信','地図配信','位置参照','分析区画','分析区画']
    for i,(r,use) in enumerate(zip(tok,uses)):
        y=205+i*62;body+=box(45,y-22,1510,55,'#eef4f8' if i%2==0 else '#fff')
        values=[r['scheme']+' '+r['level'].split('・')[0],f"{r['area_km2']:.4f}",str(r['child_count']) if r['parent_id'] else '未定義',f"辺共有 {r['neighbor_count']}",use]
        for x,value in zip(xs,values):body+=text(x,y+13,value,22)
    save(OUT,'comparison','ID・形・階層を、用途と一緒に読む','H3の親子は論理的な関係。Geohashは1文字で32分割。独自六角形には階層を設けていません。',body)
    cards(OUT,'choice','何をしたいかから、方式を選ぶ','解像度番号や「500m」という呼び名だけでは選べません。',[
        ('日本の公的統計を結合したい →',['標準地域メッシュ','測地系・年・コードの桁を合わせる']),
        ('全球のセルIDで集約したい →',['H3 / S2','形・親子関係・面積差を確認する']),
        ('文字列で位置を索引化したい →',['Geohash','文字数と実際の区画幅を確認する']),
        ('Web地図を分割して配信したい →',['XYZ / Quadkey','タイル用途と分析用途を区別する']),
        ('位置参照を共有したい →',['MGRS','桁数・UTM/UPS・ゾーンを確認する']),
        ('幅や原点を設計したい →',['独自グリッド','座標系・幅・原点を必ず残す'])])
    hierarchy=[('第1次','約80km','4桁'),('第2次','約10km','6桁'),('第3次','約1km','8桁'),('2分の1','約500m','9桁'),('4分の1','約250m','10桁'),('8分の1','約125m','11桁')]
    cards(GUIDE,'code','メッシュコードを、区切って読む','吉祥寺の代表点：53 | 39 | 4 | 4 | 4 | 6 | 1 | 4',[
        ('53・39：第1次の場所',['53：南端緯度×1.5','39：西端経度−100']),
        ('4・4：第2次の行・列',['南から4、 西から4（0始まり）','第1次を8×8へ分割']),
        ('4・6：第3次の行・列',['南から4、 西から6（0始まり）','第2次を10×10へ分割']),
        ('1：500mの四分割位置',['1=南西、2=南東、3=北西、4=北東','533944461（9桁）']),
        ('4：250mの四分割位置',['同じ1〜4の規則を繰り返す','5339444614（10桁）']),
        ('上位へは、階層ごとに桁を戻す',['250m→500mは末尾1桁を除く','第3次→第2次は末尾2桁を除く'])])
    cards(GUIDE,'conversion','緯度・経度 → コード → 境界','座標の基準を確認してから、同じ規則で変換します。',[
        ('① 緯度・経度',['35.703144… N / 139.579809… E','この例は既存の吉祥寺駅代表点']),
        ('② 500mメッシュコード',['encode_mesh(lat, lon, digits=9)','533944461']),
        ('③ 緯度経度の境界',['mesh_bounds("533944461")','西・南・東・北を取得']),
        ('④ 図に表示・面積を計算',['境界を必要な座標系へ変換','緯度経度の度数を面積にしない']),
        ('親へ集約する',['5339444614 → 533944461','250mの4区画を合計']),
        ('子へ分割する',['末尾へ1・2・3・4を追加','境界・コードで位置を照合'])])
    cards(GUIDE,'join','人口とPOIを、コードで結合する','共通キーでつながることが主題。人口とPOIの時点・意味は別です。',[
        ('① 公表人口：250mコード',['2020年国勢調査・JGD2011','欠損・秘匿・合算を確認']),
        ('② 500mの親へ合計',['子4区画の存在を検査','不足を0人に置き換えない']),
        ('③ POI座標 → 500mコード',['Overture 2026-09-23.0','登録数・カテゴリ構成を集計']),
        ('④ 同じコードで結合',['1行＝1メッシュ','人口列とPOI列を横に並べる']),
        ('保存済みの応用検証',['9メッシュ：人口28,487人','POI登録4,057件（約2.353km²）']),
        ('人口当たりの指標を作る場合',['分母0・欠損は未定義として扱う','需要・商圏・実店舗数とは言わない'])],source='応用：総務省統計局 2020年国勢調査、Overture / Foursquare 2026-09-23.0。既存Notebook 12の値。')
    # Diagram covers use large labels that remain legible at 800px.
    body=''
    for i,(name,size,digits) in enumerate(hierarchy):
        x=45+i*257
        body+=box(x,220,235,440)+text(x+117,270,name,27,'middle')+text(x+117,310,size,29,'middle')
        n = 8 if i == 0 else 10 if i == 1 else 2 if i < 5 else 1
        side=140/n
        for a in range(n):
            for b in range(n):body+=box(x+47+a*side,350+b*side,side-1,side-1,'#cde5f0' if a==0 and b==n-1 else '#f1f6f8')
        body+=text(x+117,550,digits,27,'middle')+text(x+117,600,encode(lat,lon,int(digits[:-1])),23,'middle')
        if i<5:body+=text(x+246,430,'→',18,'middle')
    body+=text(50,735,'分割：第1次→第2次は8×8、第2次→第3次は10×10、その後は2×2。',27)
    save(GUIDE,'hierarchy','標準地域メッシュの階層','各段階の区画を次の階層へ分割する模式図。各段階は同縮尺ではありません。',body,source='出典：総務省統計局「地域メッシュ統計の概要」。図の作成・変更：2026-10-23')
    for out,is_standard in [(OUT,False),(GUIDE,True)]:
        body=''
        labels=['標準地域メッシュ','H3','S2'] if not is_standard else ['1km：8桁','500m：9桁','250m：10桁']
        for i,label in enumerate(labels):
            x=55+i*515;body+=box(x,205,470,415)+text(x+235,260,label,35,'middle')
            if not is_standard:
                r=tok[i];coords=[trans.transform(*p) for p in shape(r['geometry']).exterior.coords]
                xs=[p[0] for p in coords];ys=[p[1] for p in coords];sc=0.20
                pts=' '.join(f'{x+235+(px-(max(xs)+min(xs))/2)*sc:.2f},{420-(py-(max(ys)+min(ys))/2)*sc:.2f}' for px,py in coords)
                body+=f'<polygon points="{pts}" fill="{COLORS[i]}" fill-opacity="0.2" stroke="{COLORS[i]}" stroke-width="3"/>'
                body+=text(x+235,575,f"{r['area_km2']:.4f} km²",31,'middle')
            else:
                n=2**i;side=220/n
                for a in range(n):
                    for b in range(n):body+=box(x+125+a*side,310+b*side,side-2,side-2,'#cde5f0' if (a,b)==[(0,0),(0,1),(1,2)][i] else '#f1f6f8')
                body+=text(x+235,575,['53394446','533944461','5339444614'][i],31,'middle')
            if i<2:body+=text(x+480,420,'→' if is_standard else '≠',34)
        body+=text(60,700,'位置 → コード → 境界 → 公的統計との結合' if is_standard else '統計・検索・表示・分析。目的によって区画を選ぶ。',36)
        body+=text(60,760,'約500mは厳密な正方形ではない。人口とPOIは最後に応用。' if is_standard else '選んだレベルの実測値。共通地点でも形・面積・IDが違う。',27)
        save(out,'cover_1600x900','日本の標準地域メッシュ入門' if is_standard else '地図のメッシュ入門',
             '1km・500m・250mメッシュをPythonで扱う' if is_standard else '標準地域メッシュ・H3・S2・独自グリッドをPythonで比較',body)
    return table


if __name__=='__main__':render()
