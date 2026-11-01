#!/usr/bin/env python3
"""Reproducible geographic-access screening for 40 incorporated Southern towns.

Inputs: U.S. Census places Gazetteer and HRSA Health Center Service Delivery Sites.
Distances: great-circle miles to nearest and third-nearest HRSA listed site.
Grouping: z-score features and reproducible Lloyd K-means (k=3 by default).
The output is a geographic screening model, not a diagnosis of medical shortage.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
from pathlib import Path
from statistics import mean, median
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CENSUS_BASE = "https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2024_Gazetteer/"
HRSA_QUERY = "https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/HealthCareFacilities/MapServer/18/query"
STATES = (("AL", "01"), ("AR", "05"), ("LA", "22"), ("MS", "28"))
EXPORT_COLUMNS = (
    "distance_rank", "town", "state", "geoid", "latitude", "longitude",
    "nearest_miles", "third_nearest_miles", "cluster", "nearest_clinic",
    "clinic_address", "clinic_site_id", "within_10_miles", "within_25_miles",
)


def fetch(url: str) -> str:
    request = Request(url, headers={"User-Agent": "GeographicAccessResearch/1.0"})
    with urlopen(request, timeout=60) as response:
        return response.read().decode("utf-8-sig")


def select_towns(gazetteer_tsv: str, state: str, count: int = 10) -> list[dict]:
    """Deterministically sample town-designated places across sorted Census GEOIDs.

    This is an objective systematic sample, NOT a ranked list of communities
    needing the most assistance.
    """
    candidates = []
    for row in csv.DictReader(io.StringIO(gazetteer_tsv), delimiter="\t"):
        place_name = (row.get("NAME") or "").strip()
        if not place_name.endswith(" town") or row.get("FUNCSTAT") != "A":
            continue
        try:
            lat = float(row["INTPTLAT"])
            lon = float(row["INTPTLONG"])
        except (ValueError, TypeError, KeyError):
            continue
        if math.isfinite(lat) and math.isfinite(lon):
            candidates.append({
                "town": place_name.removesuffix(" town"),
                "state": state,
                "geoid": row["GEOID"].strip(),
                "latitude": lat,
                "longitude": lon,
            })
    candidates.sort(key=lambda r: r["geoid"])
    if len(candidates) < count:
        raise ValueError(f"Expected at least {count} Census towns in {state}; found {len(candidates)}")
    return [candidates[int((i + .5) * len(candidates) / count)] for i in range(count)]


def hrsa_url() -> str:
    params = {
        "where": "1=1", "geometry": "-97,27,-83,39",
        "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": "OBJECTID,SITE_NM,SITE_ADDRESS,SITE_CITY,SITE_STATE_ABBR",
        "returnGeometry": "true", "outSR": "4326", "f": "json",
    }
    return f"{HRSA_QUERY}?{urlencode(params)}"


def parse_sites(document: str) -> list[dict]:
    payload = json.loads(document)
    if payload.get("error"):
        raise RuntimeError(f"HRSA query error: {payload['error']}")
    if payload.get("exceededTransferLimit"):
        raise RuntimeError("HRSA API result was truncated; cannot calculate honest nearest distances.")
    sites = []
    for feature in payload.get("features", []):
        a = feature.get("attributes") or {}
        g = feature.get("geometry") or {}
        try:
            lat, lon = float(g["y"]), float(g["x"])
        except (ValueError, TypeError, KeyError):
            continue
        if not all(map(math.isfinite, [lat, lon])):
            continue
        sites.append({
            "name": a.get("SITE_NM") or "Unnamed HRSA site",
            "address": ", ".join(str(v) for v in (
                a.get("SITE_ADDRESS"), a.get("SITE_CITY"), a.get("SITE_STATE_ABBR")
            ) if v),
            "site_id": str(a.get("OBJECTID") or ""),
            "latitude": lat, "longitude": lon,
        })
    if len(sites) < 250:
        raise RuntimeError("Too few HRSA site records. Aborting instead of inventing distances.")
    return sites


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in statute miles, for coordinate pairs in degrees."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 3958.7613 * 2 * math.asin(math.sqrt(max(0, min(1, a))))


def measure_towns(towns: list[dict], sites: list[dict]) -> list[dict]:
    if len(sites) < 3:
        raise ValueError("At least three sites are required for the nearest/third-nearest measures")
    measured = []
    for town in towns:
        distances = sorted(
            ((haversine_miles(town["latitude"], town["longitude"],
                              site["latitude"], site["longitude"]), site) for site in sites),
            key=lambda pair: pair[0],
        )
        nearest = distances[0][1]
        measured.append({
            **town,
            "nearest_miles": round(distances[0][0], 2),
            "third_nearest_miles": round(distances[2][0], 2),
            "nearest_clinic": nearest["name"],
            "clinic_address": nearest["address"],
            "clinic_site_id": nearest["site_id"],
            "within_10_miles": sum(distance <= 10 for distance, _ in distances),
            "within_25_miles": sum(distance <= 25 for distance, _ in distances),
        })
    return measured


def kmeans_distances(records: list[dict], k: int = 3) -> list[dict]:
    """Standardized, deterministically initialized two-feature K-means.

    The three-seed case reproduces the published web tool's initialization.
    Labels are descriptive relative-distance groupings, not medical diagnoses.
    """
    if not 2 <= k <= len(records):
        raise ValueError("k must be between 2 and the number of towns")
    features = [
        [float(r["nearest_miles"]), float(r["third_nearest_miles"])]
        for r in records
    ]
    means = [mean(row[j] for row in features) for j in range(2)]
    scales = [
        math.sqrt(mean((row[j] - means[j]) ** 2 for row in features)) or 1.0
        for j in range(2)
    ]
    xy = [[(row[j] - means[j]) / scales[j] for j in range(2)] for row in features]
    order = sorted(range(len(xy)), key=lambda i: (xy[i][0] + xy[i][1], i))
    if k == 3 and len(records) == 40:
        seeds = [order[6], order[20], order[33]]
    else:
        seeds = [order[min(len(order)-1, int((i + .5) * len(order) / k))] for i in range(k)]
    centroids = [xy[i][:] for i in seeds]
    labels = [0] * len(records)
    for _ in range(100):
        new_labels = [
            min(range(k), key=lambda i: (sum((p[j]-centroids[i][j])**2 for j in range(2)), i))
            for p in xy
        ]
        next_centroids = []
        for i in range(k):
            points = [xy[j] for j in range(len(xy)) if new_labels[j] == i]
            next_centroids.append([mean(p[dim] for p in points) for dim in range(2)] if points else centroids[i])
        delta = sum(abs(next_centroids[i][j]-centroids[i][j]) for i in range(k) for j in range(2))
        changed = new_labels != labels
        labels, centroids = new_labels, next_centroids
        if delta < 1e-10 or not changed:
            break
    ordered_centers = sorted(range(k), key=lambda i: centroids[i][0]*scales[0]+means[0])
    names = ("Closer", "Intermediate", "Farther") if k == 3 else tuple(f"Group {i+1}" for i in range(k))
    group_names = {i: names[rank] for rank, i in enumerate(ordered_centers)}
    output = [{**record, "cluster": group_names[label]} for record, label in zip(records, labels)]
    output.sort(key=lambda r: -float(r["nearest_miles"]))
    for rank, record in enumerate(output, 1):
        record["distance_rank"] = rank
    return output


def output_files(records: list[dict], directory: Path, clinic_count: int | None = None) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "town_access.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=EXPORT_COLUMNS)
        writer.writeheader()
        for row in records:
            writer.writerow({key: row.get(key, "") for key in EXPORT_COLUMNS})

    features = []
    for record in records:
        features.append({
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [record["longitude"], record["latitude"]]},
            "properties": {key: val for key, val in record.items() if key not in ("longitude", "latitude")},
        })
    (directory / "town_access.geojson").write_text(
        json.dumps({"type": "FeatureCollection", "features": features}, indent=2), encoding="utf-8"
    )
    miles = [float(row["nearest_miles"]) for row in records]
    summary = {
        "town_count": len(records),
        "clinic_count": clinic_count,
        "median_nearest_miles": round(median(miles), 2),
        "mean_nearest_miles": round(mean(miles), 2),
        "maximum_nearest_miles": max(miles),
        "minimum_nearest_miles": min(miles),
        "cluster_counts": {label: sum(r["cluster"] == label for r in records)
                           for label in sorted({r["cluster"] for r in records})},
        "sources": {
            "census_gazetteer": CENSUS_BASE,
            "hrsa_service_delivery_sites": HRSA_QUERY,
            "hrsa_query": hrsa_url()
        },
        "method": "Great-circle distance; standardized nearest and third-nearest site distances; deterministic K-means.",
        "interpretation": "Geographic screening only. HRSA sites include some school/mobile/special-purpose records; not all primary-care clinics, road travel, or verified aid allocation.",
    }
    (directory / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def read_snapshot(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="", encoding="utf-8") as file:
        rows = list(csv.DictReader(file))
    for row in rows:
        for key in ("latitude", "longitude", "nearest_miles", "third_nearest_miles"):
            row[key] = float(row[key])
    if len(rows) != 40:
        raise ValueError(f"Expected 40 rows in snapshot; got {len(rows)}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true",
                        help="Re-fetch current official Census and HRSA data; otherwise use stored snapshot")
    parser.add_argument("--out", type=Path, default=DATA, help="Output directory")
    args = parser.parse_args()
    if args.refresh:
        towns = []
        for state, fips in STATES:
            source = f"{CENSUS_BASE}2024_gaz_place_{fips}.txt"
            towns.extend(select_towns(fetch(source), state))
        sites = parse_sites(fetch(hrsa_url()))
        measured = measure_towns(towns, sites)
        total_sites = len(sites)
    else:
        measured = read_snapshot(DATA / "town_access.csv")
        total_sites = None
    clustered = kmeans_distances(measured)
    summary = output_files(clustered, args.out, total_sites)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
