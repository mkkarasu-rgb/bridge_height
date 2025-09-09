import streamlit as st
import pandas as pd
import googlemaps
import folium
from geopy.distance import geodesic
import json
from streamlit_js_eval import get_geolocation
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials

# Google Sheets setup
SHEET_NAME = "obstacles"          # Name of your Google Sheet 
WORKSHEET_NAME = "bridge_info"    # Name of your worksheet within the Google Sheet

# Authenticate using service account credentials from st.secrets
scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds_dict = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
gc = gspread.authorize(creds)

def get_worksheet():
    sh = gc.open(SHEET_NAME)  # Just open the existing sheet; don't try to create
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="4")
        ws.append_row(["Obstacle Name", "Height (m)", "Latitude", "Longitude"])
    return ws

def read_obstacles():
    ws = get_worksheet()
    data = ws.get_all_records()
    return pd.DataFrame(data)

def save_obstacle(obstacle_name, obstacle_height, lat, lon):
    ws = get_worksheet()
    ws.append_row([obstacle_name, obstacle_height, lat, lon])

def save_all_obstacles(df):
    ws = get_worksheet()
    ws.clear()
    ws.append_row(["Obstacle Name", "Height (m)", "Latitude", "Longitude"])
    for _, row in df.iterrows():
        ws.append_row([row["Obstacle Name"], row["Height (m)"], row["Latitude"], row["Longitude"]])


# You would get your API keys from st.secrets
gmaps = googlemaps.Client(key='AIzaSyCw6dw7UN52WgKsXZO3Cevx_ymoa8PPd2w')

st.set_page_config(page_title="Bridge Height Checker", layout="centered", page_icon="🚛")
# gmaps = googlemaps.Client(key=st.secrets["gmapsapi"]) # You would get your API keys from st.secrets

# Authentication
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("Login to Bridge Height Checker")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    if st.button("Login"):
        if username == "nst" and password == "nst":
        # if username == st.secrets["username"] and password == st.secrets["password"]:            
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Invalid credentials")
    st.stop()

page = "New Obstacle"

page = st.selectbox(
    "MENU:",
    ["New Obstacle", "Obstacle Lists", "Route Planner"],
    index=["New Obstacle", "Obstacle Lists", "Route Planner"].index(page),
    key="main_menu"
)

if page == "New Obstacle":

    with st.expander("Add new obstacle", expanded=True):

        address = st.text_input("Enter an address:", placeholder="If left blank, your current location is used")
        col1, col2 = st.columns(2)
        col1.text_input("Enter obstacle name:", key="obstacle_name")
        col2.text_input("Enter obstacle height in meters:", key="obstacle_height")

        lat, lon = None, None
        if address:
            geocode_result = gmaps.geocode(address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lon = location['lat'], location['lng']
        if not address:
            location = get_geolocation()
            coords = location["coords"] if location and "coords" in location else {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is not None and lon is not None:
                address = "You are here"
        
        if lat is None or lon is None:
            st.info("Address was not found on Google Maps.")
            m = None

        if lat is not None and lon is not None:
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.Marker([lat, lon], popup=address).add_to(m)
            m.add_child(folium.LatLngPopup())
            map_data = st_folium(m, height=300, width=700)
        else:
            map_data = None
        if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
            lat = map_data["last_clicked"]["lat"]
            lon = map_data["last_clicked"]["lng"]
            # Show only the last clicked marker
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.Marker([lat, lon], popup="Selected Location").add_to(m)

        if st.button("Save Obstacle", type="primary"):
            obstacle_name = st.session_state.get("obstacle_name", "")
            obstacle_height = st.session_state.get("obstacle_height", "")
            if not obstacle_name or not obstacle_height or not lat or not lon:
                st.toast("Please provide all fields and ensure location is set.", icon="❌")
            else:
                try:
                    obstacle_height = float(obstacle_height)
                    save_obstacle(obstacle_name, obstacle_height, lat, lon)
                    st.toast("Obstacle Saved!", icon="✅")
                except ValueError:
                    st.error("Height must be a number.")
            

elif page=="Obstacle Lists":

    try:
        df = read_obstacles()
    except Exception:
        st.warning("No obstacles found. Add a new obstacle first.")
        df = pd.DataFrame(columns=["Obstacle Name", "Height (m)", "Latitude", "Longitude"])

    # Display Obstacles on the Map
    if not df.empty:
        m = folium.Map(location=[df["Latitude"].mean(), df["Longitude"].mean()] if not df["Latitude"].isnull().all() else [0, 0], zoom_start=7)
        for _, obstacle in df.iterrows():
            if pd.isna(obstacle["Latitude"]) or pd.isna(obstacle["Longitude"]):
                continue
            folium.Marker(
                [obstacle["Latitude"], obstacle["Longitude"]],
                popup=f"{obstacle['Obstacle Name']} ({obstacle['Height (m)']}m)",
                icon=folium.Icon(color="red")
            ).add_to(m)
        st_folium(m, height=300, width=700)
    else:
        st.info("No obstacles to display on the map.")

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button("Save Changes", type="primary"):
        save_all_obstacles(edited_df)
        st.toast("Changes SAVED!", icon="✅")

elif page=="Route Planner":

    with st.form("route_planner_form"):
        del_from = st.text_input("Enter starting address:")
        del_to = st.text_input("Enter destination address:")
        vehicle_height = st.text_input("Enter your vehicle height in meters:")
        submitted = st.form_submit_button("Plan Route", type="primary")

    # if submitted:
        if not del_from or not del_to or not vehicle_height:
            st.error("Please provide all fields.")
        else:
            try:
                vehicle_height = float(vehicle_height)
                # Get route polyline from Google Directions API
                directions = gmaps.directions(del_from, del_to, mode="driving")
                if not directions:
                    st.error("Could not find a route between the addresses.")
                else:
                    # Decode polyline to get route coordinates
                    steps = directions[0]['legs'][0]['steps']
                    route_points = []
                    for step in steps:
                        points = googlemaps.convert.decode_polyline(step['polyline']['points'])
                        route_points.extend([(p['lat'], p['lng']) for p in points])

                    # Load obstacles
                    try:
                        df = read_obstacles()
                    except Exception:
                        st.warning("No obstacles found.")
                        df = pd.DataFrame(columns=["Obstacle Name", "Height (m)", "Latitude", "Longitude"])

                    obstacles_on_route = []
                    for _, row in df.iterrows():
                        obstacle_loc = (row["Latitude"], row["Longitude"])
                        # Check if obstacle is within 15 meters of any route point
                        for pt in route_points:
                            if geodesic(obstacle_loc, pt).meters <= 15:
                                obstacles_on_route.append(row)
                                break

                    # Show route and obstacles on map
                    if route_points:
                        m = folium.Map(location=route_points[0], zoom_start=12)
                        folium.PolyLine(route_points, color="blue", weight=5, opacity=0.7).add_to(m)
                        for _, row in df.iterrows():
                            color = "red" if any(
                                (row["Latitude"], row["Longitude"]) == (obs["Latitude"], obs["Longitude"])
                                for _, obs in pd.DataFrame(obstacles_on_route).iterrows()
                            ) else "green"
                            folium.Marker(
                                [row["Latitude"], row["Longitude"]],
                                popup=f"{row['Obstacle Name']} ({row['Height (m)']}m)",
                                icon=folium.Icon(color=color)
                            ).add_to(m)
                        st_folium(m, height=400, width=800)

                    if obstacles_on_route:
                        st.warning("Obstacles detected on your route:")
                        for _, obs in pd.DataFrame(obstacles_on_route).iterrows():
                            if obs["Height (m)"] < vehicle_height:
                                st.error(f"{obs['Obstacle Name']} ({obs['Height (m)']}m) - LOWER than your vehicle!")
                            else:
                                st.info(f"{obs['Obstacle Name']} ({obs['Height (m)']}m)")
                    else:
                        st.success("No obstacles found on your route.")
            except ValueError:
                st.error("Vehicle height must be a number.")