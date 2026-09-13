# Potsdam GPS footfall explorer

An interactive Streamlit map for the GPS-footfall assignment output. A speed slider selects a focused speed band and updates the OpenStreetMap points, routes, statistics, charts, and a compact movement indicator together.

## Speed groups

The dashboard uses adjustable exploratory thresholds: stationary (0–0.3 m/s), walking (>0.3–1.9 m/s), bicycle (>1.9–7.0 m/s), and car/faster (>7.0 m/s). These are speed heuristics, not verified transport-mode labels.

## Run locally

From this folder:

```bash
python -m pip install -r requirements.txt
python -m streamlit run GPS_app.py
```

The app reads the repository-relative file `../output_file/trajectories_footfall_Stuck_husseim.parquet copy` and expects `user`, `timestamp`, `lat`, `lng`, `speed`, and `footfall` columns.
