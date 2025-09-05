import streamlit as st
import pandas as pd
import googlemaps
import folium
from geopy.distance import geodesic
import json
from streamlit_js_eval import get_geolocation
from streamlit_folium import st_folium

st.set_page_config(page_title="Bridge Height Checker", layout="centered")
gmaps = googlemaps.Client(key=st.secrets["gmapsapi"]) # You would get your API keys from st.secrets


page = st.sidebar.radio("Menu", ["New Obstacle", "Obstacle Lists"])

if page=="New Obstacle":

    selected_method= st.selectbox("Choose location method:", ["Current Location", "Select on Map", "Enter Address or Coordinates"])

    if selected_method == "Current Location":
        location = get_geolocation()
        if location and "coords" in location:
            coords = location["coords"]
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.Marker([lat, lon], popup="Current Location").add_to(m)
            st.components.v1.html(m._repr_html_(), height=300)
        else:
            st.error("Could not get current location. Please allow location access.")

    elif selected_method == "Select on Map":
        location = get_geolocation()
        coords = location["coords"] if location and "coords" in location else {}
        lat = coords.get("latitude")
        lon = coords.get("longitude")
        m = folium.Map(location=[lat,lon], zoom_start=15)
        st.write("Click on the map to select a location.")
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=300, width=700)
        if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
            lat = map_data["last_clicked"]["lat"]
            lon = map_data["last_clicked"]["lng"]
        else:
            lat, lon = None, None

    elif selected_method == "Enter Address or Coordinates":

        address = st.text_input("Enter an address:")

        if address:
            geocode_result = gmaps.geocode(address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lon = location['lat'], location['lng']
                m = folium.Map(location=[lat, lon], zoom_start=15)
                folium.Marker([lat, lon], popup=address).add_to(m)
                st.components.v1.html(m._repr_html_(), height=300)

    col1, col2 = st.columns(2)
    col1.text_input("Enter obstacle name:", key="obstacle_name")
    col2.text_input("Enter obstacle height in meters:", key="obstacle_height")

    if st.button("Save Obstacle Info"):
        obstacle_name = st.session_state.get("obstacle_name", "")
        obstacle_height = st.session_state.get("obstacle_height", "")
        if not obstacle_name or not obstacle_height or not lat or not lon:
            st.error("Please provide all fields and ensure location is set.")
        else:
            try:
                obstacle_height = float(obstacle_height)
                df = pd.DataFrame([{
                    "Obstacle Name": obstacle_name,
                    "Height (m)": obstacle_height,
                    "Latitude": lat,
                    "Longitude": lon
                }])
                csv_path = "bridge_info.csv"
                try:
                    existing = pd.read_csv(csv_path)
                    df = pd.concat([existing, df], ignore_index=True)
                except FileNotFoundError:
                    pass
                df.to_csv(csv_path, index=False)
                st.toast("Obstacle Saved!", icon="✅")
            except ValueError:
                st.error("Height must be a number.")

elif page=="Obstacle Lists":
    csv_path = "bridge_info.csv"
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        st.warning("No obstacles found. Add a new obstacle first.")
        df = pd.DataFrame(columns=["Obstacle Name", "Height (m)", "Latitude", "Longitude"])

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button("Save Changes"):
        edited_df.to_csv(csv_path, index=False)
        st.toast("Changes SAVED!", icon="✅")
