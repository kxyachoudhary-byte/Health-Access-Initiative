# Health Access Initiative | Rural healthcare access mapping

A Python + QGIS workflow for exploring geographic access to primary healthcare in India. It calculates straight-line distance from each village centroid to the nearest healthcare facility, screens for potential geographic access gaps, and groups screened settlements with K-Means for follow-up mapping.

**Research status:** This repository contains analysis code, source references, and a blank input schema. It does not currently contain validated village-level observations, completed study results, or evidence supporting a finding of 40 rural healthcare deserts. Use the pipeline with independently sourced and checked records before making empirical claims.

## Method

1. Obtain village point data and healthcare-facility point data from appropriately licensed sources. Document version, geographic coverage, and collection date.
2. Validate coordinates, facility categories, village identifiers, and data completeness.
3. Calculate nearest-facility great-circle (haversine) distance.
4. Screen candidate access gaps using a user-specified distance threshold. **A geographic threshold is not a clinical designation or a measure of travel time.**
5. Apply K-Means to geographically group the candidate settlements. The number of groups is a modeling parameter, **not the number of independently documented healthcare deserts.**
6. Inspect the CSV and GeoJSON outputs in QGIS and validate candidate gaps against actual road connectivity, facility capacity, and local context.

## Input data format

- `data/villages_TEMPLATE.csv`: `village,district,state,latitude,longitude,population` (one settlement per row, WGS84 decimal degrees).
- `facilities.geojson` (user-supplied): GeoJSON FeatureCollection of point features with a `type` property (e.g., PHC or CHC). Coordinates are **[longitude, latitude]** in EPSG:4326.

The repository does **not** redistribute third-party facility or village data. Refer to [data/SOURCES.md](data/SOURCES.md) for candidate source collections and licensing considerations.

## Run

Requires Python 3.10+:

```bash
python -m pip install -r requirements.txt
python health_access_clusters.py \
  --villages data/villages.csv \
  --facilities data/facilities.geojson \
  --clusters 40 --threshold-km 10 \
  --out outputs
python tests/test_smoke.py
```

Input filenames above are placeholders. Add your verified CSV and GeoJSON files first. The default PHC/CHC facility-type filter can be overridden with `--facility-types` and `--type-field`.

The script writes:
- `outputs/village_access_all.csv`: all villages, nearest-facility distances and screening flag.
- `outputs/candidate_gap_villages.csv`: flagged villages and `cluster_id`.
- `outputs/candidate_cluster_summary.csv`: cluster aggregate statistics.
- `outputs/candidate_cluster_centers.geojson`: QGIS-readable centroids of clustered candidates.
- `outputs/run_metadata.json`: analysis parameters, timestamps and input SHA-256 checksums.

For QGIS Desktop native K-Means, run `qgis_native_kmeans.py` from the QGIS Python Console after the preceding command. It runs the QGIS Processing algorithm on an EPSG:6933 projected layer; labels may differ from those produced by scikit-learn.

## Interpretation and limitations

- `--clusters 40` explicitly requests 40 spatial groups; it does **not** demonstrate 40 observed healthcare deserts.
- `--threshold-km 10` is an analyst-selected screening assumption, not an official shortage definition.
- Haversine distance is straight-line distance, not road distance, typical travel duration, affordability, availability, quality of care or facility capacity.
- Missing or uneven village/facility data can materially bias results. Inspect coverage and source dates.
- Do not infer clinical need from clustering alone. Any published claim should include the input data, provenance, exact methodology, and independent validation.
- The included smoke test uses fictional toy coordinates solely to test code behavior.

## Repository structure

```text
health_access_clusters.py     Main Python analysis
qgis_native_kmeans.py         QGIS Desktop Processing variant
data/villages_TEMPLATE.csv    Blank village schema
data/SOURCES.md               Candidate source links and provenance checks
requirements.txt              Python dependencies
tests/test_smoke.py           Automated self-check with toy records
LICENSE                       Code license
```

MIT licensed.