"""Interactive GPS trajectory explorer for the foot-traffic assignment."""

from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_folium import st_folium


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "2_Output_Files" / "trajectories_footfall_Stuck_husseim.parquet"
REQUIRED_COLUMNS = {"user", "timestamp", "lat", "lng", "speed", "footfall"}


@st.cache_data(show_spinner="Loading trajectory data…")
def load_data(path_as_text: str) -> pd.DataFrame:
    """Load and validate the assignment output without modifying it."""
    data_path = Path(path_as_text).expanduser()
    if not data_path.is_file():
        raise FileNotFoundError(f"No Parquet file was found at: {data_path}")

    data = pd.read_parquet(data_path)
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"The Parquet file is missing: {', '.join(sorted(missing))}")

    data = data.copy()
    data["timestamp_dt"] = pd.to_datetime(data["timestamp"], unit="s", utc=True, errors="coerce")
    data["speed"] = pd.to_numeric(data["speed"], errors="coerce")
    data = data.dropna(subset=["lat", "lng", "timestamp_dt"])
    data = data[data["lat"].between(-90, 90) & data["lng"].between(-180, 180)]
    return data.sort_values(["user", "timestamp_dt"])


def assign_mode(data: pd.DataFrame, walk_limit: float, cycle_limit: float) -> pd.DataFrame:
    """Create display-only mode groups from the reported speed in m/s."""
    result = data.copy()
    result["mode"] = "Unknown / invalid"
    valid_speed = result["speed"].ge(0)
    result.loc[valid_speed & result["speed"].le(walk_limit), "mode"] = "Walking / stationary"
    result.loc[
        result["speed"].gt(walk_limit) & result["speed"].le(cycle_limit), "mode"
    ] = "Bicycle-like"
    result.loc[result["speed"].gt(cycle_limit), "mode"] = "Car / faster"
    return result


MODE_COLOURS = {
    "Walking / stationary": "#16a34a",
    "Bicycle-like": "#2563eb",
    "Car / faster": "#dc2626",
    "Unknown / invalid": "#6b7280",
}


def build_map(data: pd.DataFrame, show_routes: bool) -> folium.Map:
    """Render points and optional trajectories over OpenStreetMap tiles."""
    center = [data["lat"].mean(), data["lng"].mean()]
    map_view = folium.Map(location=center, zoom_start=13, control_scale=True, tiles=None)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap",
    ).add_to(map_view)

    if show_routes:
        route_layer = folium.FeatureGroup(name="User trajectories", show=True)
        for user, route in data.sort_values("timestamp_dt").groupby("user"):
            if len(route) > 1:
                folium.PolyLine(
                    route[["lat", "lng"]].values.tolist(),
                    color="#475569",
                    weight=2,
                    opacity=0.45,
                    tooltip=f"Trajectory: {user}",
                ).add_to(route_layer)
        route_layer.add_to(map_view)

    for mode, points in data.groupby("mode", sort=False):
        point_layer = folium.FeatureGroup(name=mode, show=True)
        colour = MODE_COLOURS[mode]
        for row in points.itertuples():
            speed_label = "invalid" if pd.isna(row.speed) or row.speed < 0 else f"{row.speed:.2f} m/s"
            popup = (
                f"<b>User:</b> {row.user}<br>"
                f"<b>Time (UTC):</b> {row.timestamp_dt:%Y-%m-%d %H:%M:%S}<br>"
                f"<b>Reported speed:</b> {speed_label}<br>"
                f"<b>Speed group:</b> {row.mode}<br>"
                f"<b>Assignment footfall:</b> {int(row.footfall)}"
            )
            folium.CircleMarker(
                location=[row.lat, row.lng],
                radius=4,
                color=colour,
                fill=True,
                fill_color=colour,
                fill_opacity=0.8,
                weight=1,
                popup=folium.Popup(popup, max_width=300),
            ).add_to(point_layer)
        point_layer.add_to(map_view)

    folium.LayerControl(collapsed=False).add_to(map_view)
    return map_view


st.set_page_config(page_title="Potsdam GPS Explorer", page_icon="🗺️", layout="wide")
st.title("Potsdam GPS trajectory explorer")
st.caption("Explore footfall labels, speed-based travel groups, and individual GPS trajectories on OpenStreetMap.")

with st.sidebar:
    st.header("Data and filters")
    data_path = st.text_input("Parquet file", value=str(DEFAULT_DATA_PATH))
    st.caption("The default points to the assignment output file.")
    walking_limit = st.slider("Walking maximum (m/s)", 0.5, 3.0, 1.9, 0.1)
    bicycle_limit = st.slider("Bicycle maximum (m/s)", walking_limit + 0.1, 15.0, 7.0, 0.1)
    show_routes = st.toggle("Show user trajectories", value=True)

try:
    raw_data = load_data(data_path)
except (FileNotFoundError, ValueError, ImportError) as error:
    st.error(f"Unable to load the data: {error}")
    st.info("Install the packages in requirements.txt, then check the Parquet path in the sidebar.")
    st.stop()

data = assign_mode(raw_data, walking_limit, bicycle_limit)
available_users = sorted(data["user"].astype(str).unique())

with st.sidebar:
    selected_users = st.multiselect("Users", available_users, default=available_users)
    selected_modes = st.multiselect(
        "Show speed groups",
        list(MODE_COLOURS),
        default=list(MODE_COLOURS),
        help="Use this control to show only walking, bicycle-like, or car/faster observations.",
    )
    footfall_choice = st.radio("Assignment footfall label", ["All", "Foot traffic (1)", "Not foot traffic (0)"])
    min_time, max_time = data["timestamp_dt"].min(), data["timestamp_dt"].max()
    selected_time = st.slider(
        "Time range (UTC)", min_value=min_time.to_pydatetime(), max_value=max_time.to_pydatetime(),
        value=(min_time.to_pydatetime(), max_time.to_pydatetime()), format="YYYY-MM-DD HH:mm",
    )

filtered = data[
    data["user"].astype(str).isin(selected_users)
    & data["mode"].isin(selected_modes)
    & data["timestamp_dt"].between(pd.Timestamp(selected_time[0]), pd.Timestamp(selected_time[1]))
].copy()
if footfall_choice == "Foot traffic (1)":
    filtered = filtered[filtered["footfall"] == 1]
elif footfall_choice == "Not foot traffic (0)":
    filtered = filtered[filtered["footfall"] == 0]

if filtered.empty:
    st.warning("No observations match the current filters. Adjust a filter to display the map.")
    st.stop()

metric_a, metric_b, metric_c, metric_d = st.columns(4)
metric_a.metric("Visible observations", f"{len(filtered):,}")
metric_b.metric("Visible users", filtered["user"].nunique())
metric_c.metric("Foot traffic labels", f"{(filtered['footfall'] == 1).mean():.1%}")
metric_d.metric("Median reported speed", f"{filtered.loc[filtered['speed'] >= 0, 'speed'].median():.2f} m/s")

st.subheader("Map")
st.caption("Green = walking/stationary, blue = bicycle-like, red = car/faster, gray = invalid or unavailable speed. Click a point for details.")
st_folium(build_map(filtered, show_routes), height=620, use_container_width=True, returned_objects=[])

left_chart, right_chart = st.columns(2)
with left_chart:
    st.subheader("Speed distribution")
    speed_data = filtered[filtered["speed"] >= 0]
    if speed_data.empty:
        st.info("No valid reported speeds are available for this selection.")
    else:
        chart = px.histogram(speed_data, x="speed", color="mode", nbins=35, color_discrete_map=MODE_COLOURS)
        chart.update_layout(xaxis_title="Reported speed (m/s)", yaxis_title="GPS observations", legend_title="Speed group")
        st.plotly_chart(chart, use_container_width=True)
with right_chart:
    st.subheader("Observations by user and mode")
    counts = filtered.groupby(["user", "mode"]).size().reset_index(name="observations")
    chart = px.bar(counts, x="user", y="observations", color="mode", barmode="stack", color_discrete_map=MODE_COLOURS)
    chart.update_layout(xaxis_title="User", yaxis_title="GPS observations", legend_title="Speed group")
    st.plotly_chart(chart, use_container_width=True)

with st.expander("Data quality and interpretation", expanded=False):
    invalid_speeds = (filtered["speed"] < 0).sum()
    st.write(f"{invalid_speeds:,} visible observations have a negative reported speed and are shown as unknown/invalid.")
    st.write(
        "Speed groups are exploratory visual categories based on the reported `speed` field. "
        "They are not ground-truth transport modes and are separate from the assignment's `footfall` classification."
    )

download = filtered.drop(columns=["timestamp_dt"]).to_csv(index=False).encode("utf-8")
st.download_button("Download filtered observations as CSV", data=download, file_name="filtered_gps_observations.csv", mime="text/csv")
