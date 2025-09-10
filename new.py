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
from shapely.geometry import LineString, Point
from streamlit.components.v1 import html

# -------------------------
# Ayarlar / Google Sheets
# -------------------------
SHEET_NAME = "obstacles"
WORKSHEET_NAME = "bridge_info"

scope = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
creds_dict = st.secrets["gcp_service_account"]
creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
gc = gspread.authorize(creds)

def get_worksheet():
    sh = gc.open(SHEET_NAME)
    try:
        ws = sh.worksheet(WORKSHEET_NAME)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=WORKSHEET_NAME, rows="1000", cols="4")
        ws.append_row(["Engel Adı", "Yükseklik (m)", "Enlem", "Boylam"])
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
    ws.append_row(["Engel Adı", "Yükseklik (m)", "Enlem", "Boylam"])
    for _, row in df.iterrows():
        ws.append_row([row["Engel Adı"], row["Yükseklik (m)"], row["Enlem"], row["Boylam"]])

# -------------------------
# Google Maps Client
# -------------------------
gmaps = googlemaps.Client(key=st.secrets["gmapsapi"])

st.set_page_config(page_title="Guzerhah Yükseklik Kontrolü", layout="centered", page_icon="🚛")

# -------------------------
# Basit Kimlik Doğrulama
# -------------------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

if not st.session_state.logged_in:
    st.subheader("Güzergah Yükseklik Kontrolü")
    username = st.text_input("Kullanıcı Adı")
    password = st.text_input("Şifre", type="password")
    if st.button("Giriş Yap", type="primary"):
        if username == "nst" and password == "nst":
            st.session_state.logged_in = True
            st.rerun()
        else:
            st.error("Geçersiz kullanıcı adı veya şifre")
    st.stop()

# -------------------------
# Menü
# -------------------------
page = st.selectbox(
    "MENÜ:",
    ["Yeni Engel", "Engel Listesi", "Rota Planlayıcı"],
    index=2  # default Rota Planlayıcı gösterilsin isterseniz değiştirin
)

# -------------------------
# Yeni Engel Sayfası
# -------------------------
if page == "Yeni Engel":
    with st.expander("Yeni engel ekle", expanded=True):
        address = st.text_input("Adres girin:", placeholder="Boş bırakılırsa mevcut konumunuz kullanılır")
        col1, col2 = st.columns(2, vertical_alignment="center")
        col1.text_input("Engel adı girin:", key="obstacle_name")
        col2.text_input("Engel yüksekliğini girin (m):", key="obstacle_height")
        col3, col4 = st.columns([3,1], vertical_alignment="center")

        lat, lon = None, None
        if address:
            geocode_result = gmaps.geocode(address)
            if geocode_result:
                location = geocode_result[0]['geometry']['location']
                lat, lon = location['lat'], location['lng']
        else:
            location = get_geolocation()
            coords = location["coords"] if location and "coords" in location else {}
            lat = coords.get("latitude")
            lon = coords.get("longitude")
            if lat is not None and lon is not None:
                address = "Buradasınız"

        if lat is None or lon is None:
            st.info("Adres Google Haritalar'da bulunamadı.")
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
            m = folium.Map(location=[lat, lon], zoom_start=15)
            folium.Marker([lat, lon], popup="Seçilen Konum").add_to(m)

        col3.info('Haritada kesin konumu tıklayın ve kaydet butonuna basın!')
        if col4.button("Engeli Kaydet", type="primary"):
            obstacle_name = st.session_state.get("obstacle_name", "")
            obstacle_height = st.session_state.get("obstacle_height", "")

            if not lat or not lon:
                st.toast("Lütfen haritada bir konum seçin.", icon="❌")
            elif not obstacle_name or not obstacle_height:
                st.toast("Lütfen engel adı ve yüksekliğini girin.", icon="❌")
            else:
                try:
                    obstacle_height = float(obstacle_height)
                    save_obstacle(obstacle_name, obstacle_height, lat, lon)
                    st.toast("Engel Kaydedildi!", icon="✅")
                except ValueError:
                    st.error("Yükseklik bir sayı olmalıdır.")

# -------------------------
# Engel Listesi Sayfası
# -------------------------
elif page == "Engel Listesi":
    try:
        df = read_obstacles()
    except Exception:
        st.warning("Engel bulunamadı. Önce yeni bir engel ekleyin.")
        df = pd.DataFrame(columns=["Engel Adı", "Yükseklik (m)", "Enlem", "Boylam"])

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Değişiklikleri Kaydet", type="primary"):
        save_all_obstacles(edited_df)
        st.toast("Değişiklikler KAYDEDİLDİ!", icon="✅")

    # if not df.empty:
    #     m = folium.Map(location=[df["Enlem"].mean(), df["Boylam"].mean()] if not df["Enlem"].isnull().all() else [0, 0], zoom_start=7)
    #     for _, obstacle in df.iterrows():
    #         if pd.isna(obstacle["Enlem"]) or pd.isna(obstacle["Boylam"]):
    #             continue
    #         folium.Marker(
    #             [obstacle["Enlem"], obstacle["Boylam"]],
    #             popup=f"{obstacle['Engel Adı']} ({obstacle['Yükseklik (m)']}m)",
    #             icon=folium.Icon(color="red")
    #         ).add_to(m)
    #     st_folium(m, height=400, width=800)
    # else:
    #     st.info("Haritada gösterilecek engel yok.")

# -------------------------
# Rota Planlayıcı Sayfası
# -------------------------
elif page == "Rota Planlayıcı":

    # Form ile rota isteği
    with st.form("route_planner_form"):
        del_from = st.text_input("Başlangıç adresini girin:", key="del_from_input")
        del_to = st.text_input("Varış adresini girin:", key="del_to_input")
        vehicle_height = st.text_input("Araç yüksekliğini metre cinsinden girin:", key="vehicle_height_input")
        submitted = st.form_submit_button("Rotayı Planla", type="primary")

        if submitted:
            # temiz önceki verileri
            st.session_state.pop("route_data", None)
            if not del_from or not del_to or not vehicle_height:
                st.error("Lütfen tüm alanları doldurun.")
            else:
                try:
                    vehicle_height_val = float(vehicle_height)
                except ValueError:
                    st.error("Araç yüksekliği bir sayı olmalıdır.")
                    vehicle_height_val = None

                if vehicle_height_val is not None:
                    # Directions al
                    try:
                        directions = gmaps.directions(
                            del_from,
                            del_to,
                            mode="driving",
                            alternatives=True
                        )
                    except Exception as e:
                        st.error(f"Google Directions API hatası: {e}")
                        directions = None

                    if not directions:
                        st.error("Adresler arasında bir rota bulunamadı.")
                    else:
                        # Engelleri oku
                        try:
                            df_obs = read_obstacles()
                        except Exception:
                            st.warning("Engel bulunamadı.")
                            df_obs = pd.DataFrame(columns=["Engel Adı", "Yükseklik (m)", "Enlem", "Boylam"])

                        # hazırlık
                        buffer = 10  # metre
                        route_points_list = []
                        route_summaries = []

                        # her rota için polyline -> point listesi oluştur
                        for idx, route in enumerate(directions):
                            steps = route['legs'][0]['steps']
                            route_points = []
                            for step in steps:
                                points = googlemaps.convert.decode_polyline(step['polyline']['points'])
                                route_points.extend([(p['lat'], p['lng']) for p in points])
                            route_points_list.append(route_points)

                        # her rota için özet (mesafe, süre, engel sayısı, tehlikeli engel sayısı, engel isimleri)
                        for idx, route in enumerate(directions):
                            # LineString oluştur (shapely lon,lat)
                            if not route_points_list[idx]:
                                route_line = None
                            else:
                                route_line = LineString([(lng, lat) for lat, lng in route_points_list[idx]])

                            obstacles_on_route = []
                            if route_line is not None and not df_obs.empty:
                                for _, row in df_obs.iterrows():
                                    try:
                                        if pd.isna(row["Enlem"]) or pd.isna(row["Boylam"]):
                                            continue
                                        obstacle_point = Point(row["Boylam"], row["Enlem"])
                                        distance_m = route_line.distance(obstacle_point) * 111_320
                                        if distance_m <= buffer:
                                            obstacles_on_route.append(row)
                                    except Exception:
                                        continue

                            # tehlike sayısı
                            blocking_count = 0
                            for obs in obstacles_on_route:
                                try:
                                    if float(obs["Yükseklik (m)"]) < vehicle_height_val:
                                        blocking_count += 1
                                except Exception:
                                    pass

                            distance_text = route['legs'][0]['distance']['text'] if 'distance' in route['legs'][0] else ""
                            duration_text = route['legs'][0]['duration']['text'] if 'duration' in route['legs'][0] else ""
                            obstacle_list_str = "; ".join([f"{obs['Engel Adı']} ({obs['Yükseklik (m)']}m)" for obs in obstacles_on_route])

                            route_summaries.append({
                                "Rota": f"Alternatif Rota {idx+1}",
                                "Mesafe": distance_text,
                                "Süre": duration_text,
                                "Engel": len(obstacles_on_route),
                                "Tehlikeli Engel": blocking_count,
                                "Engeller": obstacle_list_str
                            })

                        # session_state'e kaydet (harita çizimi için)
                        st.session_state["route_data"] = {
                            "directions": directions,
                            "route_points_list": route_points_list,
                            "route_summaries": route_summaries,
                            "vehicle_height": vehicle_height_val
                        }

                        # form submit sonrası sayfa yenileyip seçimi göstermek için
                        st.success("Rotalar alındı — aşağıdan bir rota seçin veya tümünü gösterin.")
                        st.rerun()

    # formun hemen altında: eğer daha önce rotalar alınmışsa, göster ve seçilebilsin
    if "route_data" in st.session_state:
        data = st.session_state["route_data"]
        directions = data["directions"]
        route_points_list = data["route_points_list"]
        route_summaries = data["route_summaries"]
        vehicle_height_val = data["vehicle_height"]

        # Özet tabloyu göster
        df_summary = pd.DataFrame(route_summaries)
        # st.markdown("### Rota Özeti")
        st.dataframe(df_summary, use_container_width=True, hide_index=True)

        # rota seçim dropdown (form dışında, anında etki)
        rota_options = ["Tüm rotalar"] + [f"Alternatif Rota {i+1}" for i in range(len(directions))]
        rota_secim = st.selectbox("Gösterilecek rota:", rota_options, key="rota_secim_selector")

        # haritayı oluştur
        start_lat = directions[0]['legs'][0]['start_location']['lat']
        start_lng = directions[0]['legs'][0]['start_location']['lng']
        m = folium.Map(location=[start_lat, start_lng], zoom_start=12)

        colors = ["blue", "green", "purple", "orange", "red"]

        # hangi rotalar gösterilecek?
        if rota_secim == "Tüm rotalar":
            displayed_idx = list(range(len(directions)))
        else:
            # "Alternatif Rota N" -> extract N
            try:
                n = int(rota_secim.split()[-1])
                displayed_idx = [n-1]
            except Exception:
                displayed_idx = list(range(len(directions)))

        # hazırlık: shapely route_lines
        route_lines = []
        for rp in route_points_list:
            if rp:
                route_lines.append(LineString([(lng, lat) for lat, lng in rp]))
            else:
                route_lines.append(None)

        # rotaları çiz
        for idx in displayed_idx:
            rp = route_points_list[idx]
            if not rp:
                continue
            distance_text = directions[idx]['legs'][0]['distance']['text'] if 'distance' in directions[idx]['legs'][0] else ""
            duration_text = directions[idx]['legs'][0]['duration']['text'] if 'duration' in directions[idx]['legs'][0] else ""
            color = colors[idx % len(colors)]
            folium.PolyLine(rp, color=color, weight=5, opacity=0.8,
                            popup=f"Alternatif Rota {idx+1} ({distance_text}, {duration_text})").add_to(m)

        # engelleri işaretle (seçili rotalar üzerinden kontrol)
        try:
            df_obs = read_obstacles()
        except Exception:
            df_obs = pd.DataFrame(columns=["Engel Adı", "Yükseklik (m)", "Enlem", "Boylam"])

        buffer = 10  # metre
        for _, row in df_obs.iterrows():
            try:
                if pd.isna(row["Enlem"]) or pd.isna(row["Boylam"]):
                    continue
                obstacle_point = Point(row["Boylam"], row["Enlem"])
            except Exception:
                continue

            # bu engel seçili rotalardan herhangi birinin yakınındaysa işaretle
            on_displayed_route = False
            for ridx in displayed_idx:
                rl = route_lines[ridx]
                if rl is None:
                    continue
                try:
                    distance_m = rl.distance(obstacle_point) * 111_320
                    if distance_m <= buffer:
                        on_displayed_route = True
                        break
                except Exception:
                    continue

            # yükseklik kontrolü
            is_danger = False
            try:
                is_danger = float(row["Yükseklik (m)"]) < vehicle_height_val
            except Exception:
                is_danger = False

            if on_displayed_route and is_danger:
                marker_color = "red"
            elif on_displayed_route and not is_danger:
                marker_color = "orange"
            else:
                marker_color = "green"

            folium.Marker(
                [row["Enlem"], row["Boylam"]],
                popup=f"{row['Engel Adı']} ({row['Yükseklik (m)']}m)",
                icon=folium.Icon(color=marker_color)
            ).add_to(m)

            # radius
            folium.Circle(
                location=[row["Enlem"], row["Boylam"]],
                radius=buffer,
                color="blue",
                weight=1,
                fill=True,
                fill_opacity=0.15
            ).add_to(m)

        # haritayı göster
        st_folium(m, height=500, width=900, key="route_map")
