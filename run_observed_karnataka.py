#!/usr/bin/env python3
"""Rebuild observed Karnataka access-screening outputs from independently published source files.
This analysis is exploratory: 40 K-Means clusters do NOT establish 40 healthcare deserts.
"""
from __future__ import annotations
import csv
import hashlib
import json
import math
import re
import sys
import urllib.request
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.neighbors import BallTree

VILLAGES_URL = "https://raw.githubusercontent.com/mchittineni/india-village-finder/main/karnataka/data/karnataka_villages.csv"
COORDS_URL = "https://raw.githubusercontent.com/mchittineni/india-village-finder/main/karnataka/data/coords_master.json"
FACILITIES_URL = "https://github.com/yashveeeeeeer/india-geodata/releases/download/healthcare/facilities/INDIA_HEALTH_FACILITIES_NIC.geojson"
KM_PER_RAD = 6371.0088
THRESHOLD_KM = 10.0
N_CLUSTERS_REQUESTED = 40
OUTPUT = Path("outputs")
DATA = Path("data")
DOCS = Path("docs")
CACHE = Path(".cache")

def get_data(url: str, filename: str) -> bytes:
    CACHE.mkdir(exist_ok=True)
    f = CACHE / filename
    if f.exists():
        return f.read_bytes()
    request = urllib.request.Request(url, headers={"User-Agent": "HealthAccessInitiative/1.0 reproducible academic analysis"})
    with urllib.request.urlopen(request, timeout=180) as response:
        result = response.read()
    if not result:
        raise ValueError(f"Empty download from {url}")
    f.write_bytes(result)
    return result

def norm(x: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(x).lower())

def parse_villages(csv_bytes: bytes, coordinates: dict):
    reader = csv.DictReader(StringIO(csv_bytes.decode("utf-8-sig")))
    required = ["Village Code", "Village", "District"]
    if any(k not in reader.fieldnames for k in required):
        raise ValueError(f"Unexpected village CSV schema: {reader.fieldnames}")
    villages = []
    all_rows = 0
    missing_coord = 0
    for row in reader:
        all_rows += 1
        code = str(row.get("Village Code", "")).strip()
        xy = coordinates.get(code)
        if not xy:
            missing_coord += 1
            continue
        lat, lon = xy
        lat, lon = float(lat), float(lon)
        if not (11 <= lat <= 19 and 73 <= lon <= 79):
            continue
        # Drop census towns where village label or category makes it explicit.
        name = str(row["Village"]).strip()
        category = str(row.get("Category", "")).lower()
        if "(ct)" in name.lower() or "urban" in category or "census town" in category:
            continue
        villages.append({
            "village": name,
            "district": row["District"].strip(),
            "state": "Karnataka",
            "village_code": code,
            "latitude": lat,
            "longitude": lon
        })
    if len(villages) < 100:
        raise ValueError(f"Insufficient geocoded villages ({len(villages)}); cannot make claims")
    return pd.DataFrame(villages).drop_duplicates("village_code"), all_rows, missing_coord

def discover_kind(properties: dict):
    # Prefer the published type field over a facility name.
    preferred = ("facilitytype", "typeofhealthfacility", "healthfacilitytype", "facilitycategory",
                 "facilitytypecode", "facility_type", "category", "type", "facility")
    keys = {norm(k): k for k in properties}
    for desired in preferred:
        key = keys.get(norm(desired))
        if key and properties.get(key) not in (None, ""):
            return str(properties[key])
    # Secondary lookup: fields with words "type", "level" or "category".
    for key, value in properties.items():
        if ("type" in norm(key) or "category" in norm(key)) and value is not None:
            return str(value)
    return ""

def acceptable_type(kind: str) -> bool:
    s = kind.strip().lower()
    return bool(re.search(r"(^|[^a-z])(?:phc|chc)(?:$|[^a-z])", s) or
                "primary health cent" in s or "community health cent" in s)

def parse_facilities(data: bytes):
    geo = json.loads(data)
    if geo.get("type") != "FeatureCollection":
        raise ValueError("Expected GeoJSON FeatureCollection for facility source")
    features = geo.get("features", [])
    facility_rows = []
    types_sample = {}
    property_keys = set()
    points_in_bounds = 0
    for feature in features:
        geometry = feature.get("geometry") or {}
        if geometry.get("type") != "Point":
            continue
        coord = geometry.get("coordinates") or []
        if len(coord) < 2: continue
        lon, lat = float(coord[0]), float(coord[1])
        # Broad Karnataka vicinity, including facilities across state borders.
        if not (73.3 <= lon <= 79.2 and 10.6 <= lat <= 19.0):
            continue
        points_in_bounds += 1
        props = feature.get("properties") or {}
        property_keys.update(props.keys())
        kind = discover_kind(props)
        if kind:
            types_sample[kind] = types_sample.get(kind, 0) + 1
        if acceptable_type(kind):
            facility_rows.append({"latitude": lat, "longitude": lon, "facility_type": kind})
    if len(facility_rows) < 50:
        raise ValueError(
            f"Only {len(facility_rows)} PHC/CHC facilities matched; inspect source schema. "
            f"Available keys: {sorted(property_keys)[:45]}. Types seen: {sorted(types_sample.items(), key=lambda x: -x[1])[:25]}"
        )
    df = pd.DataFrame(facility_rows).drop_duplicates(["latitude","longitude","facility_type"])
    return df, points_in_bounds, sorted(property_keys)

def render_map(villages: pd.DataFrame, candidates: pd.DataFrame, summary: pd.DataFrame, facility_df: pd.DataFrame):
    # The complete plotted feature set is included directly, so the map runs when downloaded as a file.
    centers = [{"lat": round(float(row.center_lat),5), "lng": round(float(row.center_lon),5),
                "id": int(row.cluster_id), "count": int(row.village_count),
                "avg": round(float(row.mean_distance_km),1)}
               for row in summary.itertuples()]
    candidate_pts = [{"lat": round(float(row.latitude),5), "lng": round(float(row.longitude),5),
                      "name": str(row.village)[:100], "distance": round(float(row.nearest_facility_km),1),
                      "cluster": int(row.cluster_id)}
                     for row in candidates.itertuples()]
    clinics = [{"lat": round(float(row.latitude),5), "lng": round(float(row.longitude),5)}
                for row in facility_df.itertuples()]
    map_html = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
    <title>Karnataka | Exploratory Healthcare Access Mapping</title>
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
    <style>*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,sans-serif;background:#f5f7fa;color:#183041}
    header{padding:18px 24px;background:#12263a;color:white}header h1{font-size:22px;margin:0 0 6px}header p{margin:0;color:#cad7e3;max-width:1000px;line-height:1.5}
    #map{height:74vh;min-height:450px}footer{padding:15px 24px;color:#40546b;font-size:13px;line-height:1.6}
    .bubble{background:#2e6485;color:white;border:2px solid #fff;border-radius:999px;width:34px;height:34px;text-align:center;line-height:30px;font-size:12px;font-weight:700;box-shadow:0 2px 5px #0005}
    .stat{font-weight:700;color:#132e4e}a{color:#1e648a}</style></head><body>
    <header><h1>Karnataka Healthcare Access | Screening Map</h1>
    <p>Observed geocoded village points and published PHC/CHC facility locations. Candidate gaps are villages at least 10 km straight-line from a mapped facility. K-Means cluster centers are planning groups, not validated healthcare deserts.</p></header>
    <div id="map" role="application" aria-label="Map of candidate village access gaps"></div>
    <footer><span class="stat" id="numbers"></span> ·
    Gaps reflect only available geocoded villages and mapped facilities, not road travel times, service capacity, or a national shortage designation.
    <div>Sources: <a href="https://github.com/mchittineni/india-village-finder">India Village Finder / LGD</a> and
    <a href="https://github.com/yashveeeeeeer/india-geodata">India Geodata / NIC HealthGIS</a>.
    <a href="../outputs/run_metadata.json">Run metadata</a>.</div></footer>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><script>
    const clusters=__CENTERS__, gaps=__GAPS__, clinics=__CLINICS__;
    const map=L.map('map',{preferCanvas:true}).setView([15.2,76.4],7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
    const candidates=L.layerGroup(gaps.map(p=>L.circleMarker([p.lat,p.lng],{radius:3,color:'#da6643',weight:0,fillOpacity:.65})
      .bindPopup('<b>'+String(p.name).replaceAll('&','&amp;').replaceAll('<','&lt;')+'</b><br>Nearest PHC/CHC: '+p.distance+' km<br>Group '+p.cluster))).addTo(map);
    const facilities=L.layerGroup(clinics.map(p=>L.circleMarker([p.lat,p.lng],{radius:2,color:'#2f946e',weight:0,fillOpacity:.5})));
    const groupCenters=L.layerGroup(clusters.map(p=>L.marker([p.lat,p.lng],{icon:L.divIcon({html:'<div class="bubble">'+p.id+'</div>',className:'',iconSize:[34,34],iconAnchor:[17,17]})})
      .bindPopup('<b>Planning group '+p.id+'</b><br>'+p.count+' flagged villages<br>Mean distance '+p.avg+' km'))).addTo(map);
    L.control.layers({},{"Gap-screened villages":candidates,"PHC/CHC facilities":facilities,"Planning group centers":groupCenters},{collapsed:false}).addTo(map);
    if(gaps.length)map.fitBounds(L.latLngBounds(gaps.map(p=>[p.lat,p.lng])).pad(.07));
    document.getElementById('numbers').textContent=gaps.length.toLocaleString()+' candidate villages · '+clusters.length+' planning clusters · '+clinics.length.toLocaleString()+' PHC/CHC points';
    </script></body></html>"""
    html = map_html.replace("__CENTERS__",json.dumps(centers,ensure_ascii=False)).replace("__GAPS__",json.dumps(candidate_pts,ensure_ascii=False)).replace("__CLINICS__",json.dumps(clinics,ensure_ascii=False))
    DOCS.mkdir(exist_ok=True)
    (DOCS/"index.html").write_text(html,encoding="utf-8")

def main():
    OUTPUT.mkdir(exist_ok=True)
    DATA.mkdir(exist_ok=True)
    villages_bytes = get_data(VILLAGES_URL,"karnataka_villages.csv")
    coords_bytes = get_data(COORDS_URL,"karnataka_coords_master.json")
    facility_bytes = get_data(FACILITIES_URL,"india_facilities_nic.geojson")
    village_df, n_source_rows, n_ungeocoded = parse_villages(villages_bytes,json.loads(coords_bytes))
    facility_df, n_nearby, property_keys = parse_facilities(facility_bytes)
    village_df.to_csv(DATA/"villages_geocoded_karnataka.csv",index=False)
    facility_df.to_csv(DATA/"facilities_phc_chc_karnataka_vicinity.csv",index=False)
    tree = BallTree(np.radians(facility_df[["latitude","longitude"]].values), metric="haversine")
    dist, near_idx = tree.query(np.radians(village_df[["latitude","longitude"]].values),k=1)
    village_df["nearest_facility_km"]=np.round(dist[:,0]*KM_PER_RAD,3)
    village_df["candidate_gap"]=village_df.nearest_facility_km>=THRESHOLD_KM
    candidates=village_df[village_df.candidate_gap].copy()
    if len(candidates)<1:
        raise ValueError("No villages meet chosen screening threshold: record finding, do not manufacture clusters")
    k=min(N_CLUSTERS_REQUESTED,len(candidates))
    lat0=math.radians(candidates.latitude.mean())
    xy=np.column_stack((candidates.longitude*111.32*math.cos(lat0),candidates.latitude*111.32))
    candidates["cluster_id"]=KMeans(n_clusters=k,n_init=10,random_state=42).fit_predict(xy)+1
    summary=candidates.groupby("cluster_id",as_index=False).agg(
        village_count=("village","size"),mean_distance_km=("nearest_facility_km","mean"),
        maximum_distance_km=("nearest_facility_km","max"),
        center_lat=("latitude","mean"),center_lon=("longitude","mean")
    ).sort_values("cluster_id")
    village_df.to_csv(OUTPUT/"village_access_all.csv",index=False)
    candidates.to_csv(OUTPUT/"candidate_gap_villages.csv",index=False)
    summary.to_csv(OUTPUT/"candidate_cluster_summary.csv",index=False)
    geo={"type":"FeatureCollection","features":[
         {"type":"Feature","geometry":{"type":"Point","coordinates":[row.center_lon,row.center_lat]},
          "properties":{"cluster_id":int(row.cluster_id),"village_count":int(row.village_count),
                        "mean_distance_km":round(float(row.mean_distance_km),3)}} for row in summary.itertuples()]}
    (OUTPUT/"candidate_cluster_centers.geojson").write_text(json.dumps(geo,indent=2))
    render_map(village_df,candidates,summary,facility_df)
    meta={
        "run_utc":datetime.now(timezone.utc).isoformat(),
        "geographic_scope":"Karnataka villages with source-matched coordinates; facility lookups include border-adjacent areas",
        "source_village_rows":n_source_rows,
        "source_rows_without_coordinates":n_ungeocoded,
        "analyzed_village_rows":len(village_df),
        "geocoded_village_coverage_fraction":round(len(village_df)/n_source_rows,4),
        "facility_features_in_vicinity":n_nearby,
        "phc_chc_facility_records_analyzed":len(facility_df),
        "facility_property_fields":property_keys,
        "straight_line_distance_threshold_km":THRESHOLD_KM,
        "candidate_gap_villages":len(candidates),
        "requested_kmeans_groups":N_CLUSTERS_REQUESTED,
        "produced_kmeans_groups":k,
        "facility_classification":"PHC/CHC only, inferred from source facility type property",
        "village_source_url":VILLAGES_URL,"coordinates_source_url":COORDS_URL,
        "facility_source_url":FACILITIES_URL,
        "source_sha256":{"villages":hashlib.sha256(villages_bytes).hexdigest(),
                         "coordinates":hashlib.sha256(coords_bytes).hexdigest(),
                         "facilities":hashlib.sha256(facility_bytes).hexdigest()},
        "limitations":"Not evidence of 40 actual healthcare deserts. Selection bias from missing village coordinates, incompleteness/outdatedness of facility records, straight-line not travel distance; source-level population not available."
    }
    (OUTPUT/"run_metadata.json").write_text(json.dumps(meta,indent=2))
    (OUTPUT/"FINDINGS.md").write_text(
        "# Exploratory Karnataka access screening\n\n"
        f"**Geocoded villages examined:** {len(village_df):,} of {n_source_rows:,} village directory records "
        f"({100*len(village_df)/n_source_rows:.1f}% coverage).\n\n"
        f"**Mapped PHC/CHC records within geographic vicinity:** {len(facility_df):,}.\n\n"
        f"**Candidate villages ≥{THRESHOLD_KM:g} km (straight-line) from a mapped PHC/CHC:** {len(candidates):,}.\n\n"
        f"**K-Means planning clusters:** {k} (requested {N_CLUSTERS_REQUESTED}, a modeling choice).\n\n"
        "These figures are an exploratory geographic screening result, **not confirmation of any number of healthcare deserts**. "
        "See run_metadata.json for sources, SHA-256 hashes, geographic scope, and coverage limitations. "
        "Verify candidate sites against road travel time, facility operations, capacity, additional datasets, and community input before citing them as shortage areas.\n"
    )
    print(json.dumps({k:v for k,v in meta.items() if k not in ("source_sha256","facility_property_fields")},indent=2))

if __name__=="__main__":
    main()
