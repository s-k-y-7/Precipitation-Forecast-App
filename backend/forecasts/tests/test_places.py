from django.test import SimpleTestCase, TestCase

from forecasts.pipeline.places import normalize_place_name, search_places


class PlaceSearchTests(SimpleTestCase):
    def test_normalization_ignores_case_accents_punctuation_and_extra_spaces(self):
        self.assertEqual(normalize_place_name("  PÚNCH---   City!!  "), "punch city")

    def test_search_matches_compact_punctuation_variants_and_aliases(self):
        places = [{
            "id": 1,
            "name": "St Johns",
            "aliases": ["St Johns", "Saint Johns"],
            "latitude": 20.0,
            "longitude": 78.0,
            "population": 10000,
            "admin1": "Example State",
        }]

        self.assertEqual(search_places("  ST.   JOHN'S!! ", places)[0]["id"], 1)
        self.assertEqual(search_places("saint johns", places)[0]["id"], 1)

    def test_search_folds_accents_in_the_query_and_place_name(self):
        places = [{
            "id": 2,
            "name": "Punch",
            "aliases": ["Punch"],
            "latitude": 20.0,
            "longitude": 78.0,
            "population": 10000,
            "admin1": "Example State",
        }]

        self.assertEqual(search_places("Pūnch", places)[0]["name"], "Punch")

    def test_results_rank_exact_then_prefix_then_substring_and_limit_to_ten(self):
        places = [
            {"id": 1, "name": "Greater Delhi", "aliases": ["Greater Delhi"], "population": 1000000, "latitude": 20, "longitude": 78},
            {"id": 2, "name": "Delhi", "aliases": ["Delhi"], "population": 1000, "latitude": 20, "longitude": 78},
            {"id": 3, "name": "Delhi Cantonment", "aliases": ["Delhi Cantonment"], "population": 500, "latitude": 20, "longitude": 78},
            *[
                {"id": index, "name": f"Place {index} Delhi", "aliases": [f"Place {index} Delhi"], "population": index, "latitude": 20, "longitude": 78}
                for index in range(4, 16)
            ],
        ]

        results = search_places("delhi", places)

        self.assertEqual(results[0]["id"], 2)
        self.assertEqual(results[1]["id"], 3)
        self.assertEqual(results[2]["id"], 1)
        self.assertEqual(len(results), 10)
        self.assertEqual(search_places("!", places), [])


class PlaceSearchApiTests(TestCase):
    def test_search_api_returns_india_places_with_location_context(self):
        from forecasts.pipeline.india import is_inside_india

        response = self.client.get("/api/places/search/?q=  MUMBAI!! ")

        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.data["results"]), 0)
        self.assertLessEqual(len(response.data["results"]), 10)
        mumbai = next(place for place in response.data["results"] if place["name"] == "Mumbai")
        self.assertEqual(mumbai["admin1"], "Maharashtra")
        self.assertTrue(is_inside_india(mumbai["longitude"], mumbai["latitude"]))

    def test_short_or_nonmatching_search_returns_no_results(self):
        self.assertEqual(self.client.get("/api/places/search/?q=m").data, {"results": []})
        self.assertEqual(self.client.get("/api/places/search/?q=Atlantis").data, {"results": []})
