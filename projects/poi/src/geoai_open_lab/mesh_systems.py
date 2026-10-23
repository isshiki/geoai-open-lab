"""Offline, deliberately bounded mesh/index comparison at three Japanese points.

IDs/neighbor definitions are scheme-specific, not interchangeable resolutions.
No downloaded datasets, tile server, or online coordinate grids are required.
"""
from pathlib import Path
from datetime import datetime, timezone
from importlib.metadata import version
from hashlib import sha256
import json
import math
import platform
import h3
import mgrs
import s2sphere as s2
import pandas as pd
from pyproj import Geod, Transformer, network
from shapely.geometry import Polygon, Point, mapping
from .standard_mesh_guide import encode, bounds, parent, children

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT/'data/cache/mesh_systems/comparison-v1'
POINTS = {'東京・吉祥寺': (35.70314448120142,139.57980985190306),
          '札幌付近': (43.06,141.35), '那覇付近': (26.21,127.68)}
BASE32 = '0123456789bcdefghjkmnpqrstuvwxyz'
GEOD = Geod(ellps='WGS84')
network.set_network_enabled(False)


def rectangle(w,s,e,n, inverse=None):
    corners=[(w,s),(e,s),(e,n),(w,n),(w,s)]
    pts=[(a[0]+i/16*(b[0]-a[0]),a[1]+i/16*(b[1]-a[1]))
         for a,b in zip(corners,corners[1:]) for i in range(16)]
    if inverse:
        pts=[inverse.transform(x,y) for x,y in pts]
    return Polygon(pts)


def geohash_encode(lat,lon,length=6):
    if not -90 <= lat < 90 or not -180 <= lon < 180 or length < 1:
        raise ValueError('Invalid Geohash input')
    ranges=[[-180.,180.],[-90.,90.]]; values=[lon,lat]; bits=[]
    for i in range(length*5):
        axis=i%2; mid=sum(ranges[axis])/2; bit=int(values[axis]>=mid)
        ranges[axis][1-bit]=mid; bits.append(bit)
    return ''.join(BASE32[sum(bits[i+j] << (4-j) for j in range(5))] for i in range(0,len(bits),5))


def geohash_bounds(code):
    ranges=[[-180.,180.],[-90.,90.]];i=0
    if not code or any(c not in BASE32 for c in code):
        raise ValueError('Invalid Geohash')
    for char in code:
        for shift in reversed(range(5)):
            axis=i%2;bit=(BASE32.index(char)>>shift)&1
            ranges[axis][1-bit]=sum(ranges[axis])/2;i+=1
    return ranges[0][0],ranges[1][0],ranges[0][1],ranges[1][1]


def tile(lat,lon,z=16):
    if not -85.05112878 < lat < 85.05112878 or not -180 <= lon < 180 or z < 0:
        raise ValueError('Outside Web Mercator tile domain')
    n=2**z
    return z,math.floor((lon+180)/360*n),math.floor((1-math.asinh(math.tan(math.radians(lat)))/math.pi)/2*n)


def tile_bounds(z,x,y):
    n=2**z
    if not 0<=x<n or not 0<=y<n: raise ValueError('Invalid tile')
    lon=lambda i:i/n*360-180
    lat=lambda j:math.degrees(math.atan(math.sinh(math.pi*(1-2*j/n))))
    return lon(x),lat(y+1),lon(x+1),lat(y)


def quadkey(z,x,y):
    tile_bounds(z,x,y)
    return ''.join(str(((x>>s)&1)+2*((y>>s)&1)) for s in reversed(range(z)))


def quad_decode(code):
    if any(c not in '0123' for c in code): raise ValueError('Invalid Quadkey')
    x=y=0
    for c in code: x=2*x+(int(c)&1);y=2*y+(int(c)>>1)
    return len(code),x,y


def record(city,scheme,level,id,poly,parent_id,child_ids,neighbors,shape):
    lat,lon=POINTS[city]
    assert poly.is_valid and poly.covers(Point(lon,lat)), (city,scheme,id)
    area=abs(GEOD.geometry_area_perimeter(poly)[0])/1e6
    return dict(city=city,scheme=scheme,level=str(level),cell_id=str(id),area_km2=area,
                shape=shape,parent_id=parent_id,child_ids=child_ids,neighbors=sorted(map(str,neighbors)),
                child_count=len(child_ids),neighbor_count=len(neighbors),geometry=mapping(poly))


def compare_point(city):
    lat,lon=POINTS[city];rows=[]
    def add(*args): rows.append(record(city,*args))
    # JGD2011 coordinates: transform explicitly, never silently relabel WGS84.
    jlon,jlat=Transformer.from_crs(4326,6668,always_xy=True).transform(lon,lat)
    inv=Transformer.from_crs(6668,4326,always_xy=True)
    code=encode(jlat,jlon);w,s,e,n=bounds(code)
    near=[encode((s+n)/2+dy*(n-s),(w+e)/2+dx*(e-w)) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]]
    add('標準地域メッシュ','2分の1・9桁',code,rectangle(w,s,e,n,inv),parent(code),children(code),near,'緯経度の四辺形')
    hid=h3.latlng_to_cell(lat,lon,8)
    add('H3','resolution 8',hid,Polygon([(b,a) for a,b in h3.cell_to_boundary(hid)]),h3.cell_to_parent(hid),sorted(h3.cell_to_children(hid)),set(h3.grid_disk(hid,1))-{hid},'六角形（例外は五角形）')
    sid=s2.CellId.from_lat_lng(s2.LatLng.from_degrees(lat,lon)).parent(14);cell=s2.Cell(sid)
    vertices=[s2.LatLng.from_point(cell.get_vertex(i)) for i in range(4)]
    add('S2','level 14',sid.to_token(),Polygon([(p.lng().degrees,p.lat().degrees) for p in vertices]),sid.parent().to_token(),[c.to_token() for c in sid.children()],[c.to_token() for c in sid.get_edge_neighbors()],'球面四辺形')
    gh=geohash_encode(lat,lon);w,s,e,n=geohash_bounds(gh)
    near=[geohash_encode((s+n)/2+dy*(n-s),(w+e)/2+dx*(e-w)) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]]
    add('Geohash','6文字',gh,rectangle(w,s,e,n),gh[:-1],[gh+c for c in BASE32],near,'緯経度の長方形')
    z,x,y=tile(lat,lon);ids=[(z+1,x*2+dx,y*2+dy) for dx in (0,1) for dy in (0,1)]
    near=[(z,(x+dx)%2**z,y+dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)] if 0<=y+dy<2**z]
    txt=lambda t:'/'.join(map(str,t))
    add('XYZ','zoom 16',txt((z,x,y)),rectangle(*tile_bounds(z,x,y)),txt((z-1,x//2,y//2)),list(map(txt,ids)),list(map(txt,near)),'投影上の正方形')
    add('Quadkey','16桁',quadkey(z,x,y),rectangle(*tile_bounds(z,x,y)),quadkey(z-1,x//2,y//2),[quadkey(*t) for t in ids],[quadkey(*t) for t in near],'XYZと同じ境界')
    m=mgrs.MGRS();mid=m.toMGRS(lat,lon,MGRSPrecision=2)
    # This comparison is restricted to Japan, within a UTM zone, northern hemisphere.
    zone=int(mid[:2]);fwd=Transformer.from_crs(4326,32600+zone,always_xy=True);inv=Transformer.from_crs(32600+zone,4326,always_xy=True)
    swlat,swlon=m.toLatLon(mid);east,north=fwd.transform(swlon,swlat)
    east=round(east/1000)*1000;north=round(north/1000)*1000
    def mc(ex,ny,p=2):
        lo,la=inv.transform(ex,ny);return m.toMGRS(la,lo,MGRSPrecision=p)
    near=[mc(east+500+dx*1000,north+500+dy*1000) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]]
    kids=[mc(east+50+100*i,north+50+100*j,3) for i in range(10) for j in range(10)]
    add('MGRS','precision 2・1km',mid,rectangle(east,north,east+1000,north+1000,inv),m.toMGRS(lat,lon,MGRSPrecision=1),kids,near,'UTM上の正方形')
    if city=='東京・吉祥寺':
        fwd=Transformer.from_crs(4326,6677,always_xy=True);inv=Transformer.from_crs(6677,4326,always_xy=True)
        ex,ny=fwd.transform(lon,lat);i,j=math.floor(ex/500),math.floor(ny/500)
        name=lambda i,j:f'6677:500:{i}:{j}'
        add('独自正方形','500m・原点(0,0)',name(i,j),rectangle(i*500,j*500,(i+1)*500,(j+1)*500,inv),f'6677:1000:{i//2}:{j//2}',[f'6677:250:{2*i+dx}:{2*j+dy}' for dx in (0,1) for dy in (0,1)],[name(i+dx,j+dy) for dx,dy in [(1,0),(-1,0),(0,1),(0,-1)]],'投影上の正方形')
        # Flat-top regular hexagons, axial coordinates; deterministic nearest-center tie.
        radius=300.;q=2*ex/(3*radius);r=(-ex/3+math.sqrt(3)*ny/3)/radius
        candidates=[(a,b) for a in range(math.floor(q)-2,math.floor(q)+3) for b in range(math.floor(r)-2,math.floor(r)+3)]
        center=lambda a,b:(radius*1.5*a,radius*math.sqrt(3)*(b+a/2))
        a,b=min(candidates,key=lambda ab:((center(*ab)[0]-ex)**2+(center(*ab)[1]-ny)**2,ab))
        cx,cy=center(a,b)
        vertices=[(cx+radius*math.cos(k*math.pi/3),cy+radius*math.sin(k*math.pi/3)) for k in range(6)]
        # Densify straight projected edges before inverse transformation.
        pts=[inv.transform(u[0]+t/16*(v[0]-u[0]),u[1]+t/16*(v[1]-u[1])) for u,v in zip(vertices,vertices[1:]+vertices[:1]) for t in range(16)]
        name=lambda a,b:f'6677:hex300:{a}:{b}'
        add('独自六角形','外接半径300m・原点(0,0)',name(a,b),Polygon(pts),None,[],[name(a+da,b+db) for da,db in [(1,0),(1,-1),(0,-1),(-1,0),(-1,1),(0,1)]],'投影上の正六角形')
    return rows


def run(output=OUT):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    rows=[r for city in POINTS for r in compare_point(city)]
    serial=json.dumps(rows,ensure_ascii=False,indent=2)
    (output/'cells.json').write_text(serial,encoding='utf8')
    table=pd.DataFrame([{k:v for k,v in r.items() if k not in ('geometry','child_ids','neighbors')} for r in rows])
    table.to_csv(output/'comparison.csv',index=False,encoding='utf-8-sig')
    manifest={'created_utc':datetime.now(timezone.utc).isoformat(),'python':platform.python_version(),
              'packages':{n:version(n) for n in ('h3','s2sphere','mgrs','pyproj','shapely','pandas')},
              'points_lat_lon':POINTS,'area':'WGS84 ellipsoidal polygon area; lat/lon or projected edges densified 16 segments',
              'source':'Algorithmic cells; no external datasets downloaded. Kichijoji existing N02-25 representative point.',
              'cells_sha256':sha256((output/'cells.json').read_bytes()).hexdigest(),
              'lock_sha256':sha256((ROOT/'uv.lock').read_bytes()).hexdigest(),
              'code_sha256': {name:sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
                              for name in ('mesh_systems.py','standard_mesh_guide.py')},
              'source_review_date':'2026-10-23',
              'reference_document':'docs/mesh-systems.md'}
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return table


if __name__=='__main__':
    print(run().to_string(index=False))
