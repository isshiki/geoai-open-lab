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


def document(width,height,title,body,subtitle):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" style="max-width:100%;height:auto">'
        '<style>text{font-family:"Yu Gothic","Meiryo",sans-serif;fill:#263238} .sig{fill:#899395}</style>'
        '<rect width="100%" height="100%" fill="white"/>'
        +text(32,42,title,27)+text(width-28,40,'masahiko.info',19,text_anchor='end',class_='sig')
        +text(32,76,subtitle,17)+body
        +text(32,height-44,'出典: Overture Maps Foundation, overturemaps.org | release 2026-09-23.0 | 取得 2026-09-25',15)
        +text(32,height-20,'集計・作図: masahiko.info | POI登録数（営業中店舗数ではない）| 吉祥寺の実験用矩形のみ',15)+'</svg>')


def density_color(value, maximum):
    fraction=max(0,min(1,value/maximum)) if maximum else 0
    first=(240,249,245);last=(0,86,83)
    return '#'+''.join(f'{round(a+(b-a)*fraction):02x}' for a,b in zip(first,last))


def save_figures(runs,out):
    """Same color scale for both resolutions; full clipped geometry, no basemap."""
    out=Path(out)
    all_geoms=list(runs[250][0].geometry)
    xmin=min(g.bounds[0] for g in all_geoms);ymin=min(g.bounds[1] for g in all_geoms)
    xmax=max(g.bounds[2] for g in all_geoms);ymax=max(g.bounds[3] for g in all_geoms)
    maximum=max(c.density_per_km2.max() for c,t in runs.values())
    body=''
    for panel,size in enumerate([250,500]):
        cells=runs[size][0]
        left=65+panel*610; top=140
        scale=min(490/(xmax-xmin),490/(ymax-ymin))
        body+=text(left,115,f'{size}m格子 / {len(cells)}区画',23)
        for ix in sorted(cells.ix.unique()):
            subset=cells[cells.ix==ix]
            mid=sum(g.centroid.x for g in subset.geometry)/len(subset)
            body+=text(left+(mid-xmin)*scale,top-5,str(ix),13,text_anchor='middle')
        for iy in sorted(cells.iy.unique()):
            subset=cells[cells.iy==iy]
            mid=sum(g.centroid.y for g in subset.geometry)/len(subset)
            body+=text(left-8,top+(ymax-mid)*scale,str(iy),13,text_anchor='end')
        for r in cells.itertuples():
            parts=[r.geometry] if r.geometry.geom_type=='Polygon' else list(r.geometry.geoms)
            for poly in parts:
                pts=' '.join(f'{left+(x-xmin)*scale:.3f},{top+(ymax-y)*scale:.3f}' for x,y in poly.exterior.coords)
                body+=f'<polygon points="{pts}" fill="{density_color(r.density_per_km2,maximum)}" stroke="#738c85" stroke-width="1"/>'
            if r.area_m2>size*size*.20:
                c=r.geometry.representative_point()
                body+=text(left+(c.x-xmin)*scale,top+(ymax-c.y)*scale,
                           f'{r.poi_count}件',15,text_anchor='middle',style='paint-order:stroke;stroke:white;stroke-width:3px')
        body+=text(left,657,'西 ← 東方向（投影座標）→ 東',16)
        body+=text(left+510,132,'N ↑',19)
        bar=250*scale
        body+=f'<path d="M {left} 685 h {bar}" stroke="#263238" stroke-width="4"/>'
        body+=text(left+bar/2,711,'250 m',16,text_anchor='middle')
    for i in range(120):
        body+=f'<rect x="{400+i*3}" y="735" width="3.1" height="20" fill="{density_color(i/119*maximum,maximum)}"/>'
    body+=text(390,752,'0',16,text_anchor='end')+text(770,752,f'{maximum:,.0f} 件/km²',16)
    body+=text(32,793,'色＝AOI内の実面積当たり密度。端の格子も切り取られた面積で計算。',18)
    body+=text(32,821,'格子内の数字＝登録件数。背景地図なし。座標系 EPSG:6677・共通原点 (0, 0)。',17)
    path=out/'density_250_500.svg'
    path.write_text(document(1240,910,'POI登録密度：250mと500mで見え方を比べる',body,
        '同じ3,666件・同じAOI・同じ色尺度。500mは250m格子をまとめたもの。'),encoding='utf8')
    cells,tables=runs[250]
    ordered=cells.sort_values(['iy','ix'],ascending=[False,True])
    groups=list(COLORS)
    table=tables['display_group'].pivot(index='cell_id',columns='display_group',values='share').fillna(0)
    b=''
    for i,g in enumerate(groups):
        x=32+(i%4)*300;y=105+(i//4)*32
        b+=f'<rect x="{x}" y="{y-15}" width="17" height="17" fill="{COLORS[g]}"/>'+text(x+24,y,LABELS[g],17)
    b+=text(32,185,'北→南、同じ行は西→東。区画IDは投影格子の列・行番号。',17)
    for i,r in enumerate(ordered.itertuples()):
        y=220+i*34
        b+=text(30,y+17,f'({r.ix}, {r.iy})',16)+text(205,y+17,f'n={r.poi_count}',16,text_anchor='end')
        x=225
        if r.poi_count==0:
            b+=text(x,y+17,'0件：構成比は未定義',16)
        else:
            for g in groups:
                width=float(table.loc[r.cell_id].get(g,0))*800
                b+=f'<rect x="{x:.3f}" y="{y}" width="{width:.3f}" height="24" fill="{COLORS[g]}"/>'
                x+=width
        b+=text(1045,y+17,f'{r.area_m2:,.0f} m²',15)
    end=220+len(ordered)*34
    b+=text(225,end+24,'0%',16)+text(1025,end+24,'100%',16,text_anchor='end')
    b+=text(32,end+65,'分母＝各区画の全登録件数（欠損含む）。複数カテゴリの重複集計なし。',18)
    b+=text(32,end+93,'その他＝表示用6群に含めなかった既知分類。元のbasic_category別集計も保存。',17)
    p=out/'category_composition_250.svg'
    p.write_text(document(1240,end+190,'場所ごとのカテゴリ構成：250m格子',b,
        '構成比だけで規模を比べない：左側に各区画の登録件数、右側にAOI内面積を表示。'),encoding='utf8')
    return [path,p,save_profile_figure(out)]


def save_profile_figure(out):
    """Render the computed single-row CSV, with raw units and no normalization."""
    import csv
    out = Path(out)
    with (out/'region_features.csv').open(encoding='utf8', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 1:
        raise ValueError('Expected one region for this figure.')
    r = rows[0]
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
    p.write_text(document(1240,970,'街の数値プロフィール',body,r['region_label']),encoding='utf8')
    return p
