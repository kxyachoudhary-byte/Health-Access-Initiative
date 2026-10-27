# Dataset provenance and limitations

This project does not invent village or healthcare-facility observations. It regenerates selected observed inputs and derived outputs directly from cited public third-party sources.

## Source 1: Karnataka administrative village directory

- **Upstream project:** [mchittineni/india-village-finder](https://github.com/mchittineni/india-village-finder).
- **Village names and official directory codes:** [karnataka_villages.csv](https://github.com/mchittineni/india-village-finder/blob/main/karnataka/data/karnataka_villages.csv).
- **Matched location coordinates:** [coords_master.json](https://github.com/mchittineni/india-village-finder/blob/main/karnataka/data/coords_master.json).
- **Government origin of directory:** Government of India Local Government Directory (LGD), per the upstream project's source notes; village geocodes come from upstream geocoding sources and are not universally validated against official village polygon centroids.
- **Documented release:** [v1.5.18, 20 September 2026 LGD snapshot](https://github.com/mchittineni/india-village-finder/releases/tag/v1.5.18). The analysis fetches the *main branch* files and stores SHA-256 checksums to identify exact downloaded versions.
- **License:** Government data attribution per the upstream [DATA_LICENSE.md](https://github.com/mchittineni/india-village-finder/blob/main/DATA_LICENSE.md) and original provider conditions.
- **Coverage warning:** 30,753 directory entries, 5,109 usable geocoded rural village records (16.6%) in this pipeline. Missing coordinate rows are not silently imputed.

## Source 2: PHC/CHC facility records

- **Upstream project:** [yashveeeeeeer/india-geodata](https://github.com/yashveeeeeeer/india-geodata).
- **Data description:** [healthcare/facilities README](https://github.com/yashveeeeeeer/india-geodata/blob/main/data/healthcare/facilities/README.md) and [metadata](https://github.com/yashveeeeeeer/india-geodata/blob/main/data/healthcare/facilities/metadata.json).
- **Release file:** [INDIA_HEALTH_FACILITIES_NIC.geojson](https://github.com/yashveeeeeeer/india-geodata/releases/tag/healthcare%2Ffacilities).
- **Reported originating source:** National Informatics Centre (NIC) HealthGIS, India.
- **Temporal documentation:** Metadata lists 2023 geographic source coverage and a 2026 release/update date.
- **Source license per publishing aggregator:** India Open Government License, subject to original-source requirements. Review upstream documentation before onward commercial use.
- **Selection:** GeoJSON point geometries within a bounding box covering Karnataka and nearby cross-border locations, with a facility `type` matching PHC or CHC. Selected coordinates (without individual names) are recorded in [facilities_phc_chc_karnataka_vicinity.csv](facilities_phc_chc_karnataka_vicinity.csv) for auditability.

## Derived processing

The script [run_observed_karnataka.py](../run_observed_karnataka.py) downloads the two sources, joins village codes to location coordinates, computes shortest great-circle distances to mapped PHC/CHC sites, flags villages at or above 10 km, and applies K-Means to those candidates with `k = min(40, candidate_count)`.

The 10-km rule and `k = 40` were analyst-defined for **screening and visualization**, not established by a medical authority. The study does not estimate road travel time, service capacity, clinical availability, patient costs, shortage designations, or total affected population. No conclusion about precisely 40 actual health deserts is supported by the clustering alone.

## Reproducibility

See [run_metadata.json](../outputs/run_metadata.json) for source SHA-256 checksums, run date, source-field names, candidate selection counts, and the exact parameters. Consult [FINDINGS.md](../outputs/FINDINGS.md) for the numeric results. The repository code is distinct from third-party data; do not conflate the repository's MIT code license with data re-use permissions.
