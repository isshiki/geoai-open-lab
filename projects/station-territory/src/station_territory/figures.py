"""Article charts from freshly computed results, including source attribution."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .territory import ROOT, RESULT, rank
from .figure_style import add_signature

METRICS = {
    'area_km2': ('駅の縄張りの面積', 'km²'),
    'population': ('駅の縄張りの推計人口', '人'),
    'poi_count': ('駅の縄張りのOSM POI登録数', '登録オブジェクト'),
    'population_mean_m': ('人口加重平均の駅までの道のり', 'm'),
}
ATTRIBUTION = '出典：© OpenStreetMap contributors / 国土数値情報 N02・N03 / 総務省統計局 2020年国勢調査（加工）'


def run():
    plt.rcParams.update({'font.family': ['Meiryo', 'DejaVu Sans'], 'font.size': 12,
                         'axes.spines.top': False, 'axes.spines.right': False})
    output = ROOT / 'data/figures'
    output.mkdir(parents=True, exist_ok=True)
    stations = pd.read_parquet(RESULT / 'all_stations.parquet')
    for field, (title, unit) in METRICS.items():
        eligible = stations.eligible & ((stations.population >= 1000) if field == 'population_mean_m' else True)
        top, _ = rank(stations.assign(eligible=eligible), field)
        fig, ax = plt.subplots(figsize=(11, 7))
        ax.barh(np.arange(len(top)), top[field], color='#37678a', height=.65)
        ax.set_yticks(np.arange(len(top)), top['name'])
        ax.invert_yaxis()
        ax.set_xlabel(unit)
        fig.text(.12, .94, title, fontsize=16, va='center')
        fig.text(.12, .89, '上位10駅 — 東京23区', fontsize=12, color='#555555')
        ax.set_xlim(0, max(top[field].max() * 1.2, 1))
        for i, value in enumerate(top[field]):
            ax.text(value, i, f'  {value:,.2f}' if field == 'area_km2' else f'  {value:,.0f}', va='center', fontsize=12)
        note = '駅代表点が23区内の駅。範囲外駅も割当の競合に含む。'
        if field == 'population_mean_m':
            note += ' 推計人口1,000人以上。実際の通勤・利用距離ではない。'
        if field == 'poi_count':
            note += ' 同一施設の複数OSM要素は未統合。'
        if field == 'population':
            note += ' 250mメッシュ人口の面積按分。'
        if field == 'area_km2':
            note += ' 有効25m格子中心の集計。人口あり面積は付表へ。'
        fig.text(.06, .13, note.replace('。 ', '。\n'), fontsize=10, va='top')
        fig.text(.06, .065, ATTRIBUTION.replace(' / 国土', '\n国土'), fontsize=9, va='top')
        fig.subplots_adjust(left=.17, right=.94, bottom=.24, top=.82)
        add_signature(fig)
        for extension in ('png', 'svg'):
            fig.savefig(output / f'top10_{field}.{extension}', dpi=180)
        plt.close(fig)
    z = np.load(RESULT / 'analysis_cells.npz')
    fig, ax = plt.subplots(figsize=(10, 9))
    valid = z['owner'] >= 0
    ax.scatter(z['x'][valid] / 1000, z['y'][valid] / 1000,
               c=z['owner'][valid] % 20, cmap='tab20', s=.15, linewidths=0, rasterized=True)
    ax.set_aspect('equal')
    ax.set(xlabel='EPSG:6677 東西位置 (km)', ylabel='南北位置 (km)')
    fig.text(.1, .94, '歩行道路網による駅の縄張り', fontsize=16, va='center')
    fig.text(.1, .895, '東京23区', fontsize=12, color='#555555')
    fig.text(.06, .13, '色は繰り返し使用（同色でも同じ駅とは限らない）。\n白い部分には水面・道路から遠い領域・未割当領域を含む。', fontsize=10, va='top')
    fig.text(.06, .065, ATTRIBUTION.replace(' / 国土', '\n国土'), fontsize=9, va='top')
    fig.subplots_adjust(bottom=.2, top=.86)
    add_signature(fig)
    fig.savefig(output / 'territories.png', dpi=180)
    plt.close(fig)


if __name__ == '__main__':
    run()
