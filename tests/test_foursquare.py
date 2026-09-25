"""Offline safety tests; all fixture values are invented, not Foursquare data."""

from pathlib import Path
import os
import traceback
import unittest
from unittest.mock import Mock, patch

from geoai_open_lab.foursquare import FoursquareError, connect, pinned_table, query


class FoursquareSafetyTests(unittest.TestCase):
    def test_api_key_and_legacy_token_are_not_portal_credentials(self):
        unrelated = {"FSQ_API_KEY": "invented-api-key", "FSQ_TOKEN": "invented-legacy-token"}
        with patch.dict(os.environ, unrelated, clear=True), patch(
            "geoai_open_lab.foursquare.dotenv_values", return_value=unrelated
        ), patch("geoai_open_lab.foursquare.duckdb.connect") as db:
            with self.assertRaisesRegex(FoursquareError, "FSQ_OS_PLACES_TOKEN is missing"):
                connect(Path.cwd())
            db.assert_not_called()

    def test_project_portal_token_is_used_instead_of_api_key(self):
        connection = Mock()
        values = {"FSQ_API_KEY": "invented-api-key", "FSQ_OS_PLACES_TOKEN": "invented-portal-token"}
        with patch.dict(os.environ, {}, clear=True), patch(
            "geoai_open_lab.foursquare.dotenv_values", return_value=values
        ), patch("geoai_open_lab.foursquare.duckdb.connect", return_value=connection):
            self.assertIs(connect(Path.cwd()), connection)
        sql = "\n".join(call.args[0] for call in connection.execute.call_args_list)
        self.assertIn("TOKEN 'invented-portal-token'", sql)
        self.assertNotIn("invented-api-key", sql)

    def test_missing_token_stops_before_network(self):
        with patch.dict(os.environ, {}, clear=True), patch(
            "geoai_open_lab.foursquare.dotenv_values", return_value={}
        ), patch("geoai_open_lab.foursquare.duckdb.connect") as db:
            with self.assertRaisesRegex(FoursquareError, "FSQ_OS_PLACES_TOKEN is missing"):
                connect(Path.cwd())
            db.assert_not_called()

    def test_env_lookup_stays_in_project_and_disables_interpolation(self):
        root = Path.cwd()
        with patch.dict(os.environ, {}, clear=True), patch(
            "geoai_open_lab.foursquare.dotenv_values", return_value={}
        ) as env:
            with self.assertRaises(FoursquareError):
                connect(root)
            env.assert_called_once_with(root / ".env", interpolate=False)

    def test_connection_error_redacts_token_and_signed_url(self):
        sentinel = "invented-test-secret-do-not-print"
        connection = Mock()
        connection.execute.side_effect = RuntimeError(
            f"Authorization: Bearer {sentinel}; https://example.invalid/?signature={sentinel}"
        )
        with patch.dict(os.environ, {"FSQ_OS_PLACES_TOKEN": sentinel}), patch(
            "geoai_open_lab.foursquare.duckdb.connect", return_value=connection
        ):
            try:
                connect(Path.cwd())
            except FoursquareError:
                rendered = traceback.format_exc()
            else:
                self.fail("Expected a sanitized error")
        self.assertNotIn(sentinel, rendered)
        self.assertNotIn("signature=", rendered)
        connection.close.assert_called_once()

    def test_query_error_redacts_remote_details(self):
        connection = Mock()
        connection.execute.side_effect = RuntimeError("invented-sensitive-header")
        try:
            query(connection, "SELECT 1")
        except FoursquareError:
            self.assertNotIn("invented-sensitive-header", traceback.format_exc())
        else:
            self.fail("Expected a sanitized error")

    def test_snapshot_ids_cannot_inject_sql(self):
        for value in [None, 123, "", "1; SELECT 2", "-1", "１２３", "0", str(2**63)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                pinned_table("places", value)
        self.assertEqual(
            pinned_table("categories", "123"),
            "places.datasets.categories_os AT (VERSION => 123)",
        )


if __name__ == "__main__":
    unittest.main()
