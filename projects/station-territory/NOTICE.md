# Third-party code provenance

Analysis modules are adapted from the user's public [eki-walk](https://github.com/isshiki/eki-walk) repository, commit `35fd7334ab36ae583c2992602975e63be101b594`, under Apache-2.0.

- `territory.py`: `artifacts/station-ranking-20261004/scripts/analysis_core.py`.
- `population.py`: `population_analysis.py`; withdrawn age analysis removed, contribution reconciliation added.
- `poi.py`: `poi_analysis.py`; local paths and cache verification adapted.
- `groups.py`: `src/eki_walk/territory/groups.py`; grouping rules retained.
- `grid.py`: grid loading format from [rail-gap-map](https://github.com/isshiki/rail-gap-map), commit `4176263d09ae9549f8feb16852adfc4378cac29c`, Apache-2.0; midpoint helper from eki-walk.

Changes: independent project paths, no stale POI columns inherited, no withdrawn age or unweighted-distance rankings. Source projects are not edited. These code licenses do not cover input datasets.

`src/station_territory/_upstream/` contains only the numerical/configuration modules needed to replay the road grid from rail-gap-map at the commit above. The original installed-file SHA-256 values are in `configs/upstream-code.json`. `network.py` and `water.py` replace automatic extension installation with an explicitly available local extension. No website or map-product UI is copied. See the included Apache-2.0 LICENSE.
