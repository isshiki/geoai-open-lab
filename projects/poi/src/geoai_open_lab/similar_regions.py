"""Predeclared block-balanced station similarity and sensitivity checks."""
import numpy as np
import pandas as pd

DENSITY = 'poi_density_per_km2'
CONCENTRATION = 'peak_to_mean_density_250m'
CATEGORIES = ('restaurant_share','cafe_share','bar_share','fashion_share','beauty_share','food_store_share')
FEATURES = (DENSITY,*CATEGORIES,CONCENTRATION)
MODES = ('main','density_only','standard','no_density','no_concentration')


def overlap_audit(stations, target='n02-003584'):
    if stations.region_id.duplicated().any():
        raise ValueError('Duplicate station ID')
    center = stations.set_index('region_id').loc[target]
    dx = (stations.x-center.x).abs()
    dy = (stations.y-center.y).abs()
    audit = stations[['region_id','station_name']].copy()
    audit['center_distance_m'] = np.hypot(dx,dy)
    audit['overlap_m2'] = np.maximum(1000-dx,0)*np.maximum(1000-dy,0)
    audit['overlap_fraction'] = audit.overlap_m2/1e6
    audit['excluded_from_main'] = audit.overlap_m2 > 0
    audit['is_target'] = audit.region_id == target
    return audit


def rank_regions(profiles, stations, target='n02-003584'):
    if profiles.region_id.duplicated().any() or set(profiles.region_id)!=set(stations.region_id):
        raise ValueError('Profile/station identity mismatch')
    frame = profiles.sort_values('region_id').set_index('region_id')
    if (frame.poi_count<0).any():
        raise ValueError('Negative count')
    zero = frame.index[frame.poi_count==0].tolist()
    frame = frame.loc[frame.poi_count>0]
    if target not in frame.index:
        raise ValueError('Target profile undefined')
    values = frame[list(FEATURES)].astype(float).copy()
    if not np.isfinite(values).all().all() or (values<0).any().any():
        raise ValueError('Invalid positive-count feature')
    values[DENSITY] = np.log1p(values[DENSITY])
    values[CONCENTRATION] = np.log1p(values[CONCENTRATION])
    med = values.median()
    iqr = values.quantile(.75)-values.quantile(.25)
    sd = values.std(ddof=0)
    if (iqr==0).any() or (sd==0).any():
        raise ValueError('Zero IQR/standard deviation; stop before ranking')
    audit = overlap_audit(stations,target).set_index('region_id')
    outputs = {}
    for mode in MODES:
        scaled = (values-values.mean())/sd if mode=='standard' else (values-med)/iqr
        delta = scaled-scaled.loc[target]
        squared = delta.pow(2)
        blocks = pd.DataFrame(dict(density=squared[DENSITY],
            composition=squared[list(CATEGORIES)].sum(axis=1)/6,
            concentration=squared[CONCENTRATION]))
        if mode=='density_only': blocks[['composition','concentration']] = 0.
        if mode=='no_density': blocks['density'] = 0.
        if mode=='no_concentration': blocks['concentration'] = 0.
        total = blocks.sum(axis=1)
        distance = np.sqrt(total)
        if distance.loc[target] != 0:
            raise ValueError('Self distance must be zero')
        result = pd.DataFrame(dict(distance=distance))
        for col in blocks:
            result[col+'_squared'] = blocks[col]
            result[col+'_contribution'] = blocks[col]/total.replace(0,np.nan)
        result = result.join(stations.set_index('region_id')[['station_name','longitude','latitude']])
        result = result.join(audit[['overlap_m2','center_distance_m','excluded_from_main']])
        result = result.drop(index=target).reset_index().sort_values(['distance','region_id']).reset_index(drop=True)
        result['audit_rank'] = np.arange(1,len(result)+1)
        result['rank'] = pd.Series(pd.NA,index=result.index,dtype='Int64')
        keep = ~result.excluded_from_main
        result.loc[keep,'rank'] = np.arange(1,keep.sum()+1)
        if not np.allclose(result.loc[result.distance>0,['density_contribution','composition_contribution','concentration_contribution']].sum(axis=1),1):
            raise ValueError('Contribution sum differs from one')
        outputs[mode] = result
    main = outputs['main'].dropna(subset=['rank']).set_index('region_id')
    top = set(main.index[main['rank']<=10])
    stability=[]
    for mode,r in outputs.items():
        ids = set(r.loc[r['rank']<=10,'region_id'])
        intersection = len(top & ids)
        stability.append(dict(mode=mode,top10_overlap=intersection,
            top10_jaccard=intersection/len(top|ids) if top|ids else np.nan,
            candidate_count=int(r['rank'].notna().sum())))
        r['main_rank'] = r.region_id.map(main['rank'])
        r['rank_change_from_main'] = r['rank']-r.main_rank
    scaling = dict(columns=list(FEATURES),log1p=[DENSITY,CONCENTRATION],
        median=med.to_dict(),iqr=iqr.to_dict(),mean=values.mean().to_dict(),std_ddof0=sd.to_dict(),
        fit_region_ids=frame.index.tolist(),zero_count_excluded=zero,category_weight=1/np.sqrt(6))
    return outputs,pd.DataFrame(stability),audit.reset_index(),scaling
