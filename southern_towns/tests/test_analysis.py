"""No-network tests for the Southern town geographic screening module."""
import csv
import importlib.util
import math
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("town_analyzer", ROOT / "analyze.py")
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)


class GeographicAccessTests(unittest.TestCase):
    def test_haversine_symmetry_and_zero(self):
        f = analyzer.haversine_miles
        self.assertEqual(f(30, -90, 30, -90), 0)
        self.assertAlmostEqual(f(30, -90, 34, -86), f(34, -86, 30, -90), places=8)
        self.assertGreater(f(30, -90, 34, -86), 300)

    def test_selection_is_deterministic(self):
        raw = "GEOID\tNAME\tFUNCSTAT\tINTPTLAT\tINTPTLONG\n"
        raw += "".join(f"{i:07d}\tTown{i:02d} town\tA\t30.1\t-90.1\n" for i in range(30))
        a = analyzer.select_towns(raw, "MS", 10)
        b = analyzer.select_towns(raw, "MS", 10)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 10)
        self.assertEqual(len({r["geoid"] for r in a}), 10)

    def test_snapshot_kmeans(self):
        snap = analyzer.read_snapshot(ROOT / "data" / "town_access.csv")
        result = analyzer.kmeans_distances(snap)
        self.assertEqual(len(result), 40)
        self.assertEqual([r["distance_rank"] for r in result], list(range(1, 41)))
        self.assertEqual(round(result[0]["nearest_miles"], 2), 21.44)
        self.assertEqual(round(result[-1]["nearest_miles"], 2), 0.47)
        self.assertEqual({r["cluster"] for r in result},
                         {"Closer", "Intermediate", "Farther"})

    def test_nearest_site_measurement(self):
        towns = [{"town": "Example", "state": "AR", "geoid": "1",
                  "latitude": 35.0, "longitude": -92.0}]
        sites = [{"name": f"site_{i}", "address": "verified source", "site_id": str(i),
                  "latitude": 35+i*.1, "longitude": -92} for i in range(3)]
        measured = analyzer.measure_towns(towns, sites)
        self.assertEqual(measured[0]["nearest_miles"], 0.0)
        self.assertGreater(measured[0]["third_nearest_miles"], 10)


if __name__ == "__main__":
    unittest.main()
