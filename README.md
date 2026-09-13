# GPS Footfall Interactive Dashboard

Interactive Streamlit dashboard for exploring the supplied GPS-footfall output on OpenStreetMap.

## Publish with Streamlit Community Cloud

1. Push this repository to GitHub.
2. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app from the repository.
3. Set the main file path to `dashboard copy/GPS_app.py`.
4. Deploy. The root `requirements.txt` supplies the required Python packages.

The Parquet data file is committed inside `output_file/`, so the deployed app uses a repository-relative path and does not depend on your local computer.
