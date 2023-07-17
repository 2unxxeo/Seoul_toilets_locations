from datetime import datetime
import pytz
import pandas as pd
import requests
import streamlit as st
import folium
from haversine import haversine
from streamlit.components.v1 import html


def load_data():
    # 데이터 로드
    df = pd.read_csv("https://roasample.cafe24.com/data/Seoul_locations_time_congestion_random.csv", encoding="utf-8")
    return df

def load_data1():
    # 데이터 로드
    df1 = pd.read_csv("https://roasample.cafe24.com/data/a.csv", encoding="utf-8")
    return df1

# 위치 정보 파라미터로 받아서 입력
query_params = st.experimental_get_query_params()

if "latitude" in query_params and "longitude" in query_params:
    if "latitude" in query_params:
        my_latitude = float(query_params["latitude"][0])

    if "longitude" in query_params:
        my_longitude = float(query_params["longitude"][0])
else:
    # 내 위치 정보를 설정
    my_latitude = st.sidebar.number_input("위도(Latitude)", value=37.5, key="latitude", format="%6f")
    my_longitude = st.sidebar.number_input("경도(Longitude)", value=126.90, key="longitude", format="%6f")


# 거리에 따른 점수를 부여하여 Distance Score 컬럼 업데이트
def calculate_distance_score(df, my_latitude, my_longitude):
    distance_scores = []
    for index, row in df.iterrows():
        point_latitude = row['latitude']
        point_longitude = row['longitude']

        # 내 위치와 데이터프레임의 위치 간의 거리를 계산 (위도, 경도 순서로 사용)
        distance = haversine((my_latitude, my_longitude), (point_latitude, point_longitude), unit='m')

        # 거리에 따라 점수 부여
        if distance <= 50:  # 50m 이내
            distance_scores.append(10)
        elif distance <= 100:  # 50m 초과 100m 이하
            distance_scores.append(8)
        elif distance <= 150:  # 100m 초과 150m 이하
            distance_scores.append(6)
        elif distance <= 200:  # 150m 초과 200m 이하
            distance_scores.append(4)
        elif distance <= 300:  # 200m 초과 300m 이하
            distance_scores.append(2)
        else:
            distance_scores.append(0)

    return distance_scores


# 데이터 로드
df = load_data()
df1 = load_data1()

if (df[['latitude', 'longitude']] == df1[['latitude', 'longitude']]).all().all():
    df['address'] = df1['address']

# 거리 점수 계산
df['Distance Score'] = calculate_distance_score(df, my_latitude, my_longitude)

# 거리 점수에 따라 추천하는 좌표 추출
df = df.sort_values('Distance Score', ascending=False)  # Distance Score에 따라 내림차순으로 정렬
recommended_df = df.head(10)  # 상위 10개 추출

# 현재 시간 가져오기
now = datetime.now()
korea_timezone = pytz.timezone("Asia/Seoul")
korea_time = now.astimezone(korea_timezone)
time_str = korea_time.strftime("%H")

# 상위 3개 추천할 거라고 가정
top_recommendations = 3

# 상위 10개 추천된 좌표에 대해 작업 수행
for index, row in recommended_df.iterrows():
    latitude = row['latitude']  # 위도 추출
    longitude = row['longitude']  # 경도 추출

    # 해당 좌표를 df에서 찾기
    coordinates_mask = (df['latitude'] == latitude) & (df['longitude'] == longitude)
    coordinate_row = df.loc[coordinates_mask].head(1)

    # time_str에 해당하는 컬럼값 가져오기
    column_value = coordinate_row[time_str].values[0]

    # Final Score 계산
    coordinate_row['Final Score'] = coordinate_row['Distance Score'] - column_value

    # 추천 결과에 추가
    recommended_df.loc[index, 'Final Score'] = coordinate_row['Final Score'].values[0]

# Final Score에 따라 내림차순으로 정렬하여 상위 3개 추천
final_recommendations = recommended_df.sort_values('Final Score', ascending=False).head(top_recommendations)

# 지도 생성
tile_seoul_map = folium.Map(location=[my_latitude, my_longitude], zoom_start=16, tiles="Stamen Terrain")

# 내 위치 마커 추가
folium.Marker([my_latitude, my_longitude], popup="My Location", icon=folium.Icon(color='red')).add_to(tile_seoul_map)

has_recommended_coordinates = False



dist = []
list = []
# 추천하는 좌표에 다른 색상의 마커로 추가 (상위 3개만)
for i in range(3):
    name, latitude, longitude, address = final_recommendations.iloc[i][['name', 'latitude', 'longitude', 'address']]
    popup_text = f"<div style='width: 200px;'>Name: {name} <br> Address: {address}</div>"
    distance = haversine((my_latitude, my_longitude), (latitude, longitude), unit='m')
    dist.append(int(distance))
    if distance <= 300:  # 300m 이내인 경우에만 마커 추가
        has_recommended_coordinates = True
        folium.Marker([latitude, longitude], popup=popup_text, icon=folium.Icon(color='green')).add_to(tile_seoul_map)

    list.append(f"{name} | 혼잡도: {final_recommendations.iloc[i][time_str]} | 거리: {dist[i]}m")

# HTML로 변환
map_html = tile_seoul_map.get_root().render()

# Streamlit 애플리케이션에 표시
st.title("Seoul Toilets Locations")
html(map_html, height=500)

# 좌표 정보 출력
css = """
    <style>
        @font-face {
            font-family: 'GoryeongStrawberry';
            src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2304-01@1.0/GoryeongStrawberry.woff2') format('woff2');
            font-weight: normal;
            font-style: normal;
        }
        .recommend {
            width : 100%;
            background : #F0F8FE;
            padding: 20px;
            padding-left : 30px;
            border-radius : 20px;
        }

        .recommend p{
            font-size: 22px;
            font-family : 'GoryeongStrawberry';
            color : #364150;
        }

        .red:first-child{
            color : red;
            font-size: 20px;
        }
    </style>
"""

st.markdown(css, unsafe_allow_html=True)
div_content = ""
for i in range(3):
    if i == 0:
        div_content += f"<p>{list[i]} &nbsp <span class='red'>힘내!</span></p>"
    else:
        div_content += f"<p>{list[i]}</p>"

styled_div = f"<div class='recommend'>{div_content}</div>"

# 300미터 이내에 추천할 좌표가 없는 경우 메시지 출력
if not has_recommended_coordinates:
    st.warning("‼️ 300m 이내에 추천할 화장실이 없습니다. 수풀로 ㄱㄱ")
else:
    st.markdown(styled_div, unsafe_allow_html=True)


# 카카오맵에서 주소 받아오기
# url = 'https://dapi.kakao.com/v2/local/geo/coord2address.json'
#
# df['address'] = ''
#
# headers = {'Authorization': 'KakaoAK {}'.format('6ba25524c4e2e89c413a3b1ecb9d23c1')}
#
# for index, row in df.iterrows():
#     latitude = row['latitude']
#     longitude = row['longitude']
#
#     if latitude and longitude:
#         params = {'x': longitude, 'y': latitude}
#         response = requests.get(url, headers=headers, params=params)
#         data = response.json()
#
#         # 응답에서 주소 정보 추출
#         documents = data.get('documents', [])
#
#         if documents:
#             address = documents[0].get('address', {}).get('address_name', '')
#             df.loc[index, 'address'] = address
#         else:
#             df.loc[index, 'address'] = '주소를 찾을 수 없음'
#
# df[['latitude', 'longitude', 'address']].to_csv('di.csv', index=False)
# st.write(df[['latitude', 'longitude', 'address']].head())

