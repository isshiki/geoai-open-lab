"""Invented local fixtures for conservative comparison; no remote data."""
import unittest
import pandas as pd
from shapely import Point, to_wkb

from geoai_open_lab.poi_comparison import (normalize_name, name_similarity,
    comparison_view, attribute_presence, candidate_pairs, classify_pairs,
    unmatched_records, three_way, phone_keys, domain_keys, evidence,
    address_evidence, has_foursquare_source, distance_histogram, exact_name_distances)


def view(source, items):
    return pd.DataFrame([dict(source=source, source_id=ident, name=name,
        name_normalized=normalize_name(name), longitude=x, latitude=35.703,
        phones=[], websites=[], address_parts=[]) for ident, name, x in items])


class MatchingTests(unittest.TestCase):
    def setUp(self):
        self.left = view("foursquare", [("f1", "架空 Ｃｏｆｆｅｅ 吉祥寺店", 139.58)])
        self.right = view("overture", [("o1", "架空 Coffee 吉祥寺店", 139.58001)])

    def test_normalization_and_empty(self):
        self.assertEqual(normalize_name("  株式会社　Ａ  Coffee\n本店！ "), "株式会社 a coffee 本店!")
        self.assertEqual(normalize_name(None), "")
        self.assertIsNone(name_similarity("", ""))
        self.assertEqual(name_similarity("tide", "diet"), name_similarity("diet", "tide"))

    def test_exact_distance_and_one_to_one(self):
        pairs = classify_pairs(candidate_pairs(self.left, self.right))
        self.assertEqual(pairs.status.tolist(), ["high_confidence"])
        self.assertTrue(0.8 < pairs.distance_m.iloc[0] < 1.0)
        self.assertTrue(unmatched_records(self.left, self.right, pairs).empty)

    def test_near_different_and_far_same(self):
        right = view("overture", [("o1", "全く別の架空名称", 139.58001),
                                  ("o2", self.left.name.iloc[0], 139.59)])
        pairs = classify_pairs(candidate_pairs(self.left, right))
        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs.status.iloc[0], "unmatched")
        reasons = unmatched_records(self.left, right, pairs).set_index("source_id").reason
        self.assertEqual(reasons["o2"], "no_spatial_candidate")
        self.assertEqual(reasons["f1"], "spatial_candidate_but_no_name_evidence")
        self.assertGreater(max(exact_name_distances(self.left, right)), 100)

    def test_empty_names_not_match(self):
        a, b = view("foursquare", [("f", None, 139.58)]), view("osm", [("o", "", 139.58)])
        pairs = classify_pairs(candidate_pairs(a, b))
        self.assertFalse(pairs.exact_name_match.iloc[0])
        self.assertEqual(set(unmatched_records(a, b, pairs).reason), {"insufficient_evidence"})

    def test_similar_name_only(self):
        a = view("foursquare", [("f", "imaginary coffee central", 139.58)])
        b = view("osm", [("s", "imaginary coffee central!", 139.58)])
        pairs = classify_pairs(candidate_pairs(a, b))
        self.assertEqual(pairs.status.iloc[0], "ambiguous")
        self.assertIn("similar_name_only", pairs.reasons.iloc[0])

    def test_all_candidates_and_competing_far_exact(self):
        b = pd.concat([self.right, view("overture", [("o2", self.left.name.iloc[0], 139.5807)])], ignore_index=True)
        pairs = classify_pairs(candidate_pairs(self.left, b))
        self.assertEqual(len(pairs), 2)
        self.assertEqual(set(pairs.status), {"ambiguous"})
        self.assertTrue(pairs.reasons.str.contains("multiple_exact_name_candidates").all())
        self.assertIn("distance_over_auto_threshold", pairs.reasons.iloc[1])
        self.assertEqual(set(unmatched_records(self.left, b, pairs).reason), {"ambiguous_candidate_exists"})

    def test_similar_competitor_blocks_exact(self):
        b = pd.concat([self.right, view("overture", [("o2", self.left.name.iloc[0] + "!", 139.5801)])], ignore_index=True)
        pairs = classify_pairs(candidate_pairs(self.left, b))
        self.assertEqual(set(pairs.status), {"ambiguous"})
        self.assertTrue(pairs.reasons.str.contains("competing_candidate").all())

    def test_conflicting_contacts_and_support_not_promotion(self):
        self.left.at[0, "phones"] = ["03-1234-5678"]
        self.right.at[0, "phones"] = ["03-1234-9999"]
        pairs = classify_pairs(candidate_pairs(self.left, self.right))
        self.assertEqual(pairs.status.iloc[0], "ambiguous")
        self.assertIn("conflicting_phone", pairs.reasons.iloc[0])
        self.right.at[0, "phones"] = ["+81 3 1234 5678"]
        self.right.at[0, "name_normalized"] = "other invented shop"
        pairs = classify_pairs(candidate_pairs(self.left, self.right))
        self.assertEqual(pairs.phone_evidence.iloc[0], "supporting")
        self.assertEqual(pairs.status.iloc[0], "ambiguous")

    def test_contact_keys_and_address(self):
        self.assertEqual(phone_keys(["03-1234-5678"]), phone_keys(["+81 (3) 1234-5678"]))
        self.assertEqual(phone_keys(["unknown", "123"]), set())
        self.assertEqual(domain_keys(["https://www.example.invalid/shop?a=1"]), {"example.invalid"})
        self.assertEqual(evidence({"a"}, {"b"}), "conflicting")
        self.assertEqual(evidence(set(), {"b"}), "unavailable")
        self.assertEqual(address_evidence([{"postcode": "100-0001"}], [{"addr:postcode": "200-0001"}]), "conflicting")
        self.assertEqual(address_evidence([{"freeform": "架空1"}], [{"addr:full": "架空１"}]), "supporting")
        self.assertEqual(address_evidence([{"locality": "架空市"}], [{"addr:city": "架空市"}]), "not_comparable")

    def test_shared_domain_alone_is_not_strong_competitor(self):
        self.left.at[0, "websites"] = ["https://example.invalid/store-a"]
        self.right.at[0, "websites"] = ["https://example.invalid/store-a"]
        b = pd.concat([self.right, view("overture", [("o2", "全く異なる名前", 139.5801)])], ignore_index=True)
        b.at[1, "websites"] = ["https://example.invalid/store-b"]
        pairs = classify_pairs(candidate_pairs(self.left, b)).set_index("right_id")
        self.assertEqual(pairs.loc["o1", "status"], "high_confidence")
        self.assertEqual(pairs.loc["o2", "status"], "ambiguous")

    def test_website_conflict_blocks_high(self):
        self.left.at[0, "websites"] = ["https://one.invalid"]
        self.right.at[0, "websites"] = ["https://two.invalid"]
        pair = classify_pairs(candidate_pairs(self.left, self.right)).iloc[0]
        self.assertEqual(pair.status, "ambiguous")
        self.assertIn("conflicting_website", pair.reasons)

    def test_triangle_only(self):
        frame = lambda pairs: pd.DataFrame(pairs, columns=["left_id", "right_id"])
        accepted = {"foursquare_overture": frame([("f", "o")]),
                    "foursquare_osm": frame([("f", "s")]), "overture_osm": frame([])}
        self.assertTrue(three_way(accepted).empty)
        accepted["overture_osm"] = frame([("o", "s")])
        self.assertEqual(three_way(accepted).to_dict("records"), [{"foursquare": "f", "overture": "o", "osm": "s"}])

    def test_no_candidates_and_bin_boundaries(self):
        right = view("osm", [("o", "far", 140)])
        pairs = classify_pairs(candidate_pairs(self.left, right))
        self.assertTrue(pairs.empty)
        self.assertEqual(set(unmatched_records(self.left, right, pairs).reason), {"no_spatial_candidate"})
        self.assertEqual(distance_histogram([0, 5, 5.1, 100, 100.1]),
                         {"5": 2, "10": 1, "20": 0, "30": 0, "50": 0, "100": 1, ">100": 1})


class ViewTests(unittest.TestCase):
    def test_osm_address_only_accepted_ids(self):
        records = [{"osm_type": "node", "osm_id": 1, "name": "invented", "longitude": 139.58,
                    "latitude": 35.703, "amenity": "cafe", "contact:website": "example.invalid"}]
        raw = {"elements": [{"type": "node", "id": 1, "tags": {"addr:full": "架空住所"}},
                            {"type": "node", "id": 999, "tags": {"addr:full": "対象外"}}]}
        frame = comparison_view("osm", records, osm_raw=raw)
        self.assertEqual(len(frame), 1)
        self.assertTrue(frame.has_address.iloc[0])
        self.assertTrue(frame.has_website.iloc[0])
        self.assertEqual(frame.source_id.iloc[0], "node/1")
        with self.assertRaises(ValueError):
            comparison_view("osm", records, osm_raw={"elements": []})

    def test_fsq_brand_na_presence_and_categories(self):
        rows = [{"fsq_place_id": "f1", "name": " ", "longitude": 139.58, "latitude": 35.703,
                 "country": "JP", "fsq_category_ids": ["invented-category"]}]
        frame = comparison_view("foursquare", rows, categories=[{"category_id": "invented-category", "category_name": "Invented"}])
        self.assertIsNone(frame.has_brand.iloc[0])
        self.assertFalse(frame.has_address.iloc[0])
        presence = attribute_presence({"foursquare": frame}).set_index("attribute")
        self.assertTrue(pd.isna(presence.loc["brand", "count"]))
        self.assertEqual(presence.loc["name", "denominator"], 1)
        self.assertEqual(presence.loc["name", "count"], 0)
        self.assertEqual(presence.loc["category", "count"], 1)

    def test_overture_source_audit_cannot_change_matching(self):
        r = {"id": "o", "geometry": to_wkb(Point(139.58, 35.703)), "names": {"primary": "架空"},
             "sources": [{"provider": "Foursquare"}], "addresses": [{"country": "JP"}]}
        first = comparison_view("overture", [r])
        self.assertTrue(first.has_foursquare_source.iloc[0])
        self.assertFalse(first.has_address.iloc[0])
        r["sources"] = []
        second = comparison_view("overture", [r])
        left = view("foursquare", [("f", "架空", 139.58)])
        pd.testing.assert_frame_equal(candidate_pairs(left, first), candidate_pairs(left, second))
        self.assertTrue(has_foursquare_source([{"dataset": "foursquare"}]))


if __name__ == "__main__":
    unittest.main()
