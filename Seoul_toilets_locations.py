from datetime import datetime
import pytz
import pandas as pd
import streamlit as st
import folium
from haversine import haversine
from streamlit.components.v1 import html
import time
import pandas as pd
import requests
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from cachetools import TTLCache
import threading


@st.cache_data(ttl=3600)
def load_data():
    # 데이터 로드
    df = pd.read_csv("https://roasample.cafe24.com/data/Seoul_toilet_location.csv", encoding="utf-8")
    return df


def calculate_distance_score(df, my_latitude, my_longitude):
    # 거리에 따른 점수를 부여하여 Distance Score 컬럼 업데이트
    for index, row in df.iterrows():
        point_latitude = row['latitude']
        point_longitude = row['longitude']

        # 내 위치와 데이터프레임의 위치 간의 거리를 계산 (위도, 경도 순서로 사용)
        distance = haversine((my_latitude, my_longitude), (point_latitude, point_longitude), unit='m')

        # 거리에 따라 점수 부여
        if distance <= 50:  # 50m 이내
            df.loc[index, 'Distance Score'] = 10
        elif distance <= 100:  # 50m 초과 100m 이하
            df.loc[index, 'Distance Score'] = 8
        elif distance <= 150:  # 100m 초과 150m 이하
            df.loc[index, 'Distance Score'] = 6
        elif distance <= 200:  # 150m 초과 200m 이하
            df.loc[index, 'Distance Score'] = 4
        elif distance <= 300:  # 200m 초과 300m 이하
            df.loc[index, 'Distance Score'] = 2
        else:
            df.loc[index, 'Distance Score'] = 0


@st.cache_data(ttl=3600)
def fetch_congestion_score(area_nm, df_locations):
    base_url = 'http://openapi.seoul.go.kr:8088/444c4c4a536232733734746f76556f/xml/citydata_ppltn/1/5/{area_nm}'
    url = base_url.format(area_nm=area_nm)
    response = requests.get(url)

    if response.status_code == 200:
        root = ET.fromstring(response.text)
        ppltn_time = root.find('.//PPLTN_TIME').text
        area_nm = root.find('.//AREA_NM').text
        area_congest_lvl = root.find('.//AREA_CONGEST_LVL').text
        location_row = df_locations[df_locations['name'] == area_nm]
        lat = location_row['latitude'].iloc[0]
        long = location_row['longitude'].iloc[0]
        score = 0

        if area_congest_lvl == '여유':
            score = 3
        elif area_congest_lvl == '보통':
            score = 5
        elif area_congest_lvl == '약간 붐빔':
            score = 8
        elif area_congest_lvl == '붐빔':
            score = 10

        return {
            'Real time': ppltn_time,
            'name': area_nm,
            'Congestion lv': area_congest_lvl,
            'latitude': lat,
            'longitude': long,
            'Congestion Score': score
        }
    else:
        return None


def update_congestion_scores(df_locations, cache):
    while True:
        with ThreadPoolExecutor() as executor:
            futures = []

            for area_nm in df_locations['name']:
                if area_nm in cache:
                    result = cache[area_nm]
                else:
                    future = executor.submit(fetch_congestion_score, area_nm, df_locations)
                    futures.append(future)

            for future in futures:
                result = future.result()
                area_nm = result['name']
                cache[area_nm] = result

        time.sleep(3600)  # 1시간 대기


def main():
    # 쿼리 파라미터 가져오기
    query_params = st.experimental_get_query_params()

    if "latitude" in query_params and "longitude" in query_params:
        if "latitude" in query_params:
            my_latitude = float(query_params["latitude"][0])

        if "longitude" in query_params:
            my_longitude = float(query_params["longitude"][0])
    else:
        # 내 위치 정보를 설정
        my_latitude = st.sidebar.number_input("위도(Latitude)", value=37.5, key="latitude")
        my_longitude = st.sidebar.number_input("경도(Longitude)", value=126.90, key="longitude")

    # 데이터 로드
    df = load_data()

    # 거리 점수 계산
    calculate_distance_score(df, my_latitude, my_longitude)

    # 현재 시간 가져오기
    now = datetime.now()
    korea_timezone = pytz.timezone("Asia/Seoul")
    korea_time = now.astimezone(korea_timezone)
    time_str = korea_time.strftime("%H")

    # CSV 파일 경로
    csv_file = "https://roasample.cafe24.com/data/Seoul_location_113_lat_long.csv"

    # CSV 파일 읽기
    df_locations = pd.read_csv(csv_file)

    # 'name' 열의 값을 사용하여 area_nms 리스트 생성
    area_nms = df_locations['name'].tolist()

    # 결과를 저장할 데이터프레임 생성
    result_df = pd.DataFrame(
        columns=['Real time', 'name', 'Congestion lv', 'latitude', 'longitude', 'Congestion Score'])

    # 데이터 캐싱을 위한 캐시 생성
    cache = TTLCache(maxsize=100, ttl=3600)

    # 실시간 혼잡도 정보 업데이트 스레드 시작
    update_thread = threading.Thread(target=update_congestion_scores, args=(df_locations, cache))
    update_thread.start()

    while True:
        # 현재 시간에 해당하는 Congestion Score 추출
        time_congestion = result_df["Congestion Score"]

        # 'Seoul_toilet_location.csv' 파일에 Congestion Score 컬럼 추가
        df["Congestion Score"] = time_congestion

        # Final Score 컬럼 추가
        df['Final Score'] = df["Distance Score"] - df["Congestion Score"].apply(
            lambda x: sum(x) / len(x) if isinstance(x, list) and len(x) > 0 else 0)

        # 결과를 저장할 리스트 초기화
        results = []

        # 기준 좌표 설정
        for _, location_row in df_locations.iterrows():
            target_latitude = location_row['latitude']
            target_longitude = location_row['longitude']

            # 반경 1km 이내에 있는지 확인
            within_radius = []
            for _, toilet_row in df.iterrows():
                toilet_latitude = toilet_row['latitude']
                toilet_longitude = toilet_row['longitude']
                distance = haversine((target_latitude, target_longitude), (toilet_latitude, toilet_longitude),
                                     unit='km')
                if distance <= 1:
                    within_radius.append(
                        (toilet_row['name'],
                         toilet_latitude,
                         toilet_longitude)
                    )

            # 결과 리스트에 추가
            results.append({
                'Location': (target_latitude, target_longitude),
                'Within 1km': within_radius,
                'Congestion Score': None  # 초기값 설정
            })

        # 반경 1km 이내에 없는 화장실에 대해 점수 6 할당
        outside_radius = df[~df['name'].isin([toilet_name for toilet_name, _, _ in within_radius])]
        outside_radius_index = outside_radius.index
        df.loc[outside_radius_index, 'Congestion Score'] = 6

        # 결과 데이터프레임 생성
        result_df = pd.DataFrame(results)

        # 'Within 1km'의 좌표에 해당하는 열에 'Congestion Score'를 할당
        for i in range(len(result_df)):
            within_1km = result_df.loc[i, 'Within 1km']
            congestion_scores = []
            for toilet_name, toilet_latitude, toilet_longitude in within_1km:
                # 원본 데이터프레임에서 해당 좌표와 일치하는 행을 찾음
                matching_row = df[(df['latitude'] == toilet_latitude) & (df['longitude'] == toilet_longitude)]
                if not matching_row.empty:
                    congestion_score = matching_row.iloc[0]['Congestion Score']
                    congestion_scores.append(congestion_score)
            result_df.at[i, 'Congestion Score'] = congestion_scores

        # 추천하는 좌표 개수 설정
        recommendations = min(3, len(df))  # 추천하는 좌표 개수를 원하는 값과 데이터프레임의 크기 중 작은 값으로 설정

        # 거리 점수와 Final Score에 따라 추천하는 좌표 추출
        df = df.sort_values(['Distance Score', 'Final Score'],
                            ascending=[False, False])  # Distance Score와 Final Score에 따라 정렬
        recommended_df = df.head(recommendations)  # 상위 추천 개수만큼 추출

        # 지도 생성
        tile_seoul_map = folium.Map(location=[my_latitude, my_longitude], zoom_start=16, tiles="Stamen Terrain")

        # 내 위치 마커 추가
        folium.Marker([my_latitude, my_longitude], popup="My Location", icon=folium.Icon(color='red')).add_to(
            tile_seoul_map)

        has_recommended_coordinates = False
        # 추천하는 좌표에 다른 색상의 마커로 추가
        for i in range(len(recommended_df)):
            name, latitude, longitude = recommended_df.iloc[i][['name', 'latitude', 'longitude']]
            popup_text = f"Name: {name}, Congestion lv: {recommended_df.iloc[i]['Congestion Score']}"
            distance = haversine((my_latitude, my_longitude), (latitude, longitude), unit='m')
            if distance <= 500:  # 500m 이내인 경우에만 마커 추가
                has_recommended_coordinates = True
                folium.Marker([latitude, longitude], popup=popup_text, icon=folium.Icon(color='green')).add_to(
                    tile_seoul_map)

                # 좌표 정보 출력
                st.write(f"{i + 1} : {name} ({recommended_df.iloc[i]['Congestion Score']})")

        # 200미터 이내에 추천할 좌표가 없는 경우 메시지 출력
        if not has_recommended_coordinates:
            st.warning("‼️ 500m 이내에 추천할 화장실이 없습니다.")

        # HTML로 변환
        map_html = tile_seoul_map.get_root().render()

        # Streamlit 애플리케이션에 표시
        st.title("Seoul Toilet Locations")
        html(map_html, height=500)

        break


if __name__ == '__main__':
    main()
