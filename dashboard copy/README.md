# Potsdam GPS trajectory explorer

An interactive Streamlit dashboard for the assignment output. It displays the supplied GPS observations on an OpenStreetMap basemap and lets you filter users, time, assignment footfall labels, and speed-based travel groups.

## Included views

- Interactive OpenStreetMap with observation popups and optional per-user routes
- Adjustable speed categories: walking/stationary, bicycle-like, car/faster, and invalid/unknown
- User, time-range, and `footfall` filters
- Speed distribution and mode-by-user charts
- Filtered-data CSV download

The transport-mode groups are exploratory speed heuristics, not verified labels. Their defaults are walking/stationary at 0–1.9 m/s, bicycle-like at >1.9–7.0 m/s, and car/faster above 7.0 m/s. Adjust these values in the sidebar to explore alternative assumptions.

## Run locally

From this `dashboard` directory:

```bash
python -m pip install -r requirements.txt
streamlit run app.py
```

The app defaults to `../2_Output_Files/trajectories_footfall_Stuck_husseim.parquet`. Use the sidebar input to select a different compatible Parquet file. It expects `user`, `timestamp`, `lat`, `lng`, `speed`, and `footfall` columns.
