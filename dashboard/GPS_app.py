"""Interactive GPS footfall dashboard using OpenStreetMap."""

from pathlib import Path

import folium
import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit_analytics2 as streamlit_analytics
from streamlit_folium import st_folium

with streamlit_analytics.track():
    st.text_input("Write something")
    st.button("Click me")


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_PATH = PROJECT_ROOT / "output_file" / "trajectories_footfall_Stuck_husseim.parquet"
REQUIRED_COLUMNS = {"user", "timestamp", "lat", "lng", "speed", "footfall"}
MODE_COLOURS = {
    "Stationary": "#64748b",
    "Walking": "#16a34a",
    "Bicycle": "#2563eb",
    "Car / faster": "#dc2626",
    "Invalid / unknown": "#9ca3af",
}


@st.cache_data(show_spinner="Loading GPS observations…")
def load_data(data_path_text: str) -> pd.DataFrame:
    """Load the Parquet output and retain only valid map coordinates."""
    data_path = Path(data_path_text).expanduser()
    if not data_path.is_file():
        raise FileNotFoundError(f"File not found: {data_path}")
    data = pd.read_parquet(data_path)
    missing = REQUIRED_COLUMNS.difference(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    data = data.copy()
    data["speed"] = pd.to_numeric(data["speed"], errors="coerce")
    data["timestamp_dt"] = pd.to_datetime(data["timestamp"], unit="s", utc=True, errors="coerce")
    data = data.dropna(subset=["lat", "lng", "timestamp_dt"])
    data = data[data["lat"].between(-90, 90) & data["lng"].between(-180, 180)]
    return data.sort_values(["user", "timestamp_dt"])


def classify_speed(data: pd.DataFrame, stationary_limit: float, walking_limit: float, bicycle_limit: float) -> pd.DataFrame:
    """Create display-only transport groups from the reported speed in m/s."""
    result = data.copy()
    result["speed_group"] = "Invalid / unknown"
    valid = result["speed"].ge(0)
    result.loc[valid & result["speed"].le(stationary_limit), "speed_group"] = "Stationary"
    result.loc[result["speed"].gt(stationary_limit) & result["speed"].le(walking_limit), "speed_group"] = "Walking"
    result.loc[result["speed"].gt(walking_limit) & result["speed"].le(bicycle_limit), "speed_group"] = "Bicycle"
    result.loc[result["speed"].gt(bicycle_limit), "speed_group"] = "Car / faster"
    return result


def speed_mode(speed: float, stationary_limit: float, walking_limit: float, bicycle_limit: float) -> tuple[str, str, float]:
    """Return a label, icon, and animation duration for the chosen speed."""
    if speed <= stationary_limit:
        return "Stationary", "●", 0.0
    if speed <= walking_limit:
        return "Walking", "🚶", 2.0
    if speed <= bicycle_limit:
        return "Bicycle", "🚲", 1.1
    return "Car / faster", "🚗", 0.55


def movement_indicator(label: str, icon: str, duration: float) -> None:
    """Show a deliberately small movement indicator linked to the speed choice."""
    animation = "none" if duration == 0 else f"gps-move {duration}s ease-in-out infinite"
    st.markdown(
        f"""
        <style>
        .speed-indicator {{display:flex;align-items:center;gap:.8rem;margin:.15rem 0 .8rem}}
        .speed-track {{width:130px;height:28px;background:#e5e7eb;border-radius:18px;overflow:hidden;position:relative}}
        .speed-icon {{position:absolute;top:1px;left:8px;font-size:21px;animation:{animation}}}
        @keyframes gps-move {{0% {{transform:translateX(0)}} 50% {{transform:translateX(90px)}} 100% {{transform:translateX(0)}}}}
        </style>
        <div class="speed-indicator" aria-label="{label} speed indicator">
          <div class="speed-track"><span class="speed-icon">{icon}</span></div><strong>{label}</strong>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_map(data: pd.DataFrame, show_routes: bool) -> folium.Map:
    """Build a map of the filtered observations over OpenStreetMap tiles."""
    map_view = folium.Map(location=[data["lat"].mean(), data["lng"].mean()], zoom_start=13, control_scale=True, tiles=None)
    folium.TileLayer(
        tiles="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        attr="© OpenStreetMap contributors",
        name="OpenStreetMap",
    ).add_to(map_view)

    if show_routes:
        routes = folium.FeatureGroup(name="Visible user routes", show=True)
        for user, route in data.sort_values("timestamp_dt").groupby("user"):
            if len(route) > 1:
                folium.PolyLine(
                    route[["lat", "lng"]].values.tolist(),
                    color="#475569",
                    weight=2,
                    opacity=0.45,
                    tooltip=f"Route: {user}",
                ).add_to(routes)
        routes.add_to(map_view)

    for group, points in data.groupby("speed_group", sort=False):
        layer = folium.FeatureGroup(name=group, show=True)
        colour = MODE_COLOURS[group]
        for row in points.itertuples():
            speed_text = "invalid" if pd.isna(row.speed) or row.speed < 0 else f"{row.speed:.2f} m/s"
            popup = (
                f"<b>User:</b> {row.user}<br><b>Time (UTC):</b> {row.timestamp_dt:%Y-%m-%d %H:%M:%S}<br>"
                f"<b>Speed:</b> {speed_text}<br><b>Speed group:</b> {row.speed_group}<br><b>Footfall:</b> {int(row.footfall)}"
            )
            folium.CircleMarker(
                [row.lat, row.lng],
                radius=4,
                color=colour,
                fill=True,
                fill_color=colour,
                fill_opacity=0.82,
                weight=1,
                popup=folium.Popup(popup, max_width=300),
            ).add_to(layer)
        layer.add_to(map_view)

    folium.LayerControl(collapsed=False).add_to(map_view)
    return map_view


st.set_page_config(page_title="Potsdam Footfall Explorer", page_icon="🗺️", layout="wide")
st.title("Potsdam footfall explorer")
st.caption("Use the speed slider to explore where stationary, walking, bicycle, and faster observations occur.")

try:
    raw_data = load_data(str(DEFAULT_DATA_PATH))
except (FileNotFoundError, ValueError, ImportError) as error:
    st.error(f"The dashboard could not load its data: {error}")
    st.stop()

with st.sidebar:
    st.header("Map filters")
    stationary_limit = st.slider("Stationary maximum (m/s)", 0.0, 1.0, 0.3, 0.1)
    walking_limit = st.slider("Walking maximum (m/s)", stationary_limit + 0.1, 3.0, 1.9, 0.1)
    bicycle_limit = st.slider("Bicycle maximum (m/s)", walking_limit + 0.1, 15.0, 7.0, 0.1)

data = classify_speed(raw_data, stationary_limit, walking_limit, bicycle_limit)
valid_speed_series = data.loc[data["speed"] >= 0, "speed"]
valid_speed_max = 15.0 if valid_speed_series.empty else max(15.0, float(valid_speed_series.max()))

st.subheader("Choose a speed")
speed_focus = st.slider("Speed (m/s)", 0.0, valid_speed_max, 1.0, 0.1, help="Move this slider to focus the map and statistics on a speed band.")
speed_band = st.slider("Speed band (± m/s)", 0.05, 3.0, 0.30, 0.05)
focus_label, focus_icon, focus_duration = speed_mode(speed_focus, stationary_limit, walking_limit, bicycle_limit)
movement_indicator(focus_label, focus_icon, focus_duration)
st.caption(f"Showing valid observations from **{max(0, speed_focus - speed_band):.2f}** to **{speed_focus + speed_band:.2f} m/s**.")

with st.sidebar:
    users = sorted(data["user"].astype(str).unique())
    selected_users = st.multiselect("Users", users, default=users)
    show_routes = st.toggle("Show visible user routes", value=True)
    footfall_filter = st.radio("Footfall label", ["All", "Foot traffic (1)", "Not foot traffic (0)"])
    min_time, max_time = data["timestamp_dt"].min(), data["timestamp_dt"].max()
    time_range = st.slider(
        "Time range (UTC)",
        min_value=min_time.to_pydatetime(),
        max_value=max_time.to_pydatetime(),
        value=(min_time.to_pydatetime(), max_time.to_pydatetime()),
        format="YYYY-MM-DD HH:mm",
    )

start_time, end_time = (pd.Timestamp(item) for item in time_range)
filtered = data[
    data["user"].astype(str).isin(selected_users)
    & data["timestamp_dt"].between(start_time, end_time)
    & data["speed"].between(max(0, speed_focus - speed_band), speed_focus + speed_band)
].copy()

if footfall_filter == "Foot traffic (1)":
    filtered = filtered[filtered["footfall"] == 1]
elif footfall_filter == "Not foot traffic (0)":
    filtered = filtered[filtered["footfall"] == 0]

if filtered.empty:
    st.warning("No valid-speed observations match this selection. Increase the speed band or change the filters.")
    st.stop()

metric_a, metric_b, metric_c, metric_d = st.columns(4)
metric_a.metric("Matching points", f"{len(filtered):,}")
metric_b.metric("Users represented", filtered["user"].nunique())
metric_c.metric("Foot traffic share", f"{(filtered['footfall'] == 1).mean():.1%}")
metric_d.metric("Mean speed", f"{filtered['speed'].mean():.2f} m/s")

st.subheader("Map")
st.caption("Gray = stationary, green = walking, blue = bicycle, red = car/faster. Click a point for details.")
st_folium(build_map(filtered, show_routes), height=620, width=None, returned_objects=[])

chart_left, chart_right = st.columns(2)
with chart_left:
    st.subheader("Matching speed distribution")
    speed_chart = px.histogram(filtered, x="speed", color="speed_group", nbins=25, color_discrete_map=MODE_COLOURS)
    speed_chart.update_layout(xaxis_title="Reported speed (m/s)", yaxis_title="GPS observations", legend_title="Speed group")
    st.plotly_chart(speed_chart, width="stretch")
with chart_right:
    st.subheader("Matching observations by user")
    counts = filtered.groupby(["user", "speed_group"]).size().reset_index(name="observations")
    user_chart = px.bar(counts, x="user", y="observations", color="speed_group", barmode="stack", color_discrete_map=MODE_COLOURS)
    user_chart.update_layout(xaxis_title="User", yaxis_title="GPS observations", legend_title="Speed group")
    st.plotly_chart(user_chart, width="stretch")

st.download_button(
    "Download matching observations as CSV",
    data=filtered.drop(columns=["timestamp_dt"]).to_csv(index=False).encode("utf-8"),
    file_name="gps_speed_selection.csv",
    mime="text/csv",
)
