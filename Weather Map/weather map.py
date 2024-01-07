# standard
import json

# third-party
import folium
import requests as api_request

from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError

from selenium import webdriver

from http.server import BaseHTTPRequestHandler, HTTPServer

# config setup
from config import API_KEY, BASE_URL, FOLIUM_PORT, STARTUP_COORDS, STARTUP_ZOOM, MAP_FILEPATH, PROJECT_FILEPATH, JSON_COORD_FILEPATH


# API methods
def weather_request(BASE_URL, API_KEY, coords):
    # coords updates on each map click. use negative indexing (-1) to specifiy last element in list
    latitude = coords[-1]["latitude"]
    longitude = coords[-1]["longitude"]

    valid, city, state, country = valid_location(str(coords[-1]["latitude"]), str(coords[-1]["longitude"]))

    if valid:
        # compile request
        url = f"{BASE_URL}lat={latitude}&lon={longitude}&appid={API_KEY}"
        response = api_request.get(url).json()

        # make human readable
        sanitize_weather(response, latitude, longitude, city, state, country)


def sanitize_weather(response, latitude, longitude, city, state, country):
    temp_kelvin = response['main']['temp']
    temp_celsius, temp_fahrenheit = kelvin_to_celsius_fahrenheit(temp_kelvin)

    feels_like_kelvin = response['main']['feels_like']
    feels_like_celsius, feels_like_fahrenheit = kelvin_to_celsius_fahrenheit(feels_like_kelvin)
    # wind_speed = response['wind']['speed']

    humidity = response['main']['humidity']
    description = response['weather'][0]['description']
    # sunrise_time = dt.datetime.utcfromtimestamp(response['sys']['sunrise'] + response['timezone'])
    # sunset_time = dt.datetime.utcfromtimestamp(response['sys']['sunset'] + response['timezone'])

    comma1 = ', '
    comma2 = ', '

    if city == '':
        comma1 = ''
    if state == '':
        comma2 = ''

    location = f'{city}{comma1}{state}{comma2}{country}'

    print(f"Temparature in {location}: {temp_celsius:.2f} degrees Celsius or {temp_fahrenheit:.2f} degrees Fahrenheit.")
    print(f"Temperature in {location} feels like: {feels_like_celsius:.2f} degrees Celsius.")
    print(f"Humidity in {location}: {humidity}%")
    # print(f"Wind Speed in {LOCATION}: {wind_speed} m/s")
    print(f"General Weather in {location}: {description}")
    # print(f"Sun rises in {LOCATION} at {sunrise_time} local time.")
    # print(f"Sun sets in {LOCATION} at {sunset_time} local time.")


def kelvin_to_celsius_fahrenheit(kelvin):
    celsius = kelvin - 273.15
    fahrenheit = celsius * (9 / 5) + 32
    return celsius, fahrenheit


def valid_location(latitude, longitude):
    # try catch for errors
    try:
        location = geolocator.reverse(latitude + ", " + longitude)

        # if location not None
        if location and location.raw.get('address'):

            address = location.raw['address']
            city = address.get('city', '')
            state = address.get('state', '')
            country = address.get('country', '')

            # return valid, city, state, country
            return True, city, state, country
        else:
            print("Location not found.")
            # return valid, None, None, None
            return False, '', '', ''
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"error: {e}")
        return False, '', '', ''


# find folium-map.html index at which to insert
def find_head_index(html):

    pattern = "</head>"
    starting_index = html.find(pattern)

    return starting_index


# find the starting and ending index of latLngPop function (marker popup function)
def find_popup_slice(html):

    pattern = "function latLngPop(e)"

    # starting index
    starting_index = html.find(pattern)

    # cut off everything in front of latLngPop(E)
    tmp_html = html[starting_index:]

    # loop through opening and closing brackets
    found = 0
    index = 0
    opening_found = False
    while not opening_found or found > 0:
        if tmp_html[index] == "{":
            found += 1
            opening_found = True
        elif tmp_html[index] == "}":
            found -= 1

        index += 1

    # determine the ending index of popup function
    ending_index = starting_index + index

    return starting_index, ending_index


# find the map codes that change on refresh
def find_variable_name(html, name_start):
    variable_pattern = "var "

    pattern = variable_pattern + name_start

    starting_index = html.find(pattern) + len(variable_pattern)  # length of "var " in pattern
    tmp_html = html[starting_index:]
    ending_index = tmp_html.find(" =") + starting_index

    return html[starting_index:ending_index]


# inject custom popup botton to get weather
def custom_code(popup_variable_name, map_variable_name, FOLIUM_PORT):
    return '''
            // custom injected code
            function latLngPop(e) {
                %s
                    .setLatLng(e.latlng)
                    .setContent(`
                    <div class = "popup-container">
                        <p class="popup-title"> Coordinates: </p>
                        <p class="popup-coordinates">
                            Lat: ${e.latlng.lat.toFixed(5)}, Long: ${e.latlng.lng.toFixed(5)}
                        </p>
                            // send latitude and longitude over HTTP POST
                            <button class="popup-button"
                                onClick="
                                fetch('http://localhost:%s', {
                                    method: 'POST',
                                    mode: 'no-cors',
                                    headers: {
                                        'Accept': 'application/json',
                                        'Content-Type': 'application/json'
                                    },
                                    body: JSON.stringify({
                                        latitude: ${e.latlng.lat},
                                        longitude: ${e.latlng.lng}
                                    })
                                });
                                // code to add a marker
                                L.marker(
                                    [${e.latlng.lat.toFixed(5)}, ${e.latlng.lng.toFixed(5)}],
                                    {}
                                ).addTo(%s);
                            "> Get Weather </button>
                            // send quit char over HTTP POST
                            <button class="quit-button"
                                onClick="
                                fetch('http://localhost:%s', {
                                    method: 'POST',
                                    mode: 'no-cors',
                                    headers: {
                                        'Accept': 'application/json',
                                        'Content-Type': 'application/json'
                                    },
                                    body: 'q'
                                });
                            "> Quit </button>
                    </div>
                    `)
                    .openOn(%s);
            }
            // end custom code
    ''' % (popup_variable_name, FOLIUM_PORT, map_variable_name, FOLIUM_PORT, map_variable_name)


# create the folium map and insert the custom code for css stylesheet and get weather popup
def create_folium_map(MAP_FILEPATH, STARTUP_COORDS, FOLIUM_PORT, STARTUP_ZOOM):
    # create folium map
    vmap = folium.Map(STARTUP_COORDS, STARTUP_ZOOM)

    # add popup
    folium.LatLngPopup().add_to(vmap)

    # store the map to a file
    vmap.save(MAP_FILEPATH)

    # read the folium file
    html = None
    with open(MAP_FILEPATH, 'r') as mapfile:
        html = mapfile.read()

    # find variable names
    # "map_" and "lat_lng_popup_" are specific keywords in the html file
    map_variable_name = find_variable_name(html, "map_")
    popup_variable_name = find_variable_name(html, "lat_lng_popup_")

    # determine popup function indices
    pstart, pend = find_popup_slice(html)

    # string literal
    custom_css_link = '''    <link href="styles.css" rel="stylesheet">
'''
    css_index = find_head_index(html)

    # inject code
    with open(MAP_FILEPATH, 'w') as mapfile:
        mapfile.write(
            html[:css_index] +
            custom_css_link +
            html[css_index:pstart] +
            custom_code(popup_variable_name, map_variable_name, FOLIUM_PORT) +
            html[pend:]
        )


# open the folium map using selenium
def open_folium_map(PROJECT_FILEPATH, MAP_FILEPATH):
    driver = None
    # this can fail
    # requires specific chromedriver for chrome version
    try:
        driver = webdriver.Chrome()
        driver.get(
            PROJECT_FILEPATH + MAP_FILEPATH
        )
    except Exception as ex:
        print(f"Driver failed to open/find url: {ex}")

    return driver


# close the folium map
def close_folium_map(driver):
    try:
        driver.close()
    except Exception as ex:
        print(f"error: {ex}")


# folium server to send coordinates over HTTP
class FoliumServer(BaseHTTPRequestHandler):
    # overwriting default _set_response(self)
    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    # overwriting default do_POST(self)
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)

        # decode post_data (bytes) to utf-8
        data = post_data.decode("utf-8")

        # check for quit char
        if data.lower() == 'q':
            raise KeyboardInterrupt("Intended exception to exit webserver")
        else:
            print(data)

        # store coords to json
        # convert string data to actual json
        coords.append(json.loads(data))

        # http request status/info
        # prevents resending information
        self._set_response()

        # api weather request
        weather_request(BASE_URL, API_KEY, coords)


# listen for coords
def listen_to_folium_map(port):
    server_address = ('localhost', port)
    httpd = HTTPServer(server_address, FoliumServer)
    print("Server opened ...")
    # have server listen indefinitely until quit char
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass

    httpd.server_close()
    print("Server closed")


if __name__ == "__main__":
    # create folium variables
    coords = []

    # initilalize Nominatim API
    geolocator = Nominatim(user_agent = "InteractiveWeatherMap")

    # create folium map
    create_folium_map(MAP_FILEPATH, STARTUP_COORDS, FOLIUM_PORT, STARTUP_ZOOM)

    # open the folium map (selenium)
    driver = open_folium_map(PROJECT_FILEPATH, MAP_FILEPATH)

    # run webserver that listens to sent coordinates
    listen_to_folium_map(FOLIUM_PORT)

    # close the folium map
    close_folium_map(driver)

    # save coords to json file
    json.dump(coords, open(JSON_COORD_FILEPATH, 'w'))
