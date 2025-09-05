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


page = "New Obstacle"

page = st.selectbox(
    "MENU:",
    ["New Obstacle", "Obstacle Lists", "Route Planner"],
    index=["New Obstacle", "Obstacle Lists", "Route Planner"].index(page),
    key="main_menu"
)

if page == "New Obstacle":

    with st.expander("Location Method", expanded=True):
        selected_method= st.radio("Choose from:", ["Current Location", "Enter Address or Coordinates"])

    if selected_method == "Current Location":

        with st.expander("Enter Name, Height and Click on the Map", expanded=True):
            col1, col2 = st.columns(2)
            col1.text_input("Enter obstacle name:", key="obstacle_name")
            col2.text_input("Enter obstacle height in meters:", key="obstacle_height")
        
            location = get_geolocation()
            coords = location["coords"] if location and "coords" in location else {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is not None and lon is not None:
                m = folium.Map(location=[lat, lon], zoom_start=12)
                folium.Marker([lat, lon], popup="You are here", icon=folium.Icon(color="blue")).add_to(m) 
            m.add_child(folium.LatLngPopup())
            map_data = st_folium(m, height=500, width=800)
            if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
                lat = map_data["last_clicked"]["lat"]
                lon = map_data["last_clicked"]["lng"]
            else:
                lat, lon = None, None

    elif selected_method == "Enter Address or Coordinates":

        address = st.text_input("Enter an address:")
        col1, col2 = st.columns(2)
        col1.text_input("Enter obstacle name:", key="obstacle_name")
        col2.text_input("Enter obstacle height in meters:", key="obstacle_height")

        lat, lon = None, None
        if address:
            geocode_result = gmaps.geocode(address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lon = location['lat'], location['lng']

        m = None
        if lat is not None and lon is not None:
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.Marker([lat, lon], popup=address).add_to(m)
        m.add_child(folium.LatLngPopup())
        map_data = st_folium(m, height=500, width=800)
        if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
            lat = map_data["last_clicked"]["lat"]
            lon = map_data["last_clicked"]["lng"]
            # Show only the last clicked marker
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.Marker([lat, lon], popup="Selected Location").add_to(m)
            st_folium(m, height=500, width=800)

    col1,col2,col3 = st.columns(3)
    if col2.button("Save Obstacle", type="primary"):
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

    # Display Obstacles on the Map
    if not df.empty:
        m = folium.Map(location=[df["Latitude"].mean(), df["Longitude"].mean()] if not df["Latitude"].isnull().all() else [0, 0], zoom_start=7)
        for _, obstacle in df.iterrows():
            folium.Marker(
                [obstacle["Latitude"], obstacle["Longitude"]],
                popup=f"{obstacle['Obstacle Name']} ({obstacle['Height (m)']}m)",
                icon=folium.Icon(color="red")
            ).add_to(m)
        st_folium(m, height=500, width=800)
    else:
        st.info("No obstacles to display on the map.")

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button("Save Changes", type="primary"):
        edited_df.to_csv(csv_path, index=False)
        st.toast("Changes SAVED!", icon="✅")

elif page=="Route Planner":

    with st.form("route_planner_form"):
        del_from = st.text_input("Enter starting address:")
        del_to = st.text_input("Enter destination address:")
        vehicle_height = st.text_input("Enter your vehicle height in meters:")
        submitted = st.form_submit_button("Plan Route")

    if submitted:
        if not del_from or not del_to or not vehicle_height:
            st.error("Please provide all fields.")
        else:
            try:
                vehicle_height = float(vehicle_height)
            except ValueError:
                st.error("Vehicle height must be a number.")
                vehicle_height = None

            if vehicle_height is not None:
                directions_result = gmaps.directions(
                    del_from, del_to, mode="driving", departure_time="now",
                    avoid=["ferries"], traffic_model="best_guess",
                    alternatives=False, optimize_waypoints=True
                )
                if not directions_result:
                    st.error("Could not find a route. Please check the addresses.")
                else:
                    steps = directions_result[0]['legs'][0]['steps']
                    csv_path = "bridge_info.csv"
                    try:
                        obstacles_df = pd.read_csv(csv_path)
                    except FileNotFoundError:
                        obstacles_df = pd.DataFrame(columns=["Obstacle Name", "Height (m)", "Latitude", "Longitude"])

                    obstacle_warnings = []
                    for step in steps:
                        start_loc = (step['start_location']['lat'], step['start_location']['lng'])
                        end_loc = (step['end_location']['lat'], step['end_location']['lng'])
                        for _, obstacle in obstacles_df.iterrows():
                            obstacle_loc = (obstacle['Latitude'], obstacle['Longitude'])
                            dist_to_start = geodesic(start_loc, obstacle_loc).meters
                            dist_to_end = geodesic(end_loc, obstacle_loc).meters
                            if dist_to_start < 150 or dist_to_end < 150:
                                if obstacle['Height (m)'] < vehicle_height:
                                    warning = (
                                        f"Warning: Obstacle '{obstacle['Obstacle Name']}' with height "
                                        f"{obstacle['Height (m)']}m is too low for your vehicle ({vehicle_height}m) "
                                        f"near step: {step['html_instructions']}"
                                    )
                                    obstacle_warnings.append(warning)
                    if obstacle_warnings:
                        st.toast("Height obstacles detected on your route",icon="⚠️")
                        # for warning in obstacle_warnings:
                        #     st.error(warning)
                    else:
                        st.toast("No height obstacles on your route!",icon="✅")

    # Visualize Route and Obstacles
    if del_from and del_to:
        directions_result = gmaps.directions(del_from, del_to, mode="driving", departure_time="now", avoid=["ferries"], traffic_model="best_guess", alternatives=False, optimize_waypoints=True)
        if directions_result:
            route_points = []
            steps = directions_result[0]['legs'][0]['steps']
            for step in steps:
                polyline = step.get('polyline', {}).get('points')
                if polyline:
                    route_points += googlemaps.convert.decode_polyline(polyline)
            if route_points:
                start_latlng = [route_points[0]['lat'], route_points[0]['lng']]
                m = folium.Map(location=start_latlng, zoom_start=7)
                folium.PolyLine([(pt['lat'], pt['lng']) for pt in route_points], color="blue", weight=5, opacity=0.7).add_to(m)
                csv_path = "bridge_info.csv"
                try:
                    obstacles_df = pd.read_csv(csv_path)
                except FileNotFoundError:
                    obstacles_df = pd.DataFrame(columns=["Obstacle Name", "Height (m)", "Latitude", "Longitude"])
                for _, obstacle in obstacles_df.iterrows():
                    folium.Marker(
                        [obstacle['Latitude'], obstacle['Longitude']],
                        popup=f"{obstacle['Obstacle Name']} ({obstacle['Height (m)']}m)",
                        icon=folium.Icon(color="red" if obstacle['Height (m)'] < float(vehicle_height) else "green")
                    ).add_to(m)
                # Add markers for start and end locations
                folium.Marker(
                    [route_points[0]['lat'], route_points[0]['lng']],
                    popup="Start",
                    icon=folium.Icon(color="blue", icon="play")
                ).add_to(m)
                folium.Marker(
                    [route_points[-1]['lat'], route_points[-1]['lng']],
                    popup="Destination",
                    icon=folium.Icon(color="green", icon="flag")
                ).add_to(m)
                st_folium(m, height=500, width=800)
