"""Offline SVG figures with true projected geometries; no tiles or fonts fetched."""
from html import escape
from pathlib import Path

COLORS={'restaurant':'#bc5929','cafe':'#d9a441','bar':'#86639b',
        'fashion':'#3d79a1','beauty':'#49a18e','food_store':'#75894b',
        '__OTHER__':'#b2b6bc','__MISSING__':'#424952'}
LABELS={'restaurant':'食事（2分類）','cafe':'カフェ（2分類）','bar':'バー',
        'fashion':'衣料','beauty':'美容等','food_store':'食品小売',
        '__OTHER__':'その他の分類','__MISSING__':'カテゴリ欠損'}


def text(x,y,value,size=18,**attrs):
    extra=' '.join(f'{k.rstrip("_").replace("_","-")}="{escape(str(v))}"' for k,v in attrs.items())
    return f'<text x="{x}" y="{y}" font-size="{size}" {extra}>{escape(str(value))}</text>'


def document(width,height,title,body,subtitle,manifest):
    date=manifest['acquisition_utc'][:10]
    release=manifest['config']['release']
    footer=[f'出典: Overture Maps Foundation | release {release} | 取得 {date}',
        '駅: 国土交通省 国土数値情報 N02-25（CC BY 4.0）を加工 | 加工日 2026-10-14',
        'Foursquare由来: Apache-2.0 / NOTICEは同梱資料参照 | 本集計の変更日 2026-10-14',
        '集計・作図: masahiko.info | POI登録数（営業中店舗数ではない）']
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%;height:auto">'
        '<style>text{font-family:"Yu Gothic","Meiryo",sans-serif;fill:#263238}.sig{fill:#899395}</style>'
        '<rect width="100%" height="100%" fill="white"/>'
        +text(32,42,title,27)+text(width-28,40,'masahiko.info',19,text_anchor='end',class_='sig')
        +text(32,76,subtitle,17)+body
        +''.join(text(32,height-92+i*23,line,14) for i,line in enumerate(footer))+'</svg>')


def density_color(value, maximum):
    fraction=max(0,min(1,value/maximum)) if maximum else 0
    first=(240,249,245);last=(0,86,83)
    return '#'+''.join(f'{round(a+(b-a)*fraction):02x}' for a,b in zip(first,last))


def save_figures(runs,out):
    """Station-centered metric maps; common density scale, geographic directions."""
    import json
    out=Path(out)
    m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    c=m['station'];xmin=c['x']-500;ymax=c['y']+500
    maximum=max(cells.density_per_km2.max() for cells,t in runs.values())
    body=''
    for panel,size in enumerate([250,500]):
        cells=runs[size][0];left=85+panel*610;top=155;scale=.45
        body+=text(left,115,f'{size}m格子 / {len(cells)}区画',23)
        for row in cells.itertuples():
            pts=' '.join(f'{left+(x-xmin)*scale:.3f},{top+(ymax-y)*scale:.3f}' for x,y in row.geometry.exterior.coords)
            body+=f'<polygon points="{pts}" fill="{density_color(row.density_per_km2,maximum)}" stroke="#738c85" stroke-width="1.5"/>'
            point=row.geometry.centroid
            body+=text(left+(point.x-xmin)*scale,top+(ymax-point.y)*scale,f'{row.poi_count}件',18,text_anchor='middle',style='paint-order:stroke;stroke:white;stroke-width:3px')
        cx=left+225;cy=top+225
        body+=f'<circle cx="{cx}" cy="{cy}" r="7" fill="#b81932" stroke="white" stroke-width="2"/>'
        body+=text(cx+12,cy-14,'吉祥寺駅',17,style='paint-order:stroke;stroke:white;stroke-width:4px')
        for x,y,label in [(cx,top-12,'北 ↑'),(cx,top+480,'南'),(left-24,cy,'西'),(left+474,cy,'東')]:
            body+=text(x,y,label,18,text_anchor='middle')
        body+=f'<path d="M {left} 665 h 112.5" stroke="#263238" stroke-width="4"/>'
        body+=text(left+56,691,'250 m',17,text_anchor='middle')
        body+=text(left+300,688,'全体：1,000m × 1,000m',18,text_anchor='middle')
    for i in range(120):body+=f'<rect x="{400+i*3}" y="730" width="3.1" height="22" fill="{density_color(i/119*maximum,maximum)}"/>'
    body+=text(385,749,'0',17,text_anchor='end')+text(775,749,f'{maximum:,.0f} 件/km²',18)
    body+=text(32,798,'色＝登録密度、数字＝登録件数。赤点＝公式駅線から算出した代表点（出入口ではない）。',17)
    body+=text(32,829,'投影座標 EPSG:6677 の北を上に表示。格子は駅中心から±500m、部分区画なし。',17)
    p=out/'density_250_500.svg'
    p.write_text(document(1240,970,'1km四方の登録密度：駅を中心に同じ面積で集計',body,
        f"吉祥寺駅周辺1km四方 | {m['region_profile'][0]['poi_count']:,}件 | 両図は共通色尺度",m),encoding='utf8')
    # Intermediate category diagram is retained, with positions instead of grid IDs.
    cells,tables=runs[250];table=tables['display_group'].pivot(index='cell_id',columns='display_group',values='share').fillna(0)
    b=''
    for i,g in enumerate(COLORS):
        x=32+(i%4)*300;y=108+(i//4)*32
        b+=f'<rect x="{x}" y="{y-15}" width="17" height="17" fill="{COLORS[g]}"/>'+text(x+24,y,LABELS[g],17)
    for i,r in enumerate(cells.sort_values(['iy','ix'],ascending=[False,True]).itertuples()):
        y=190+i*38;x=360
        b+=text(32,y+20,f'北から{4-r.iy}段・西から{r.ix+1}列 / {r.poi_count}件',17)
        for g in COLORS:
            width=float(table.loc[r.cell_id].get(g,0))*800
            b+=f'<rect x="{x:.3f}" y="{y}" width="{width:.3f}" height="25" fill="{COLORS[g]}"/>';x+=width
    b+=text(32,835,'分母＝各区画の全登録件数（欠損含む）。各区画は62,500m²。',18)
    q=out/'category_composition_250.svg'
    q.write_text(document(1240,990,'算出根拠：250m格子のカテゴリ構成',b,'地域プロフィールを作るための途中集計（16区画）',m),encoding='utf8')
    return [p,q,save_profile_figure(out)]


def save_profile_figure(out):
    """Render the computed single-row CSV, with raw units and no normalization."""
    import csv
    import json
    out = Path(out)
    with (out/'region_features.csv').open(encoding='utf8', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError('Expected one region for this figure.')
    r = rows[0]
    manifest=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    metrics = [
        ('対象面積', f'{float(r["area_km2"]):.6f} km²'),
        ('POI登録数', f'{int(r["poi_count"]):,} 件'),
        ('地域全体の平均登録密度', f'{float(r["poi_density_per_km2"]):,.2f} 件/km²'),
        ('250m格子の最大密度', f'{float(r["peak_density_250m"]):,.2f} 件/km²'),
        ('集中度（最大密度 ÷ 地域平均）', f'{float(r["peak_to_mean_density_250m"]):.4f} 倍'),
    ]
    body = text(32,116,'1地域＝1行。ここでは、その列を読みやすく縦に並べています。',19)
    for i,(label,value) in enumerate(metrics):
        y=160+i*42
        body += text(40,y,label,20)+text(1140,y,value,23,text_anchor='end')
    body += text(40,390,'カテゴリ構成比（分母＝全登録件数、欠損を含む）',21)
    fields=['restaurant_share','cafe_share','bar_share','fashion_share','beauty_share',
            'food_store_share','other_share','category_missing_share']
    for i,(group,field) in enumerate(zip(COLORS,fields)):
        y=430+i*42;share=float(r[field])
        body += text(40,y+20,LABELS[group],19)
        body += f'<rect x="285" y="{y}" width="{share*700:.3f}" height="25" fill="{COLORS[group]}"/>'
        body += text(1140,y+20,f'{share*100:.2f}%',21,text_anchor='end')
    body += text(40,805,'横棒は0〜100%の共通尺度。表示群の定義は設定ファイルが正本。',17)
    body += text(40,838,'比較の候補：密度・構成比・集中度。類似度に使う列や重みはまだ決めていません。',17)
    body += text(40,871,'面積・件数・欠損率は監査にも使用。今回の1地域だけでは街同士の比較はできません。',17)
    p=out/'region_profile.svg'
    p.write_text(document(1240,1040,'街の数値プロフィール',body,r['region_label']+' | 駅代表点を中心に東西南北各500m',manifest),encoding='utf8')
    return p
