"""Run from QGIS Python Console in the repository directory after running the main pipeline.

This groups candidate geographic access-gap points. k=40 is a chosen parameter,
not confirmation of 40 clinically or operationally underserved regions.
"""
from pathlib import Path
from qgis.core import QgsCoordinateReferenceSystem, QgsVectorLayer
from qgis.PyQt.QtCore import QUrl
import processing

root = Path.cwd()
source = root / "outputs" / "candidate_gap_villages.csv"
assert source.exists(), "Run health_access_clusters.py with validated inputs first"
url = QUrl.fromLocalFile(str(source)).toString()
layer = QgsVectorLayer(f"{url}?type=csv&detectTypes=yes&xField=longitude&yField=latitude&crs=EPSG:4326", "candidate gaps", "delimitedtext")
if not layer.isValid():
    raise RuntimeError("Could not read candidate gaps")
projected = processing.run("native:reprojectlayer", {
    "INPUT":layer, "TARGET_CRS":QgsCoordinateReferenceSystem("EPSG:6933"),"OUTPUT":"memory:"})["OUTPUT"]
clustered = processing.run("native:kmeansclustering", {
    "INPUT":projected,"CLUSTERS":40,"FIELD_NAME":"QGIS_CLUSTER",
    "SIZE_FIELD_NAME":"QGIS_SIZE","OUTPUT":"memory:"})["OUTPUT"]
dest = root / "outputs" / "qgis_native_kmeans_clusters.geojson"
processing.run("native:reprojectlayer", {
    "INPUT":clustered,"TARGET_CRS":QgsCoordinateReferenceSystem("EPSG:4326"),
    "OUTPUT":str(dest)})
print("Saved",dest)
