"""Article figures drawn from the tutorial examples and recorded observations."""
from html import escape
import json
from .geojson_tutorial import OUT, example_frame

BLUE='#0072b2'; ORANGE='#c16b00'; GREEN='#008568'


def text(x,y,value,size=28,color='#203b47',anchor='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" text-anchor="{anchor}">{escape(str(value))}</text>'


def box(x,y,w,h,fill='#eef4f8'):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="{fill}" stroke="#bdced7"/>'


def save(name,title,subtitle,body):
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic",Meiryo,sans-serif}</style>'
    svg+=box(0,0,1600,900,'white')+text(45,65,title,34)+text(1540,65,'masahiko.info',23,anchor='end')
    svg+=text(45,118,subtitle,25)+body
    svg+=text(45,840,'GeoAI Open Lab ｜ 説明用の架空データ・外部地図データなし ｜ 実行条件：GeoPandas 1.1.4 / Shapely 2.1.2',18)
    svg+=text(45,879,'点・線・面は実際の施設位置、通行可能な経路、土地や施設の境界を保証しません。',21)+'</svg>'
    (OUT/f'{name}.svg').write_text(svg,encoding='utf8')


def cards(name,title,subtitle,items):
    body=''
    for i,(heading,lines) in enumerate(items):
        x=45+(i%2)*775;y=165+(i//2)*310
        body+=box(x,y,735,270)+text(x+25,y+48,heading,30)
        for j,line in enumerate(lines):body+=text(x+25,y+100+j*46,line,26)
    save(name,title,subtitle,body)


def map_body(left=70,top=180,width=900,height=590):
    frame=example_frame().to_crs(6677)
    xmin,ymin,xmax,ymax=frame.total_bounds
    scale=min((width-130)/(xmax-xmin),(height-140)/(ymax-ymin))
    xy=lambda x,y:(left+width/2+(x-(xmin+xmax)/2)*scale,top+height/2-(y-(ymin+ymax)/2)*scale)
    body=box(left,top,width,height,'#f7fafb')
    for x in range(int(xmin//100)*100,int(xmax)+101,100):
        px,_=xy(x,ymin)
        if left+15<px<left+width-15:body+=f'<path d="M{px},{top+20} V{top+height-20}" stroke="#dde5e8"/>'
    colors=[BLUE,ORANGE,GREEN]
    for index in [2,1,0]:
        g=frame.geometry.iloc[index];color=colors[index]
        if g.geom_type=='Point':
            x,y=xy(g.x,g.y);body+=f'<circle cx="{x}" cy="{y}" r="11" fill="{color}" stroke="white" stroke-width="3"/>'
            body+=text(x-20,y-23,'Point',25,color,'end')
        else:
            coords=g.exterior.coords if g.geom_type=='Polygon' else g.coords
            d='M'+' L'.join(f'{x:.2f},{y:.2f}' for x,y in [xy(*p) for p in coords])
            if g.geom_type=='Polygon':d+='Z'
            body+=f'<path d="{d}" fill="{GREEN if index==2 else "none"}" fill-opacity=".18" stroke="{color}" stroke-width="5"/>'
            p=g.representative_point();x,y=xy(p.x,p.y)
            body+=text(x,y+(55 if index==1 else 10),g.geom_type,26,color,'middle')
    body+=text(left+width-60,top+52,'N ↑',25)
    bar=100*scale
    body+=f'<path d="M{left+35},{top+height-40} h{bar}" stroke="#203b47" stroke-width="4"/>'
    body+=text(left+35,top+height-55,'100m（6677）',20)
    return body


def render():
    report=json.loads((OUT/'results.json').read_text(encoding='utf8'))
    cards('reading_flow','PythonでGeoJSONを読み込む','同じファイルでも、辞書として読むか、地理データの表として読むかで使い方が変わります。',[
        ('1　GeoJSONファイル',['UTF-8のテキスト','FeatureCollectionに3つのFeature','coordinatesは［経度, 緯度］']),
        ('2　json.load() → 辞書',['type・featuresを確認','geometryとpropertiesを取り出す','JSON構文の読込と地理的な正しさは別']),
        ('3　GeoPandas → GeoDataFrame',['from_features() または read_file()','1つのFeatureが表の1行に','geometry列と属性列を一緒に扱う']),
        ('4　保存 → 再読込 → 確認',['WGS 84へそろえて保存','形状と属性が残ったか照合','図にして位置と内容も確かめる'])])
    body=''
    for i,(kind,color) in enumerate([('Point',BLUE),('LineString',ORANGE),('Polygon',GREEN)]):
        y=220+i*170
        body+=box(50,y,600,140)+text(75,y+42,f'Feature {i+1}：{kind}',30,color)
        body+=text(75,y+90,'geometry ＋ properties.name',27)
        body+=text(700,y+80,'→',48)
        body+=box(800,y,745,140)+text(825,y+42,f'表の{i+1}行目：{report["geometry_types"][i]}',30,color)
        body+=text(825,y+90,example_frame()['name'].iloc[i]+' ｜ fictional = True',25)
    save('dataframe','GeoJSONとGeoDataFrameの対応','FeatureCollection → 表 ／ properties → 属性列 ／ geometry → 地理形状の列',body)
    cards('validation_layers','検証は4段階に分ける','「読めた」だけでは、正しい地図データと判断できません。',[
        ('1　JSON構文',['カンマ・括弧・引用符','json.load()で読み込めるか','GeoJSONの構造はここでは未確認']),
        ('2　GeoJSONの基本構造',['FeatureCollection・座標配列','Polygonの閉じ方・座標の数値範囲','この記事の簡易チェックは限定的']),
        ('3　幾何学的な妥当性',['自己交差などを確認','Shapelyの is_valid','緯度経度の意味や実在性は分からない']),
        ('4　座標の意味・内容',['想定地域にあるか、出典は何か','東京の例なのに別地域なら要確認','実際の経路・境界は別の根拠が必要'])])
    labels={'normal':'正常例','broken_json':'カンマ不足','swapped_lon_lat':'経緯度を逆転',
            'unclosed_polygon':'Polygon未閉鎖','self_intersection':'自己交差Polygon',
            'wrong_place_valid_range':'範囲内数値・別の場所'}
    body=box(45,165,1510,590)
    for x,label in [(65,'例'),(400,'json'),(570,'from_features'),(885,'read_file'),(1120,'is_valid*')]:body+=text(x,210,label,27)
    lookup={r['case']:r for r in report['cases']}
    for i,key in enumerate(labels):
        r=lookup[key];y=275+i*77
        body+=text(65,y,labels[key],27)
        def yes(value):return '—' if value is None else '読める' if value else 'エラー'
        body+=text(400,y,yes(r['json_ok']),25)+text(570,y,yes(r['from_features_ok']),25)+text(885,y,yes(r['read_file_ok']),25)
        valid=r['shapely_valid'];value='—' if valid is None else 'True' if all(valid) else 'False'
        body+=text(1120,y,value+('（補完後）' if key=='unclosed_polygon' else ''),25)
    body+=text(55,797,'* shape()で生成後。未閉鎖は自動で閉じる／経緯度逆転は幾何だけでは検出できない。',24)
    save('error_examples','読める・形が妥当・内容が正しいは別','GeoPandas 1.1.4＋pyogrio 0.13.0で実測。—は前段の失敗により未評価。',body)
    body=map_body()
    for i,(kind,name,color) in enumerate(zip(report['geometry_types'],example_frame()['name'],[BLUE,ORANGE,GREEN])):
        y=230+i*165
        body+=text(1030,y,kind,32,color)+text(1030,y+48,name,29)+text(1030,y+87,'架空の説明用データ',23)
    save('final_map','Point・LineString・Polygonを同じ地図へ','東京駅付近を想定した架空の例。表示はEPSG:6677、上は座標系の北。背景地図なし。',body)
    body=map_body(45,200,780,550)
    body+=text(880,240,'読む → 作る → 保存する',38)
    body+=text(880,305,'GeoJSON → Python → 地図',32,BLUE)
    for i,line in enumerate(['3つのFeatureを1つの表へ','形状と属性の往復一致を確認','読めても、正しいとは限らない']):
        body+=box(870,365+i*115,675,90)+text(895,420+i*115,line,30)
    save('cover_1600x900','GeoJSONをPythonで扱う','読み込み・作成・検証・地図表示',body)


if __name__=='__main__':render()
