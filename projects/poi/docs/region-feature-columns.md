# 地域特徴量の列定義（schema version 1）

主成果 `region_features.csv` は1地域1行、以下の固定列順。今回は吉祥寺駅周辺の実験用矩形だけ。値は生の数値で、shareは0〜1（図では%）。複数地域へ同じ定義を適用する土台であり、今回類似度は計算しない。

| 列 | 日本語名・単位 | 定義 | 比較時の注意・役割 |
| --- | --- | --- | --- |
| region_id | 地域ID | 設定のregion_id | 結合キー。特徴量として距離計算しない |
| region_label | 地域名 | 吉祥寺駅周辺の実験用矩形 | 吉祥寺全域や商圏を意味しない |
| area_km2 | 対象面積・km² | 投影したAOIの格子交差面積合計/百万 | 監査・説明用。範囲の揃え方が重要 |
| poi_count | POI登録数・件 | 全格子の登録数合計 | 監査・説明用。密度と同時投入すると規模を二重評価しうる |
| poi_density_per_km2 | 平均登録密度・件/km² | poi_count/area_km2 | 比較候補。格子密度の単純平均ではない |
| restaurant_share | 食事群構成比・比率 | restaurantとcasual_eatery件数/全件数 | 比較候補。全飲食業ではない |
| cafe_share | カフェ群構成比・比率 | cafeとcoffee_shop件数/全件数 | 比較候補。Overtureのbasic_categoryに従う |
| bar_share | バー構成比・比率 | bar件数/全件数 | 比較候補 |
| fashion_share | 衣料構成比・比率 | fashion_and_apparel_store件数/全件数 | 比較候補 |
| beauty_share | 美容等構成比・比率 | personal_or_beauty_service件数/全件数 | 比較候補 |
| food_store_share | 食品小売構成比・比率 | food_and_beverage_store件数/全件数 | 比較候補。すべての食品販売店を包含するとは限らない |
| other_share | その他構成比・比率 | 表示6群に含まれない既知分類件数/全件数 | 比較候補。異質な分類をまとめている |
| category_missing_share | カテゴリ欠損率・比率 | basic_category欠損・空文字件数/全件数 | 監査用。地域特性と欠損を混同しない |
| peak_density_250m | 250m最大密度・件/km² | 250m格子の密度の最大値 | 集中度の算出根拠。平均密度・比率との重複に注意 |
| peak_to_mean_density_250m | 250m集中度・倍 | peak_density_250m/poi_density_per_km2 | 比較候補。格子原点・端の小面積・AOIに敏感 |

カテゴリの正本は [設定のdisplay_groups](../configs/region_features.toml)。taxonomyの複数項目を展開せず、1登録を1分類に数える。7群と欠損の構成比合計は1。登録数0の地域では構成比・集中度は未定義（CSVでは空欄）であり、0で埋めない。

比較候補は密度、既知分類の構成比、集中度。これは採用決定ではない。構成比の総和制約、欠損の違い、密度・最大密度・集中度の相互依存を考慮して、複数地域を比較する次段階で採用列・重み・正規化・距離関数を決める。欠損率を無条件に類似度へ入れない。

release・取得日時・AOI・投影座標系・格子原点・解像度・入力ハッシュは別の `manifest.json` で監査する。面積と登録数・欠損率は表にも残して説明可能にする。地域IDを追加するだけで異なる条件のデータを比較してよいわけではない。次回は同じrelease・カテゴリ定義・AOI設定方針・格子条件を確認してから行を追加する。
