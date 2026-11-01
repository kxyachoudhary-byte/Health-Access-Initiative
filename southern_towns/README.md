# Geographic Clinic Access: 40 Southern Towns

A reproducible geospatial screening tool for **40 incorporated towns** in Alabama, Arkansas, Louisiana, and Mississippi. This is a coding and data-analysis project, not a fundraising landing page.

**[Open the live interactive explorer](https://southern-clinic-access.vercel.app/)** · [CSV results](data/town_access.csv) · [GeoJSON for QGIS](data/town_access.geojson) · [Analysis script](analyze.py) · [Tests](tests/test_analysis.py)

## Research question

How far are geographically sampled Southern towns from the nearest and third-nearest **HRSA Health Center Service Delivery Sites**?

The tool joins Census town representative points to HRSA facility records, computes great-circle distances, and uses deterministic K-means to group towns by relative distance. It is a *screening tool*, not a clinical shortage diagnosis.

## Verified results

| Metric | Value |
| :--- | ---: |
| Towns selected | 40 (10 per state) |
| HRSA site records screened | 3,553 |
| Median distance to nearest listed site | 6.24 miles |
| Longest nearest-site distance in selected sample | 21.44 miles |
| Groups from nearest + third-nearest distance features | 3 |

The results above come from the included output snapshot and may change when official facility data are updated.

## Run the code

Python 3.10 or newer. No third-party packages are needed.

~~~bash
cd southern_towns

# Reproduce K-means from the recorded 40-town measurements without internet:
python analyze.py

# Re-fetch the Census and HRSA public datasets and recompute distances + groups:
python analyze.py --refresh

# Execute no-network checks:
python -m unittest discover -s tests -v
~~~

Output consists of:

- \`data/town_access.csv\`: 40 town records, coordinates, two distance measures, nearest HRSA site, cluster and rank.
- \`data/town_access.geojson\`: QGIS-compatible point features with the measurements and cluster labels.
- \`data/summary.json\`: summary metrics, source URLs, and method description.

## Technical method

1. **Sample**: Use the U.S. Census Bureau places Gazetteer and the \`NAME\` ending in "town" with \`FUNCSTAT=A\`. For each state, sort eligible towns by Census GEOID and select ten evenly spaced positions. This is systematic geographic sampling, not purposive ranking by need.
2. **Acquire facilities**: Query the published HRSA GIS Health Center Service Delivery Sites layer for the four-state region with a buffer. Reject an incomplete or truncated response.
3. **Distance features**: Compute haversine great-circle miles from each Census representative town point to all returned HRSA site coordinates. Retain distances to the nearest and third-nearest.
4. **Cluster**: Standardize both distance features using population standard deviation; apply deterministic Lloyd K-means with \`k=3\`. Label cluster centers "Closer," "Intermediate," and "Farther" in order of their average nearest-site distance.
5. **Export**: Write CSV, GeoJSON and machine-readable summary. Use GeoJSON in QGIS for further visual mapping.

### Important scope

The HRSA layer includes some mobile, school-based, and other special-purpose service-delivery sites. It is not a comprehensive database of all clinics or a guarantee that a given site can provide walk-in primary care. Straight-line distance is not driving time. Clusters reflect relative proximity in the **sample**, not measured individual medical need.

The software is a separate artifact from community fundraising or care-kit distribution. It does not claim that this particular model determined earlier kit placements.

### Data provenance

- U.S. Census Bureau places Gazetteer (2024 data release): https://www.census.gov/geographies/reference-files/2024/geo/gazetter-file.html
- HRSA Health Center Program: https://data.hrsa.gov/topics/health-centers/
- HRSA GIS layer: https://gisportal.hrsa.gov/server/rest/services/HealthCareFacilities/HealthCareFacilities/MapServer/18

The full API query is recorded in [summary.json](data/summary.json).
