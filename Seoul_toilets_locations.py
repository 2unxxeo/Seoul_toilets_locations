import streamlit as st
import folium
import pandas as pd
from haversine import haversine
from streamlit.components.v1 import html


def load_data():
    # 데이터 로드
    df = pd.read_csv("https://roasample.cafe24.com/data/Seoul_toilet_locations.csv", encoding="utf-8")
    return df


# # 내 위치 정보를 설정
# my_latitude = st.number_input("위도(Latitude)", value=37.5, key="latitude")
# my_longitude = st.number_input("경도(Longitude)", value=126.90, key="longitude")

# 쿼리 파라미터 가져오기
query_params = st.experimental_get_query_params()

if "latitude" in query_params:
    my_latitude = float(query_params["latitude"][0])

if "longitude" in query_params:
    my_longitude = float(query_params["longitude"][0])

# 거리에 따른 점수를 부여하여 Distance Score 컬럼 업데이트
def calculate_distance_score(df, my_latitude, my_longitude):
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

    # 데이터 타입을 숫자로 변환
    df['Distance Score'] = df['Distance Score'].astype(int)
    df['Congestion Score'] = df['Congestion Score'].astype(int)


# 데이터 로드
df = load_data()

# 거리 점수 계산
calculate_distance_score(df, my_latitude, my_longitude)

# Final Score 컬럼 추가
df['Final Score'] = df["Distance Score"] - df["Congestion Score"]

# 추천하는 좌표 개수 설정
recommendations = min(3, len(df))  # 추천하는 좌표 개수를 원하는 값과 데이터프레임의 크기 중 작은 값으로 설정

# 거리 점수와 Final Score에 따라 추천하는 좌표 추출
df = df.sort_values(['Distance Score', 'Final Score'], ascending=[False, False])  # Distance Score와 Final Score에 따라 정렬
recommended_df = df.head(recommendations)  # 상위 추천 개수만큼 추출

# 지도 생성
tile_seoul_map = folium.Map(location=[my_latitude, my_longitude], zoom_start=16, tiles="Stamen Terrain")

# 내 위치 마커 추가
folium.Marker([my_latitude, my_longitude], popup="My Location", icon=folium.Icon(color='red')).add_to(tile_seoul_map)

has_recommended_coordinates = False
# 추천하는 좌표에 다른 색상의 마커로 추가
for i in range(len(recommended_df)):
    name, latitude, longitude = recommended_df.iloc[i][['name', 'latitude', 'longitude']]
    popup_text = f"Name: {name})"
    distance = haversine((my_latitude, my_longitude), (latitude, longitude), unit='m')
    if distance <= 200:  # 200m 이내인 경우에만 마커 추가
        has_recommended_coordinates = True
        folium.Marker([latitude, longitude], popup=popup_text, icon=folium.Icon(color='green')).add_to(tile_seoul_map)

        # 좌표 정보 출력
        st.write(f"{i+1} : {name}")

# 200미터 이내에 추천할 좌표가 없는 경우 메시지 출력
if not has_recommended_coordinates:
    st.warning("‼️ 200m 이내에 추천할 화장실이 없습니다.")

# HTML로 변환
map_html = tile_seoul_map.get_root().render()

# Streamlit 애플리케이션에 표시
st.title("Seoul Toilet Locations")
html(map_html, height=500)