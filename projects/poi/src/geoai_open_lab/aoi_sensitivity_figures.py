"""AOI sensitivity figures derived only from saved audited results."""
import json
import numpy as np
import pandas as pd
from .aoi_sensitivity import OUT
from .region_figures import text
from .clustering_figures import document,rect,line

COLORS={500:'#0072b2',600:'#56b4e9',700:'#d55e00',800:'#c43939'}
NAMES=('aoi_sizes','target_rankings','common_distribution','station_sensitivity','cluster_changes','cover_1600x900')

def figures(out=OUT):
    # Optional A-quality-check directory; original audit figures stay untouched.
    OUT = out
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    ranks=pd.read_csv(OUT/'rankings.csv');stats=pd.read_csv(OUT/'station_stability.csv')
    metrics=pd.read_csv(OUT/'cluster_metrics.csv');summary=pd.read_csv(OUT/'summary.csv')
    paths=[]
    def save(name,title,subtitle,body):
        footer='半幅の色：500m 青 / 600m 水色 / 700m オレンジ / 800m 赤'
        if 'a_peak_rule' in m: footer+='　Aの集中度：完全250m区画のみ'
        body+=text(60,785,footer,21)
        p=OUT/(name+'.svg')
        svg=document(title,subtitle,body,m).replace('2026-10-16','2026-10-17')
        svg=svg.replace('取得 2026-10-17','取得 2026-10-15 / 不足分追加 2026-10-17')
        p.write_text(svg,encoding='utf8');paths.append(p)
    body=''
    for h in (800,700,600,500):
        side=h*.65;x=390-side/2;y=445-side/2
        body+=f'<rect x="{x}" y="{y}" width="{side}" height="{side}" fill="none" stroke="{COLORS[h]}" stroke-width="5"/>'
    body+='<circle cx="390" cy="445" r="8" fill="#203b47"/>'+text(410,453,'駅',25)+text(390,170,'北 ↑',23,text_anchor='middle')
    for i,h in enumerate((500,600,700,800)):
        y=260+i*105;body+=rect(800,y-26,22,22,COLORS[h])+text(845,y,f'半幅 {h}m  →  一辺 {2*h/1000:.1f}km',31)
        body+=text(845,y+40,f'面積 {(2*h/1000)**2:.2f}km²',26)
    body+=text(65,735,'同じ駅代表点・EPSG:6677。円や徒歩の駅勢圏ではありません。',26)
    save('aoi_sizes','駅のまわりを、どこまで集計する？','正方形は共通。駅から東西南北へ広げる距離だけを変更。',body)
    body=''
    for j,mode in enumerate('ABC'):
        x=55+j*515;a=ranks[(ranks['mode']==mode)&(ranks.half_width_m==500)].head(10);b=ranks[(ranks['mode']==mode)&(ranks.half_width_m==800)].head(10)
        common=set(a.region_id)&set(b.region_id)
        body+=text(x,175,mode+'：共通 '+str(len(common))+'/10駅',28,font_weight='bold')
        body+=text(x,216,'500m',25,style='fill:'+COLORS[500])+text(x+245,216,'800m',25,style='fill:'+COLORS[800])
        for t,offset in [(a,0),(b,245)]:
            for i,r in enumerate(t.itertuples()):
                y=258+i*43;status='共' if r.region_id in common else ('外' if offset==0 else '新')
                color='#e2e8ec' if status=='共' else ('#edf5fa' if status=='外' else '#fbe8e5')
                label=r.station_name if r.station_name!='池袋' else f'池袋({r.region_id[-6:]})'
                body+=rect(x+offset,y-27,238,37,color)+text(x+offset+6,y,f'{i+1} {label}',20)+text(x+offset+222,y,status,17,text_anchor='end')
    body+=text(60,720,'共＝両方の上位10駅 / 新＝800mで上位入り / 外＝800mでは上位10圏外',24)
    body+=text(60,753,'A：8特徴 / B：カテゴリTF-IDF / C：64次元Embedding。候補は全範囲で共通。',23)
    save('target_rankings','吉祥寺に似ている駅：500m と 800m','同名駅は固定の駅グループとして別集計。全順位・IDは付属CSVで確認。',body)
    body=''
    for j,mode in enumerate('ABC'):
        x=65+j*515;body+=text(x,190,mode+'：上位10駅の共通数',27,font_weight='bold')
        for k,h in enumerate((600,700,800)):
            t=stats[(stats['mode']==mode)&(stats.half_width_m==h)]
            hist=np.bincount(t.common_top10,minlength=11)
            for n,value in enumerate(hist):
                xx=x+40+n*37+k*10;hh=value/250*310
                body+=rect(xx,590-hh,10,hh,COLORS[h])
            body+=text(x,665+k*31,f'{h}m：平均 {t.common_top10.mean():.2f} / 中央値 {t.common_top10.median():.0f}',23,style='fill:'+COLORS[h])
        for n in range(11):body+=text(x+40+n*37+10,620,str(n),20,text_anchor='middle')
        for v in (0,50,100,150,200,250):
            yy=590-v/250*310;body+=line(x+40,yy,x+445,yy)+text(x+30,yy+5,str(v),16,text_anchor='end')
    save('common_distribution','全656駅：似ている上位駅は何駅残る？','500mとの共通数（0〜10駅）。各色の件数合計は656駅。横軸＝共通数、縦軸＝駅数。',body)
    t=stats[(stats['mode']=='C')&(stats.half_width_m==800)]
    body=text(60,185,'C：500m時点のPOI数と共通数',28,font_weight='bold')
    xmax=np.log1p(t.baseline_poi_count.max())
    for r in t.itertuples():
        x=90+np.log1p(r.baseline_poi_count)/xmax*720;y=650-r.common_top10*40
        body+=f'<circle cx="{x}" cy="{y}" r="3.2" fill="{COLORS[800]}" opacity=".35"/>'
    for n in (0,2,4,6,8,10):body+=text(65,657-n*40,str(n),20)+line(90,650-n*40,810,650-n*40)
    for n in (10,100,1000,10000):
        x=90+np.log1p(n)/xmax*720
        if x<=810:body+=text(x,687,str(n),20,text_anchor='middle')
    body+=text(160,727,'POI登録数（log1p目盛）',25)
    low=t.sort_values(['common_top10','spearman','region_id']).head(3)
    high=t.sort_values(['common_top10','spearman','region_id'],ascending=[False,False,True]).head(3)
    for offset,items,title in [(0,low,'変化が大きい例'),(270,high,'上位駅が比較的残った例')]:
        body+=text(900,220+offset,title,28,font_weight='bold')
        for i,r in enumerate(items.itertuples()):body+=text(900,275+offset+i*55,f'{r.station_name}：{r.common_top10}/10駅',27)
    save('station_sensitivity','駅によって、範囲変更への反応が異なる','Cの800mを500mと比較。例は共通数→全順位相関→IDの事前規則で選択。',body)
    assigned=pd.read_csv(OUT/'assignments.csv');t=assigned[(assigned['mode']=='C')&(assigned.half_width_m==800)]
    cross=pd.crosstab(t.baseline_cluster,t.cluster).reindex(index=[1,2,3],columns=[1,2,3],fill_value=0)
    cm=metrics[(metrics['mode']=='C')&(metrics.half_width_m==800)].iloc[0]
    body=text(65,195,'行：500mの群 / 列：800mの対応後の群',27)
    for j in range(3):body+=text(335+j*230,250,f'群{j+1}',28,style='fill:'+COLORS[800])
    for i in range(3):
        body+=text(90,345+i*135,f'群{i+1}',28,style='fill:'+COLORS[500])
        for j in range(3):body+=rect(240+j*230,280+i*135,215,120,'#e6eef2' if i==j else '#f8e9e6')+text(345+j*230,352+i*135,str(cross.iloc[i,j]),40,text_anchor='middle')
    body+=text(1030,340,f'ARI {cm.ari:.3f}',42,font_weight='bold')+text(1030,420,f'所属変更 {cm.changed}駅',32)
    body+=text(1030,490,'吉祥寺：群3 → 群3',27)+text(65,735,'群番号を最大一致で対応付け。ARIは分類の一致度で、正解率ではありません。',25)
    save('cluster_changes','Cの3群分類：500m → 800m','上位10の順位変化と、全体を3群にまとめたときの変化は別の尺度です。',body)
    body=''
    for h,x in [(500,90),(800,385)]:
        side=h*.27;body+=f'<rect x="{x}" y="230" width="{side}" height="{side}" fill="none" stroke="{COLORS[h]}" stroke-width="7"/>'
        body+=text(x,500,f'{h}m',42,style='fill:'+COLORS[h])
    body+=text(265,320,'→',50)+text(750,245,'吉祥寺のC・1位',30)+text(750,305,'町田 → 都電雑司ヶ谷',42,font_weight='bold')
    body+=text(750,375,'町田は800mでも2位',28)
    means=summary[summary.half_width_m==800].set_index('mode').common_mean
    body+=text(60,590,'全駅平均：上位10駅の共通数',32)
    body+=text(60,650,f'A {means.A:.2f}駅 / B {means.B:.2f}駅 / C {means.C:.2f}駅',42,font_weight='bold')
    body+=text(950,590,f'Cの分類 ARI {cm.ari:.3f}',34)+text(60,725,'Embeddingだけでなく、対象範囲を変えると3方式とも結果が変わった。',29)
    save('cover_1600x900','街をどこまで数える？ 500m → 800m','東京都内656駅。最適な商圏を決める実験ではなく、分析条件への感度を確認。',body)
    return paths

if __name__=='__main__': figures()
