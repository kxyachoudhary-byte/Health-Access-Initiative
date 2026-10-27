"""Smoke test for the analysis pipeline. Toy inputs are fictional test fixtures."""
import json, tempfile
from pathlib import Path
import pandas as pd
from health_access_clusters import run
with tempfile.TemporaryDirectory() as d:
    root=Path(d)
    v=pd.DataFrame([
       {"village":"toy_A","district":"TEST","state":"TEST","latitude":18.0,"longitude":75.3},
       {"village":"toy_B","district":"TEST","state":"TEST","latitude":18.3,"longitude":75.0},
       {"village":"toy_C","district":"TEST","state":"TEST","latitude":18.0,"longitude":75.01}])
    f=pd.DataFrame([{"latitude":18.0,"longitude":75.0,"facility_type":"PHC"}])
    result=run(v,f,root/"output",clusters=2,threshold_km=10)
    assert result["candidate_gap_villages"]==2, result
    assert result["clusters_returned"]==2, result
    assert (root/"output/candidate_cluster_centers.geojson").exists()
    assert len(json.loads((root/"output/candidate_cluster_centers.geojson").read_text())["features"])==2
    print("PASS: toy pipeline smoke test")
