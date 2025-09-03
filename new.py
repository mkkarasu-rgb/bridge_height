import streamlit as st
import pandas as pd
import googlemaps
import folium
from geopy.distance import geodesic
import json

# import gspread # To read data from Google Sheets

# You would get your API keys from st.secrets
gmaps = googlemaps.Client(key=st.secrets('gmapsapi'))

# Get device location using Streamlit's experimental geolocation feature
location_data = st.query_params.get("geolocation")
if location_data:
    try:
        device_location = json.loads(location_data[0])
        st.info(f"Device location: {device_location['latitude']}, {device_location['longitude']}")
    except Exception:
        device_location = st.error("Could not parse device location")
else:
    device_location = st.error("Device location not available")


st.set_page_config(page_title="Bridge Height Checker", layout="centered")

address = st.text_input("Enter an address:")

if address:
    geocode_result = gmaps.geocode(address)
    if geocode_result:
        location = geocode_result[0]['geometry']['location']
        lat, lng = location['lat'], location['lng']

        st.success(f"Location found: {lat}, {lng}")

        m = folium.Map(location=[lat, lng], zoom_start=16)
        folium.Marker([lat, lng], popup=address).add_to(m)
        st.components.v1.html(m._repr_html_(), height=500)

        bridge_height = st.number_input("Enter bridge height (meters):", min_value=0.0, step=0.1)

        if bridge_height:
            if st.button("Save Bridge Info"):
                bridge_info = {
                    "name": address,
                    "latitude": lat,
                    "longitude": lng,
                    "height": bridge_height
                }
                # Save bridge_info to a CSV file
                df = pd.DataFrame([bridge_info])
                csv_file = "bridge_info.csv"
                try:
                    # If file exists, append without header
                    df.to_csv(csv_file, mode='a', header=not pd.io.common.file_exists(csv_file), index=False)
                except Exception as e:
                    st.error(f"Error saving to CSV: {e}")
                else:
                    st.success("Bridge info saved")
                # You can add code here to save bridge_info to a file or database
    else:
        st.error("Address not found. Please try again.")
    
# Load existing bridge data from CSV
try:
    bridge_data = pd.read_csv("bridge_info.csv")
    st.dataframe(bridge_data)
except FileNotFoundError:
    bridge_data = pd.DataFrame(columns=["name", "latitude", "longitude", "height"])
