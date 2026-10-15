"""Source-backed offline SVGs. Rasterization uses a browser, not image generation."""
from pathlib import Path
import json
import shutil
import pandas as pd
from .region_figures import text

NAMES={'main':'主指標','density_only':'密度のみ','standard':'平均・標準偏差',
       'no_density':'密度なし','no_concentration':'集中度なし'}


def document(title, subtitle, body, manifest, *, cover=False):
    footer=[f"出典：Overture Maps Foundation | release {manifest['release']} | 取得 {manifest['acquisition_utc'][:10]}",
        '駅：国土交通省 国土数値情報 N02-25（CC BY 4.0）を加工 | 集計・作図 2026-10-15',
        'Foursquare由来：Apache-2.0 / 同梱NOTICE参照 | POI登録を分析（営業中店舗数・人出ではない）']
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">'
        '<style>text{font-family:"Yu Gothic","Meiryo",sans-serif;fill:#203b47}.muted{fill:#72838b}</style>'
        '<rect width="1600" height="900" fill="#f8fafb"/>'
        +text(60,80,title,52 if cover else 38,font_weight='bold')
        +text(1540,75,'masahiko.info',26,text_anchor='end',class_='muted')
        +text(60,126,subtitle,24)+body
        +''.join(text(60,813+i*29,line,18,class_='muted') for i,line in enumerate(footer))+'</svg>')


def save_similarity_figures(out):
    out=Path(out)
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    rankings={mode:pd.read_csv(out/f'ranking_{mode}.csv').dropna(subset=['rank']).sort_values('rank') for mode in NAMES}
    top=rankings['main'].head(10)
    profiles=pd.read_csv(out/'region_features.csv').set_index('region_id')
    stations=pd.read_csv(out/'stations.csv').set_index('region_id')
    stability=pd.read_csv(out/'stability.csv')
    files=[]
    def save(name,title,subtitle,body,cover=False):
        p=out/(name+'.svg');p.write_text(document(title,subtitle,body,manifest,cover=cover),encoding='utf8');files.append(p)
    body=''
    for i,r in enumerate(top.itertuples()):
        y=200+i*55
        body+=text(65,y,f'{i+1:02}',27)+text(130,y,r.station_name,29)
        body+=f'<rect x="360" y="{y-25}" width="{r.distance/1.2*930:.1f}" height="32" rx="4" fill="#327e8e"/>'
        body+=text(1410,y,f'{r.distance:.3f}',28,text_anchor='end')
    save('top10','吉祥寺に似た駅周辺 トップ10','3ブロックの距離：小さいほど近い / 吉祥寺と重なるAOIを除外 / 1km四方',body)
    ids=['n02-003584']+top.region_id.head(3).tolist()
    metrics=[('poi_density_per_km2','登録密度（件/km²）',1),('restaurant_share','食事（%）',100),
        ('cafe_share','カフェ（%）',100),('bar_share','バー（%）',100),('fashion_share','衣料（%）',100),
        ('beauty_share','美容等（%）',100),('food_store_share','食品小売（%）',100),('peak_to_mean_density_250m','集中度（倍）',1)]
    body=text(70,190,'特徴量',27)
    for j,ident in enumerate(ids):body+=text(565+j*270,190,stations.loc[ident,'station_name'],29,text_anchor='middle',font_weight='bold')
    for i,(col,label,mult) in enumerate(metrics):
        y=250+i*59
        body+=f'<rect x="55" y="{y-35}" width="1490" height="56" fill="'+('#e9f1f3' if i%2==0 else '#fff')+'"/>'
        body+=text(75,y,label,27)
        for j,ident in enumerate(ids):
            v=profiles.loc[ident,col]*mult
            body+=text(565+j*270,y,f'{v:,.0f}' if col=='poi_density_per_km2' else f'{v:.2f}',29,text_anchor='middle')
    save('profile_comparison','吉祥寺と上位3地域の数値プロフィール','構成比の分母は欠損を含む全登録数 / 集中度＝250m最大密度÷地域平均密度',body)
    # Geographic positions in metric coordinates, no basemap tiles or copied boundaries.
    xmin,xmax=stations.x.min()-3000,stations.x.max()+3000
    ymin,ymax=stations.y.min()-3000,stations.y.max()+3000
    scale=min(950/(xmax-xmin),580/(ymax-ymin))
    def xy(r):return 70+(r.x-xmin)*scale,740-(r.y-ymin)*scale
    body=text(70,178,'北 ↑   駅代表点の位置図（都境界は表示しない）',22)
    for r in stations.itertuples():
        x,y=xy(r);body+=f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.7" fill="#bbc7ce"/>'
    for i,r in enumerate(top.itertuples()):
        x,y=xy(stations.loc[r.region_id]);body+=f'<circle cx="{x:.2f}" cy="{y:.2f}" r="7" fill="#187f92"/>'
        # Fixed vertical callouts keep the three Tachikawa group labels distinct.
        label_y=220+i*49
        body+=f'<path d="M{x:.2f},{y:.2f} L1040,{label_y-8}" fill="none" stroke="#8eb3bd" stroke-width="1"/>'
        body+=text(1060,label_y,f'{i+1}. {r.station_name}',29)
    x,y=xy(stations.loc['n02-003584']);body+=f'<circle cx="{x}" cy="{y}" r="9" fill="#d45a30"/>'+text(x+12,y-12,'吉祥寺',27,fill='#d45a30')
    body+=f'<path d="M80,765 h{10000*scale:.1f}" stroke="#203b47" stroke-width="4"/>'+text(80,792,'10km',20)
    save('candidate_map','上位候補は東京都内のどこにあるか',f'灰色：対象{len(stations)}駅 / 青：主順位トップ10 / 橙：吉祥寺 / EPSG:6677、同じ縮尺',body)
    density=rankings['density_only'].head(10)
    body=text(65,185,'密度だけのトップ10',30,font_weight='bold')+text(850,185,'地域特徴量のトップ10',30,font_weight='bold')
    for i,(a,b) in enumerate(zip(density.itertuples(),top.itertuples())):
        y=240+i*49
        body+=text(70,y,f'{i+1}. {a.station_name}',28)+text(540,y,f'主順位 {int(a.main_rank)}位',23)
        dr=int(rankings['density_only'].set_index('region_id').loc[b.region_id,'rank'])
        body+=text(850,y,f'{i+1}. {b.station_name}',28)+text(1300,y,f'密度 {dr}位',23)
    save('rank_comparison','密度だけでは、同じ候補にならなかった',f'両方式のトップ10共通は{len(set(density.region_id) & set(top.region_id))}件 / 店の多さに、種類の構成と集まり方を加えた違い',body)
    body=''
    for i,r in enumerate(stability.itertuples()):
        y=230+i*100
        body+=text(65,y,NAMES[r.mode],28)
        body+=f'<rect x="420" y="{y-32}" width="950" height="45" fill="#e2e9ec"/>'
        body+=f'<rect x="420" y="{y-32}" width="{r.top10_overlap*95}" height="45" fill="#327e8e"/>'
        body+=text(1500,y,f'{r.top10_overlap}/10',30,text_anchor='end')
    save('stability','条件を変えると、上位候補はどれだけ残るか','主指標とのトップ10共通件数 / 同じ入力・候補・AOI重複除外で比較',body)
    body=''
    for i,r in enumerate(top.itertuples()):
        col=i//5;row=i%5;x=80+col*780;y=270+row*93
        body+=text(x,y,f'{i+1:02}',45,fill='#327e8e')+text(x+95,y,r.station_name,48,font_weight='bold')
    save('cover_1600x900','吉祥寺に似た街',f'東京都内{len(stations)}駅のPOI特徴を比較 / 駅周辺1km四方・トップ10',body,True)
    return files
