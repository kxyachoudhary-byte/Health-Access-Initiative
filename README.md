# Health Access Initiative

**Open, reproducible analysis of rural healthcare access in Karnataka, India.**

This repository combines a published village directory with independently geocoded village locations and an external public health-facility dataset to screen for geographic gaps in access to primary and community health centres (PHCs/CHCs). It includes Python and QGIS scripts, the selected observed records, derived CSV and GeoJSON outputs, source checksums, an automated regeneration workflow, and an interactive map.

## Observed-data screening (26–27 October 2026)

| Metric | Result |
| --- | ---: |
| Karnataka village directory entries | 30,753 |
| Villages with matched geocoordinates, analyzed | **5,109 (16.6%)** |
| PHC/CHC records in Karnataka and border-adjacent vicinity | **4,148** |
| Villages ≥ 10 km (great-circle distance) from a mapped PHC/CHC | **85** |
| K-Means planning groups of those candidate villages | **40, chosen as a model parameter** |

**These are candidate access gaps, not 40 verified rural healthcare deserts.** The sampling coverage is only 16.6% and it is not possible to infer the true state-wide or India-wide number of underserved areas from the result. The 10-km threshold is analyst-selected; geographic straight-line distance is not actual travel time, road access, clinical quality, patient costs, clinic staffing, or facility capacity.

## Explore outputs

- [Analysis results](outputs/FINDINGS.md) | [run metadata and source SHA-256 hashes](outputs/run_metadata.json)
- [Village-level screening results (CSV)](outputs/village_access_all.csv)
- [85 candidate gap villages (CSV)](outputs/candidate_gap_villages.csv)
- [40 candidate planning groups (CSV)](outputs/candidate_cluster_summary.csv)
- [Cluster centers (QGIS-compatible GeoJSON)](outputs/candidate_cluster_centers.geojson)
- [Selected geocoded villages (CSV)](data/villages_geocoded_karnataka.csv)
- [Selected PHC/CHC facility positions (CSV)](data/facilities_phc_chc_karnataka_vicinity.csv)
- [Interactive Leaflet map (HTML)](docs/index.html) — download the file to open it directly in a browser; it can also be hosted using GitHub Pages if configured
- [Detailed data provenance](data/SOURCES.md)

## Reproduce the analysis

Requires Python 3.10+ and network access to fetch the original source datasets.

```bash
python -m pip install -r requirements.txt
python run_observed_karnataka.py
```

The script downloads source files and recomputes the village-to-facility great-circle distances, candidate selection, K-Means group labels, CSVs, GeoJSON, SHA-256 provenance, and interactive map. The GitHub Actions [workflow](.github/workflows/rebuild_real_data.yml) runs this automatically when its code changes or when started manually.

Other scripts:
- [health_access_clusters.py](health_access_clusters.py): reusable distance screening and K-Means pipeline for independently supplied village CSV and facility GeoJSON.
- [qgis_native_kmeans.py](qgis_native_kmeans.py): QGIS Desktop Processing equivalent on generated candidate village coordinates.
- [Smoke test](tests/test_smoke.py): fictional small inputs used only to verify script functionality. Test data are not empirical findings.

## Data sources

1. Village directory and geocoded location matching: [India Village Finder](https://github.com/mchittineni/india-village-finder), government LGD-based directory, with coordinate coverage limitations. Downloads: [Karnataka village CSV](https://github.com/mchittineni/india-village-finder/blob/main/karnataka/data/karnataka_villages.csv) and [coordinate source](https://github.com/mchittineni/india-village-finder/blob/main/karnataka/data/coords_master.json).
2. PHC/CHC facility coordinates: [India Geodata public healthcare dataset](https://github.com/yashveeeeeeer/india-geodata/blob/main/data/healthcare/facilities/README.md), compiled from NIC HealthGIS; dataset's recorded provenance period is 2023 and its release was published in 2026. [Source release](https://github.com/yashveeeeeeer/india-geodata/releases/tag/healthcare%2Ffacilities).

Source licenses and attribution requirements are independent of this repository's code license. See [data/SOURCES.md](data/SOURCES.md). Source checksums in [run metadata](outputs/run_metadata.json) help identify exactly which downloaded files were processed.

## Important scope limitations

- The output is **Karnataka-only**, covering the 5,109 source villages with geocoded points, not all India or all Karnataka villages.
- Some 2023-era facility records may not reflect current operation, availability, or location accuracy.
- PHC/CHC records from surrounding areas are included to avoid falsely inflating distances near state borders.
- The analysis does not use population weights, travel networks, facility capacity, or verified healthcare need.
- The requested count of **40 K-Means groups** is not a validated count of access-deprived regions. Independent field and official administrative validation would be required before calling an area a healthcare desert.

Code: MIT License. Third-party data: attributed to their respective providers under their applicable licenses.
