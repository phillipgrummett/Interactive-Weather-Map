import os

# OpenWeatherMap API - OpenWeatherMap.org
API_KEY = open('api_key.txt', 'r').read()
BASE_URL = "http://api.openweathermap.org/data/2.5/weather?"

# default folium variables
FOLIUM_PORT = 3001
STARTUP_COORDS = [31.083180198360026, 9.307220072053097]
STARTUP_ZOOM = 3
MAP_FILEPATH = "folium-map.html"

# default project filepath
script_dir = os.path.dirname(os.path.abspath(__file__))
relative_path = "./"
PROJECT_FILEPATH = os.path.join(script_dir, relative_path)

JSON_COORD_FILEPATH = "coords.json"
