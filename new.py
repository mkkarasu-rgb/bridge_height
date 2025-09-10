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

    if not df.empty:
        m = folium.Map(location=[df["Enlem"].mean(), df["Boylam"].mean()] if not df["Enlem"].isnull().all() else [0, 0], zoom_start=7)
        for _, obstacle in df.iterrows():
            if pd.isna(obstacle["Enlem"]) or pd.isna(obstacle["Boylam"]):
                continue
            folium.Marker(
                [obstacle["Enlem"], obstacle["Boylam"]],
                popup=f"{obstacle['Engel Adı']} ({obstacle['Yükseklik (m)']}m)",
                icon=folium.Icon(color="red")
            ).add_to(m)
        st_folium(m, height=400, width=800)
    else:
        st.info("Haritada gösterilecek engel yok.")

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Değişiklikleri Kaydet", type="primary"):
        save_all_obstacles(edited_df)
        st.toast("Değişiklikler KAYDEDİLDİ!", icon="✅")

# -------------------------
# Rota Planlayıcı Sayfası
# -------------------------
# ✅ Rota Planlayıcı
elif page == "Rota Planlayıcı":
    with st.form("route_planner_form"):
        del_from = st.text_input("Başlangıç adresini girin:")
        del_to = st.text_input("Varış adresini girin:")
        vehicle_height = st.text_input("Araç yüksekliğini metre cinsinden girin:")
        submitted = st.form_submit_button("Rotayı Planla", type="primary")

    if submitted:
        if not del_from or not del_to or not vehicle_height:
            st.error("Lütfen tüm alanları doldurun.")
        else:
            try:
                vehicle_height = float(vehicle_height)
                directions = gmaps.directions(
                    del_from,
                    del_to,
                    mode="driving",
                    alternatives=True
                )
                if not directions:
                    st.error("Adresler arasında bir rota bulunamadı.")
                else:
                    try:
                        df = read_obstacles()
                    except Exception:
                        st.warning("Engel bulunamadı.")
                        df = pd.DataFrame(columns=["Engel Adı", "Yükseklik (m)", "Enlem", "Boylam"])

                    colors = ["blue", "green", "purple", "orange", "red"]
                    buffer = 10  # metre
                    all_routes = []

                    for idx, route in enumerate(directions):
                        steps = route['legs'][0]['steps']
                        route_points = []
                        for step in steps:
                            points = googlemaps.convert.decode_polyline(step['polyline']['points'])
                            route_points.extend([(p['lat'], p['lng']) for p in points])

                        route_line = LineString([(lng, lat) for lat, lng in route_points])

                        obstacles_on_route = []
                        for _, row in df.iterrows():
                            obstacle_point = Point(row["Boylam"], row["Enlem"])
                            distance_m = route_line.distance(obstacle_point) * 111_320
                            if distance_m <= buffer:
                                obstacles_on_route.append(row)

                        all_routes.append({
                            "idx": idx,
                            "points": route_points,
                            "distance": route['legs'][0]['distance']['text'],
                            "duration": route['legs'][0]['duration']['text'],
                            "obstacles": obstacles_on_route
                        })

                    # ✅ Sonuçları session_state içine kaydet
                    st.session_state["route_data"] = {
                        "routes": all_routes,
                        "obstacles": df,
                        "vehicle_height": vehicle_height
                    }

            except ValueError:
                st.error("Araç yüksekliği bir sayı olmalıdır.")

    # ✅ Harita ve tablo gösterimi (yeniden hesaplama yapmadan)
    if "route_data" in st.session_state:
        data = st.session_state["route_data"]
        routes = data["routes"]
        df = data["obstacles"]
        vehicle_height = data["vehicle_height"]

        rota_secim = st.selectbox(
            "Gösterilecek rota:",
            ["Tüm rotalar"] + [f"Alternatif Rota {r['idx']+1}" for r in routes]
        )

        # ✅ Harita oluştur
        m = folium.Map(location=routes[0]["points"][0], zoom_start=12)

        for r in routes:
            if rota_secim != "Tüm rotalar" and rota_secim != f"Alternatif Rota {r['idx']+1}":
                continue

            color = colors[r["idx"] % len(colors)]
            folium.PolyLine(r["points"], color=color, weight=5, opacity=0.7,
                            popup=f"Alternatif Rota {r['idx']+1}").add_to(m)

            for _, row in df.iterrows():
                color_marker = "red" if any(row["Engel Adı"] == obs["Engel Adı"] for _, obs in pd.DataFrame(r["obstacles"]).iterrows()) else "green"
                folium.Marker(
                    [row["Enlem"], row["Boylam"]],
                    popup=f"{row['Engel Adı']} ({row['Yükseklik (m)']}m)",
                    icon=folium.Icon(color=color_marker)
                ).add_to(m)

        # ✅ Haritayı embed et (zoom/pan sırasında yeniden hesaplama yapılmaz)
        map_html = m._repr_html_()
        html(map_html, height=500, width=900)

        # ✅ Rota tablosu
        summary_data = []
        for r in routes:
            engel_sayisi = len(r["obstacles"])
            riskli_engel = any(obs["Yükseklik (m)"] < vehicle_height for _, obs in pd.DataFrame(r["obstacles"]).iterrows())
            durum = "⚠️ Riskli Engel Var" if riskli_engel else ("✅ Engel Var (Yeterli Yükseklik)" if engel_sayisi > 0 else "🟢 Engel Yok")
            summary_data.append({
                "Rota": f"Alternatif Rota {r['idx']+1}",
                "Mesafe": r["distance"],
                "Süre": r["duration"],
                "Engel Sayısı": engel_sayisi,
                "Durum": durum
            })

        st.subheader("Rota Özeti")
        st.table(pd.DataFrame(summary_data))