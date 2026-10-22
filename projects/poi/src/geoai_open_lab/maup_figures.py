"""Static MAUP figures: same density scale and all 15 category pairs."""
import json
import numpy as np
import pandas as pd
from .maup import OUT
from .region_figures import text
from .clustering_figures import document,rect
NAMES=['scale','zoning','statistics','cover_1600x900']
LABELS={'square250':'250m × 250m','square500':'500m × 500m','square1000':'1000m × 1000m','wide':'1000m × 250m','tall':'250m × 1000m'}
JP={'restaurant':'食事','cafe':'カフェ','bar':'バー','fashion':'衣料','beauty':'美容等','food_store':'食品小売'}

def figures():
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'));cells=pd.read_csv(OUT/'cells.csv');stats=pd.read_csv(OUT/'distribution.csv');cor=pd.read_csv(OUT/'correlations.csv')
    peak=cells.density_per_km2.max();paths=[]
    def color(v):
        f=np.log1p(v)/np.log1p(peak)
        return '#'+''.join(f'{round(a+(b-a)*f):02x}' for a,b in zip((239,246,252),(0,70,126)))
    def map_panel(scheme,x,y,size):
        t=cells[cells.scheme==scheme];body=''
        for r in t.itertuples():
            px=x+(r.west-m['bounds'][0])/4000*size;py=y+size-(r.south-m['bounds'][1]+r.height_m)/4000*size
            body+=rect(px,py,r.width_m/4000*size,r.height_m/4000*size,color(r.density_per_km2))
            body+=f'<rect x="{px}" y="{py}" width="{r.width_m/4000*size}" height="{r.height_m/4000*size}" fill="none" stroke="white" stroke-width=".6"/>'
        body+=f'<circle cx="{x+size/2}" cy="{y+size/2}" r="5" fill="#e69f00" stroke="#203b47"/>'
        return body
    def save(name,title,subtitle,body):
        p=OUT/(name+'.svg');p.write_text(document(title,subtitle,body,m).replace('2026-10-16','2026-10-22'),encoding='utf8');paths.append(p)
    def maps(name,schemes,title):
        body=''
        for i,scheme in enumerate(schemes):
            x=70+510*i;t=cells[cells.scheme==scheme]
            body+=text(x,185,LABELS[scheme],28,font_weight='bold')+text(x,224,f'{len(t)}区画 / 1区画 {t.area_km2.iloc[0]:.4g}km²',24)
            body+=map_panel(scheme,x,260,420)+text(x,715,'北 ↑　中央の点＝吉祥寺駅',21)
        for i in range(100):body+=rect(70+i*3.4,750,3.5,20,color(np.expm1(i/99*np.log1p(peak))))
        body+=text(430,768,f'登録密度：0〜{peak:,.0f}件/km²（全図共通・log1p色目盛）',23)
        save(name,title,f'同じ4km四方・同じ{m["poi_count"]:,}件。外枠16km²を隙間なく分割。',body)
    maps('scale',['square250','square500','square1000'],'区画を大きくすると、密度の見え方は？')
    maps('zoning',['square500','wide','tall'],'面積は同じ、形と向きだけを変える')
    body=text(60,177,'6カテゴリ件数のSpearman相関：全15組',27,font_weight='bold')
    schemes=list(LABELS)
    for j,s in enumerate(schemes):body+=text(285+j*125,215,{'square250':'250m','square500':'500m','square1000':'1km','wide':'横長','tall':'縦長'}[s],22,text_anchor='middle')
    for i,(a,b) in enumerate(cor[['first','second']].drop_duplicates().itertuples(index=False,name=None)):
        y=250+i*31;body+=text(60,y,JP[a]+'×'+JP[b],19)
        for j,s in enumerate(schemes):
            rho=cor[(cor.scheme==s)&(cor['first']==a)&(cor.second==b)].rho.iloc[0]
            fill='#dddddd' if not np.isfinite(rho) else ('#'+''.join(f'{round(255+(v-255)*abs(rho)):02x}' for v in ((112,55,160) if rho>=0 else (213,94,0))))
            body+=rect(235+j*125,y-23,104,28,fill)+text(287+j*125,y-3,'NA' if not np.isfinite(rho) else f'{rho:.2f}',18,text_anchor='middle',style='fill:'+('white' if abs(rho)>.65 else '#203b47'))
    body+=text(935,190,'密度の分布（件/km²）',27,font_weight='bold')
    body+=text(935,235,'方式　　　 中央値 / P90 / 最大',22)
    for i,s in enumerate(schemes):
        r=stats[(stats.scheme==s)&(stats.metric=='density_per_km2')].iloc[0]
        body+=text(935,285+i*65,LABELS[s],23)+text(935,313+i*65,f'{r["median"]:,.0f} / {r.p90:,.0f} / {r.maximum:,.0f}',23)
    body+=text(60,755,'相関：紫＝正、橙＝負、白＝0（−1〜1）。区画内の件数の関係で、需要や因果ではない。',23)
    save('statistics','集計単位を変えたときの違いを、全組で確認','P90＝区画の90%がこの値以下。構成比の分布・欠損もCSVへ保存。',body)
    body=''
    for i,s in enumerate(['square250','square500','wide']):
        x=70+i*500;body+=map_panel(s,x,205,350)+text(x,595,LABELS[s],30)
    body+=text(60,670,f'入力 {m["poi_count"]:,}件と総面積16km²は同じ。変わるのは集計する区切り。',30)
    body+=text(60,735,'スケール効果とゾーニング効果を分けて確認。どの区切りも「正解」とはしない。',26)
    save('cover_1600x900','地図の区切りで答えが変わる？','PythonでMAUPを確かめる｜青の濃さ＝登録密度（全図共通）',body)
    return paths

if __name__=='__main__':figures()
