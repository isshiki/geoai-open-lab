"""Six static, source-backed clustering figures; no external map tiles."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from .region_figures import text
from .similar_regions import FEATURES

COLORS = ['#0072b2','#d55e00','#009e73','#cc79a7','#8a7300','#5649a0','#568a9b','#b54d60']
JP = ['登録密度','食事','カフェ','バー','衣料','美容等','食品小売','集中度']


def rect(x,y,w,h,fill):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{fill}"/>'


def line(x1,y1,x2,y2):
    return f'<path d="M{x1},{y1} L{x2},{y2}" stroke="#bdc8d0" fill="none"/>'


def document(title, subtitle, body, m):
    footer=[f"出典：Overture Maps Foundation {m['release']} | 取得 {m['acquisition_utc'][:10]}",
        '駅：国土交通省 国土数値情報 N02-25（CC BY 4.0）を加工 | 集計・作図 2026-10-16',
        'Foursquare由来：Apache-2.0 / 同梱NOTICE参照 | POI登録の分類（住みやすさ・街の優劣ではない）']
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900">'
        '<style>text{font-family:"Yu Gothic","Meiryo",sans-serif;fill:#203b47}</style>'
        +rect(0,0,1600,900,'#f8fafb')+text(60,75,title,38,font_weight='bold')
        +text(1540,72,'masahiko.info',26,text_anchor='end')+text(60,120,subtitle,23)+body
        +''.join(text(60,813+i*29,t,18) for i,t in enumerate(footer))+'</svg>')


def save_clustering_figures(out, names):
    out=Path(out)
    m=json.loads((out/'manifest.json').read_text(encoding='utf8'))
    a=pd.read_csv(out/'assignments.csv'); s=pd.read_csv(out/'cluster_summary.csv')
    f=pd.read_csv(out/'cluster_features.csv'); metrics=pd.read_csv(out/'k_metrics.csv')
    paths=[]
    def save(name,title,subtitle,body):
        p=out/(name+'.svg'); p.write_text(document(title,subtitle,body,m),encoding='utf8');paths.append(p)
    def legend(x=1120,y=200):
        return ''.join(rect(x,y+i*65-18,20,20,COLORS[i])+text(x+32,y+i*65,f'C{i+1} {names[str(i+1)]}',21)
                       for i in range(m['main_k']))
    # Diverging heatmap: exact transformed mean differences, fixed +/-2 color scale.
    body=''
    for j,label in enumerate(JP): body+=text(460+j*132,205,label,23,text_anchor='middle')
    for row in s.itertuples():
        y=245+(row.cluster-1)*83
        body+=text(60,y+40,f'C{row.cluster} {names[str(row.cluster)]}',22)
        for j,feature in enumerate(FEATURES):
            v=float(f.loc[(f.cluster==row.cluster)&(f.feature==feature),'transformed_mean_difference'].iloc[0])
            t=min(abs(v)/2,1); target=np.array([26,115,155] if v<0 else [208,97,58]); color=np.round(255*(1-t)+target*t).astype(int)
            body+=rect(400+j*132,y,126,70,'#'+''.join(f'{c:02x}' for c in color))
            body+=text(460+j*132,y+43,f'{v:+.2f}',23,text_anchor='middle',style='fill:'+('white' if t>.65 else '#203b47'))
    body+=text(60,745,'青：全駅平均より低い　白：0　赤：高い（色の範囲 −2〜+2、数値は切り詰めない）',23)
    save('heatmap','クラスタの特徴差','変換・重み付け後の群平均 − 全656駅平均。生の割合ではありません。',body)
    # Projected point map with equal aspect ratio.
    xmin,xmax=a.x.min(),a.x.max(); ymin,ymax=a.y.min(),a.y.max()
    scale=min(950/(xmax-xmin),540/(ymax-ymin))
    def mapxy(r): return 90+(r.x-xmin)*scale,720-(r.y-ymin)*scale
    body=legend()
    for r in a.itertuples():
        x,y=mapxy(r);body+=f'<circle cx="{x}" cy="{y}" r="5" fill="{COLORS[r.cluster-1]}" fill-opacity=".7"/>'
    body+=text(80,185,'N ↑',24)+line(100,760,100+10000*scale,760)+text(100,787,'10 km',20)
    save('station_map','656駅の分類を地図で見る','EPSG:6677の駅代表点。点の重なりあり。行政界・商圏を示す地図ではありません。',body)
    # PCA, equal units in both directions, annotate true explained variance.
    xr=a.pc1.max()-a.pc1.min(); yr=a.pc2.max()-a.pc2.min(); scale=min(920/xr,500/yr)
    ox=100-a.pc1.min()*scale; oy=710+a.pc2.min()*scale
    body=legend()+line(100,710,1040,710)+line(100,180,100,710)
    for r in a.itertuples(): body+=f'<circle cx="{ox+r.pc1*scale}" cy="{oy-r.pc2*scale}" r="4" fill="{COLORS[r.cluster-1]}" fill-opacity=".6"/>'
    for val in np.linspace(a.pc1.min(),a.pc1.max(),5): body+=text(ox+val*scale,740,f'{val:.1f}',18,text_anchor='middle')
    for val in np.linspace(a.pc2.min(),a.pc2.max(),5): body+=text(88,oy-val*scale+6,f'{val:.1f}',18,text_anchor='end')
    ratios=m['pca_explained_ratio']
    body+=text(560,780,f'PC1（{ratios[0]:.1%}）',23,text_anchor='middle')+text(100,165,f'PC2（{ratios[1]:.1%}）',23)
    save('pca','PCAで8次元の分類を眺める',f'表示専用・2軸の累積寄与率 {sum(ratios):.1%}。分類は元の8次元で計算。',body)
    body=''
    for r in s.itertuples():
        y=205+(r.cluster-1)*83
        body+=text(60,y+35,f'C{r.cluster} {names[str(r.cluster)]}',24)
        body+=rect(430,y,900*r.count/s['count'].max(),54,COLORS[r.cluster-1])+text(450+900*r.count/s['count'].max(),y+36,f'{r.count}駅',26)
    body+=text(430,760,'0を起点とする駅グループ数。合計656（重複AOIを含む）。',23)
    save('cluster_sizes','クラスタごとの駅数','表示順は密度中央値の昇順。番号は優劣を表しません。',body)
    body=''
    fields=[('silhouette','Silhouette ↑'),('calinski_harabasz','Calinski–Harabasz ↑'),('davies_bouldin','Davies–Bouldin ↓')]
    for j,(col,label) in enumerate(fields):
        left=90+j*510; low=metrics[col].min(); high=metrics[col].max(); span=high-low or 1
        body+=text(left,210,label,25)+line(left,650,left+400,650)
        points=[]
        for r in metrics.itertuples():
            x=left+(r.k-3)*76; val=getattr(r,col); y=600-(val-low)/span*300
            points.append(f'{x},{y}'); body+=f'<circle cx="{x}" cy="{y}" r="7" fill="#0072b2"/>'
            body+=text(x,y-18,f'{val:.3f}' if col!='calinski_harabasz' else f'{val:.1f}',18,text_anchor='middle')+text(x,685,str(r.k),23,text_anchor='middle')
        body+=f'<polyline points="{" ".join(points)}" fill="none" stroke="#0072b2"/>'+text(left,735,'クラスタ数 k',23)
    save('k_comparison','クラスタ数を変えて比較する',f'指標ごとに独立した縦尺度・点の数値を併記。主結果は k={m["main_k"]}。',body)
    body=text(70,205,f'東京都内656駅周辺 × {m["main_k"]}つのまとまり',44,font_weight='bold')
    for r in s.itertuples():
        y=290+(r.cluster-1)*130
        body+=rect(70,y,14,75,COLORS[r.cluster-1])+text(110,y+48,f'C{r.cluster}  {names[str(r.cluster)]}',40)
        body+=text(850,y+48,f'{r.count}駅',42)+text(1080,y+48,r.representatives.split(' / ')[0],42)
    body+=text(70,760,'POIの構成を分類。街の優劣や住みやすさではありません。',26)
    save('cover_1600x900','POIデータで街をクラスタリング','Pythonで東京都内656駅周辺を分類してみた',body)
    return paths
