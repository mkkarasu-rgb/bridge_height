import streamlit as st
import pandas as pd
import googlemaps
import folium
from geopy.distance import geodesic
import json
from streamlit_js_eval import get_geolocation
from streamlit_folium import st_folium

st.set_page_config(page_title="Yol Kontrol", layout="centered", page_icon="🚛")
gmaps = googlemaps.Client(key=st.secrets["gmapsapi"]) # You would get your API keys from st.secrets


# Authentication
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("Yol Kontrol - Giriş")
    username = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")
    if st.button("Giriş", type="primary"):
        if username == st.secrets["username"] and password == st.secrets["password"]:
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Hatalı kullanıcı adı veya şifre.")
    st.stop()

page = "Yeni Engel"  # Default page

page = st.selectbox(
    "MENU:",
    ["Yeni Engel", "Engel Listesi", "Rota Kontrol"],
    index=["Yeni Engel", "Engel Listesi", "Rota Kontrol"].index(page),
    key="main_menu"
)

if page == "Yeni Engel":

    with st.expander("Yeni engel ekleyin", expanded=True):

        address = st.text_input("Adresi Girin:", placeholder="Boş bırakıldığında mevcut konum kullanılır")
        col1, col2 = st.columns(2)
        col1.text_input("Engel Adi:", key="obstacle_name")
        col2.text_input("Engel Yüksekliği (m):", key="obstacle_height")

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
                address = "Buradasınız"
        
        if lat is None or lon is None:
            st.info("Adres Google Haritalarda bulunamadı.")
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
            folium.Marker([lat, lon], popup="Seçilen Konum").add_to(m)

        if st.button("Engeli Kaydet", type="primary"):
            obstacle_name = st.session_state.get("obstacle_name", "")
            obstacle_height = st.session_state.get("obstacle_height", "")
            if not obstacle_name or not obstacle_height or not lat or not lon:
                st.toast("Engel Adi, yüksekliği veya konumunu eksik.", icon="❌")
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
                    st.toast("Engel eklendi!", icon="✅")
                except ValueError:
                    st.error("Yükseklik rakam olmalı.")
            

elif page=="Engel Listesi":

    csv_path = "bridge_info.csv"
    try:
        df = pd.read_csv(csv_path)
    except FileNotFoundError:
        st.warning("Engel bulunamadı. Lütfen önce yeni engel ekleyin.")
        df = pd.DataFrame(columns=["Engel Adi", "Yükseklik (m)", "Enlem", "Boylam"])

    # Display Obstacles on the Map
    if not df.empty:
        m = folium.Map(location=[df["Latitude"].mean(), df["Longitude"].mean()] if not df["Latitude"].isnull().all() else [0, 0], zoom_start=7)
        for _, obstacle in df.iterrows():
            folium.Marker(
                [obstacle["Latitude"], obstacle["Longitude"]],
                popup=f"{obstacle['Engel Adi']} ({obstacle['Yükseklik (m)']}m)",
                icon=folium.Icon(color="red")
            ).add_to(m)
        st_folium(m, height=300, width=700)
    else:
        st.info("Haritada gösterilecek engel yok.")

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button("Değişiklikleri kaydet", type="primary"):
        edited_df.to_csv(csv_path, index=False)
        st.toast("Kayıt Başarılı!", icon="✅")

elif page=="Rota Kontrol":

    with st.form("route_planner_form"):
        del_from = st.text_input("Çıkış adresi:")
        del_to = st.text_input("Varış adresi:")
        vehicle_height = st.text_input("Araç yüksekliği (m):")
        submitted = st.form_submit_button("Rota Oluştur", type="primary")

    if submitted:
        if not del_from or not del_to or not vehicle_height:
            st.error("Eksik bilgileri giriniz.")
        else:
            try:
                vehicle_height = float(vehicle_height)
            except ValueError:
                st.error("Araç yüksekliği rakam olmalı.")
                vehicle_height = None

            if vehicle_height is not None:
                directions_result = gmaps.directions(
                    del_from, del_to, mode="driving", departure_time="now",
                    avoid=["ferries"], traffic_model="best_guess",
                    alternatives=False, optimize_waypoints=True
                )
                if not directions_result:
                    st.error("Rota bulunamadı. Adresleri kontrol edin.")
                else:
                    steps = directions_result[0]['legs'][0]['steps']
                    csv_path = "bridge_info.csv"
                    try:
                        obstacles_df = pd.read_csv(csv_path)
                    except FileNotFoundError:
                        obstacles_df = pd.DataFrame(columns=["Engel Adi", "Yükseklik (m)", "Enlem", "Boylam"])

                    obstacle_warnings = []
                    for step in steps:
                        start_loc = (step['start_location']['lat'], step['start_location']['lng'])
                        end_loc = (step['end_location']['lat'], step['end_location']['lng'])
                        for _, obstacle in obstacles_df.iterrows():
                            obstacle_loc = (obstacle['Latitude'], obstacle['Longitude'])
                            dist_to_start = geodesic(start_loc, obstacle_loc).meters
                            dist_to_end = geodesic(end_loc, obstacle_loc).meters
                            if dist_to_start < 150 or dist_to_end < 150:
                                if obstacle['Yükseklik (m)'] < vehicle_height:
                                    warning = (
                                        f"Uyarı: '{obstacle['Engel Adi']}' yüksekliği"
                                        f"{obstacle['Yükseklik (m)']}m aracınız için çok alçak ({vehicle_height}m) "
                                        f"near step: {step['html_instructions']}"
                                    )
                                    obstacle_warnings.append(warning)
                    if obstacle_warnings:
                        st.toast("Rota üzerinde engel tespit edildi",icon="❌")
                        # for warning in obstacle_warnings:
                        #     st.error(warning)
                    else:
                        st.toast("Rota üzerinde engel yok.",icon="✅")

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
                    obstacles_df = pd.DataFrame(columns=["Engel Adi", "Yükseklik (m)", "Enlem", "Boylam"])
                for _, obstacle in obstacles_df.iterrows():
                    folium.Marker(
                        [obstacle['Latitude'], obstacle['Longitude']],
                        popup=f"{obstacle['Engel Adi']} ({obstacle['Yükseklik (m)']}m)",
                        icon=folium.Icon(color="red" if obstacle['Yükseklik (m)'] < float(vehicle_height) else "green")
                    ).add_to(m)
                # Add markers for start and end locations
                folium.Marker(
                    [route_points[0]['lat'], route_points[0]['lng']],
                    popup="Çıkış",
                    icon=folium.Icon(color="blue", icon="play")
                ).add_to(m)
                folium.Marker(
                    [route_points[-1]['lat'], route_points[-1]['lng']],
                    popup="Varış",
                    icon=folium.Icon(color="blue", icon="flag")
                ).add_to(m)
                st_folium(m, height=300, width=700)
