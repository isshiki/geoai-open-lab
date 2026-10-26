"""Data-backed SVGs in the existing GeoAI article design; no analysis writes."""
import json
from html import escape
import numpy as np
import pandas as pd
from .urban_function import OUT
from .crs_figures import text,box

COLORS={'commercial':'#c16b00','green':'#0072b2','residential':'#999999'}
LABELS={'commercial':'商業・サービス（6群）','green':'緑地・レクリエーション','residential':'住宅：入力不足・未推定'}


def save(name,title,sub,body):
    svg='<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="900" viewBox="0 0 1600 900"><style>text{font-family:"Yu Gothic",Meiryo,sans-serif;fill:#203b47}</style>'
    svg+=box(0,0,1600,900,'white')+text(45,62,title,34)+text(1540,62,'masahiko.info',23,'end')+text(45,111,sub,24)
    svg+=body+text(45,836,'Overture 2026-09-23.0（取得2026-10-15）／N02-25加工。加工日2026-10-26。',19)
    svg+=text(45,870,'POIから推定した機能的影響。土地利用・需要・売上・実際の街の境界ではありません。',21)+'</svg>'
    (OUT/(name+'.svg')).write_text(svg,encoding='utf8')


def mix(a,b,t):
    x=np.array([int(a[i:i+2],16) for i in (1,3,5)]);y=np.array([int(b[i:i+2],16) for i in (1,3,5)])
    return '#'+''.join(f'{int(round(v)):02x}' for v in x*(1-t)+y*t)


def panel(t,left,top,size,values,color):
    n=int(np.sqrt(len(t)));body='';step=size/n
    for i,v in enumerate(values):
        fill='#dddddd' if not np.isfinite(v) else color(float(v))
        body+=f'<rect x="{left+(i%n)*step:.2f}" y="{top+(n-1-i//n)*step:.2f}" width="{step+.1:.2f}" height="{step+.1:.2f}" fill="{fill}"/>'
    body+=f'<rect x="{left}" y="{top}" width="{size}" height="{size}" fill="none" stroke="#203b47"/>'
    body+=text(left+size-12,top-12,'N ↑',21,'end')
    body+=text(left,top+size+33,'← 西　　4km　　東 →',21)
    cx,cy=left+size/2,top+size/2
    body+=f'<path d="M{cx-7},{cy}h14 M{cx},{cy-7}v14" stroke="white" stroke-width="4"/><path d="M{cx-7},{cy}h14 M{cx},{cy-7}v14" stroke="black" stroke-width="2"/>'
    return body


def render():
    m=json.loads((OUT/'manifest.json').read_text(encoding='utf8'))
    tables={name:pd.read_csv(OUT/f'{name}_100.csv') for name in ('fixed_cells','common_gaussian','adaptive')}
    labels=['区画内の固定集計',f'共通半径 h={m["common_h_m"]:.1f}m','適応半径（S=1）']
    body=''
    for i,(model,t) in enumerate(tables.items()):
        x=45+i*520
        body+=text(x,179,labels[i],27)+panel(t,x,225,460,t.mu_green,lambda v:mix(COLORS['commercial'],COLORS['green'],v))
    for i in range(100):body+=f'<rect x="{250+i*8}" y="758" width="8" height="22" fill="{mix(COLORS["commercial"],COLORS["green"],i/99)}"/>'
    body+=text(45,780,'商業 100%',23)+text(1070,780,'緑地等 100%／灰：未定義',23)
    save('membership','半径で、機能的影響の見え方が変わる','100m格子中心。住宅は未推定。2機能だけで正規化した混色図。＋ 吉祥寺駅',body)
    a=tables['adaptive'];body=''
    for i,g in enumerate(('commercial','green')):
        x=45+i*520;z=a['z_'+g];mx=float(z.max())
        body+=text(x,179,LABELS[g],26)+panel(a,x,225,460,np.log1p(z)/np.log1p(mx),lambda v:mix('#ffffff',COLORS[g],v))
        body+=text(x,765,f'強度0～{mx:.2f}（log1p色尺度）',23)
    body+=box(1085,225,460,460)+text(1110,315,'住宅は未推定',32)+text(1110,380,'apartment：1件',27)+text(1110,430,'k=5の近傍を定義できない',24)+text(1110,490,'灰色＝住宅がない、ではない',23)
    save('intensity','機能ごとの強度を分けて見る','適応ガウス／半径の大きいPOIほど影響の総量も増えるモデル。色尺度は機能別。',body)
    body=text(50,177,'最大帰属度の機能',28)+panel(a,50,220,510,a.mu_green,lambda v:COLORS['green'] if v>.5 else COLORS['commercial'])
    body+=text(650,177,'混合度（2機能の正規化エントロピー）',28)+panel(a,650,220,510,a.entropy,lambda v:mix('#ffffff','#75507b',v))
    body+=text(1210,300,'0：片方が優勢',23)+text(1210,350,'1：同じ帰属度',23)+text(1210,430,'S2の遷移帯判定',23)+text(1210,470,'とは異なる',23)
    save('dominant_mixing','支配的機能と、モデル上の混ざり方','橙＝商業6群、青＝緑地等。番号や色は優劣を表さない。住宅は未推定。',body)
    d=a.mu_green-tables['common_gaussian'].mu_green
    body=panel(a,80,215,540,d,lambda v:mix('#ffffff','#0072b2' if v>=0 else '#c16b00',abs(v)))
    body+=text(720,260,'適応 − 共通半径：緑地等の帰属度',30)
    for y,s in [(340,'青：増加／橙：減少／白：差なし'),(400,'色の強さ：絶対差 0～1'),(480,'まばらなカテゴリはKNN距離が長くなる'),(540,'広い半径と機能別正規化が結果へ影響'),(620,'住宅不足を補った推定ではない')]:body+=text(720,y,s,25)
    save('difference','適応半径は、精度向上を保証しない','同じ入力・同じ100m格子。モデル間の差を表示し、正解との差とは呼ばない。',body)
    row=a.iloc[20*40:21*40];body=''
    for i,model in enumerate(('common_gaussian','adaptive')):
        t=tables[model].iloc[800:840];x0=70+i*780
        body+=text(x0,190,labels[i+1],28)
        for level in (0,.5,1):
            yy=680-level*400;body+=f'<path d="M{x0+50},{yy}h630" stroke="#cbd5da"/>'+text(x0+38,yy+7,str(level),20,'end')
        for g in ('commercial','green'):
            pts=' '.join(f'{x0+50+j/39*630:.2f},{680-v*400:.2f}' for j,v in enumerate(t['mu_'+g]))
            body+=f'<polyline points="{pts}" fill="none" stroke="{COLORS[g]}" stroke-width="4"/>'
        body+=text(x0+50,725,'西 −1950m',23)+text(x0+680,725,'東 +1950m',23,'end')
    body+=text(70,785,'橙：商業6群　青：緑地等。駅の北50mを通る東西横断線（事前固定）。',24)
    save('transect','横断線で、帰属度の変化を読む','縦軸は0～1。正規化された相対値で、利用者数・人気・需要ではない。',body)
    p=pd.read_csv(OUT/'mapped_locations.csv');body=''
    for i,g in enumerate(('commercial','residential','green')):
        x=45+i*520;sub=p[p.function.eq(g)]
        body+=text(x,180,LABELS[g],26)+box(x,225,460,460,'#f3f7fa')
        for r in sub.itertuples():
            px=x+(r.x-m['center'][0]+2000)/4000*460;py=225+(2000-r.y+m['center'][1])/4000*460
            body+=f'<circle cx="{px:.2f}" cy="{py:.2f}" r="{4 if g=="residential" else 2}" fill="{COLORS[g]}"/>'
        body+=text(x,733,f'{len(sub):,}件／4km四方・北が上',25)
    save('input_audit','推定の前に、入力の偏りを確かめる','1点＝1POI登録。住宅関連サービスを住宅へ読み替えない。未対応カテゴリは除外。',body)
    body=panel(a,55,210,470,a.mu_green,lambda v:mix(COLORS['commercial'],COLORS['green'],v))
    body+=text(590,240,'固定半径 → 適応半径',40)+text(590,315,'POIの密集度で、影響範囲を変える',32)
    for y,s in [(410,'住宅POIは1件：住宅機能は推定できなかった'),(480,'半径変更には安定しても、外部との一致は別問題'),(550,'商業・緑地の「正しい境界」は得られない'),(640,'論文の数式を、日本の公開データで部分追試')]:body+=text(590,y,s,27)
    save('cover_1600x900','POIの影響範囲をPythonで推定する','固定半径・適応半径を比較／吉祥寺4km四方／論文の完全再現ではありません',body)


if __name__=='__main__':render()
