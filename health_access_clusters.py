#!/usr/bin/env python3
"""Village-to-facility distance screening and exploratory K-Means grouping.

k geographical clusters are NOT k verified healthcare deserts.
"""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.neighbors import BallTree

EARTH_KM = 6371.0088

def run(villages, facilities, out, clusters=40, threshold_km=10):
    required = {"village", "district", "state", "latitude", "longitude"}
    if required - set(villages.columns):
        raise ValueError("Missing village columns: " + str(sorted(required-set(villages.columns))))
    v = villages.copy()
    for c in ["latitude", "longitude"]:
        v[c] = pd.to_numeric(v[c], errors="coerce")
    v = v.dropna(subset=["latitude","longitude"])
    v = v[v.latitude.between(-90,90) & v.longitude.between(-180,180)].copy()
    if v.empty or facilities.empty:
        raise ValueError("Valid village and facility coordinates required")
    if clusters < 1 or threshold_km <= 0:
        raise ValueError("clusters and distance threshold must be positive")
    tree = BallTree(np.radians(facilities[["latitude","longitude"]].to_numpy()), metric="haversine")
    d, idx = tree.query(np.radians(v[["latitude","longitude"]].to_numpy()), k=1)
    v["nearest_facility_km"] = np.round(d[:,0] * EARTH_KM,3)
    v["nearest_facility_type"] = facilities.iloc[idx[:,0]]["facility_type"].to_numpy()
    v["candidate_gap"] = v["nearest_facility_km"] >= threshold_km
    gaps = v.loc[v.candidate_gap].copy()
    if gaps.empty:
        raise ValueError("No settlements reach selected threshold")
    lat0 = np.radians(gaps.latitude.mean())
    xy = np.column_stack([gaps.longitude * 111.32 * np.cos(lat0), gaps.latitude * 111.32])
    k = min(clusters,len(gaps))
    gaps["cluster_id"] = KMeans(n_clusters=k, random_state=42,n_init=10).fit_predict(xy)+1
    summary = gaps.groupby("cluster_id",as_index=False).agg(
        village_count=("village","size"), mean_distance_km=("nearest_facility_km","mean"),
        max_distance_km=("nearest_facility_km","max"),
        center_lat=("latitude","mean"),center_lon=("longitude","mean"))
    out = Path(out); out.mkdir(parents=True,exist_ok=True)
    v.to_csv(out/"village_access_all.csv",index=False)
    gaps.to_csv(out/"candidate_gap_villages.csv",index=False)
    summary.to_csv(out/"candidate_cluster_summary.csv",index=False)
    features=[]
    for r in summary.to_dict("records"):
        features.append({"type":"Feature","geometry":{"type":"Point","coordinates":[r.pop("center_lon"),r.pop("center_lat")]},"properties":r})
    (out/"candidate_cluster_centers.geojson").write_text(json.dumps({"type":"FeatureCollection","features":features},indent=2))
    return {"villages_analyzed":len(v),"candidate_gap_villages":len(gaps),
            "clusters_requested":clusters,"clusters_returned":k,
            "threshold_km_straight_line":threshold_km,
            "interpretation":"Exploratory groupings only; not validated healthcare deserts or travel times."}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--villages",required=True,type=Path)
    p.add_argument("--facilities",required=True,type=Path)
    p.add_argument("--out",type=Path,default=Path("outputs"))
    p.add_argument("--clusters",type=int,default=40)
    p.add_argument("--threshold-km",type=float,default=10)
    p.add_argument("--type-field",default="type")
    p.add_argument("--facility-types",default="PHC,CHC,Primary Health Centre,Community Health Centre")
    args=p.parse_args()
    villages=pd.read_csv(args.villages)
    raw=json.loads(args.facilities.read_text())
    if raw.get("type")!="FeatureCollection":
        raise ValueError("Facilities must be GeoJSON FeatureCollection")
    allowed=[x.strip().lower() for x in args.facility_types.split(",") if x.strip()]
    fac=[]
    for f in raw.get("features",[]):
        g=f.get("geometry") or {}; props=f.get("properties") or {}
        kind=str(props.get(args.type_field,""))
        if g.get("type")!="Point" or (allowed and not any(a in kind.lower() for a in allowed)): continue
        lon,lat=g["coordinates"][:2]
        if -90<=lat<=90 and -180<=lon<=180:
            fac.append({"latitude":lat,"longitude":lon,"facility_type":kind})
    result=run(villages,pd.DataFrame(fac,columns=["latitude","longitude","facility_type"]),args.out,args.clusters,args.threshold_km)
    result["village_sha256"]=hashlib.sha256(args.villages.read_bytes()).hexdigest()
    result["facility_sha256"]=hashlib.sha256(args.facilities.read_bytes()).hexdigest()
    (args.out/"run_metadata.json").write_text(json.dumps(result,indent=2))
    print(json.dumps(result,indent=2))
if __name__=="__main__": main()
