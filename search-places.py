import googlemaps
from datetime import datetime
import json
import pandas as pd
import time
from pandas import json_normalize
import os.path
import xlsxwriter

## SETTINGS
############################

# Needs Geocoding API and Places API enabled.
#   https://console.cloud.google.com/google/maps-apis/credentials
google_api_key = 'YOUR_API_KEY'

# Address to center search at.
search_around_address = ''

# What type of businesses to search for
#   https://developers.google.com/maps/documentation/places/web-service/supported_types
search_for = ''

# Limit pages.  To avoid overages, set a value here
limit_pages = 100

# Set to True if you don't want to make ANY google API calls.
# Will attempt to parse local files if they exist
no_requests = False

if not google_api_key:
    print("You must provide a Google API Key")
    exit()

if not search_around_address:
    print("You must provide an address to search near")
    exit()

if not search_for:
    print("You must provide a category to search for")
    exit()

def get_places_nearby(location, search_for, next_page_token):

    if not no_requests:
        places_json = gmaps.places_nearby(
                    location        = location,
                    keyword         = search_for,
                    rank_by         = "distance",
                    page_token = next_page_token,
        )

        return places_json

def get_place_details(place_id):

    if not no_requests:
        place_details_json = gmaps.place(
                    place_id = place_id,
                    fields   = (
                        'name',
                        'address_component',
                        'formatted_address',
                        'formatted_phone_number'
                    ),
        )

        return place_details_json

# Create googlemaps object
gmaps = googlemaps.Client(key=google_api_key)
dataframe = pd.DataFrame()

# Set data dir
data_dir = f"./data/{search_for}/{search_around_address}"

if not os.path.exists(data_dir):
    os.makedirs(data_dir)

if os.path.isfile(f"{data_dir}/places_1.json"):

    i = 1
    next_page_token = ''
    while (1):

        # Open local cached file (avoid fees while testing!)
        with open(f'{data_dir}/places_{i}.json') as json_file:
            places_json = json.load(json_file)

        # "Normalize" our json
        places_json_normalized = json_normalize(places_json, "results")
        dataframe = dataframe.append(pd.DataFrame.from_dict(places_json_normalized))

        i += 1

        if not os.path.isfile(f"{data_dir}/places_{i}.json"):
            break

else:

    if not no_requests:
        # Geocode address
        geocode_result = gmaps.geocode(search_around_address)
        location = geocode_result[0]['geometry']['location']

    i = 1
    next_page_token = ''

    while (1):

        # Perform a new request
        places_json = get_places_nearby(location, search_for, next_page_token)

        # Save the JSON locally so that we can open it again (for testing)
        with open(f"{data_dir}/places_{i}.json", 'w') as outfile:
            json.dump(places_json, outfile)

        # "Normalize" our json
        places_json_normalized = json_normalize(places_json, "results")
        dataframe = dataframe.append(pd.DataFrame.from_dict(places_json_normalized))

        # Look for a next page token
        if "next_page_token" in places_json:
            next_page_token = places_json['next_page_token']

            # Wait 4 seconds  ( There is a short delay between when a next_page_token is
            # issued, and when it will become valid. Requesting the next page before it is
            # available will return an INVALID_REQUEST response )
            time.sleep(4)

        else:
            next_page_token = ''

        i += 1

        if not next_page_token or i >= limit_pages:
            break

# Create a workbook and add a worksheet.
workbook = xlsxwriter.Workbook(f"{data_dir}/GooglePlacesData.xlsx")
worksheet = workbook.add_worksheet()

row_count = 0

worksheet.write(row_count, 0, 'PLACE_ID')
worksheet.write(row_count, 1, 'NAME')
worksheet.write(row_count, 2, 'ADDRESS')
worksheet.write(row_count, 3, 'PHONE')
worksheet.write(row_count, 4, 'BUSINESS_STATUS')

for row in dataframe.sort_values(by=['name']).itertuples():

    place_id = getattr(row, 'place_id')
    name = getattr(row, 'name')
    business_status = getattr(row, 'business_status')

    print(f"[{place_id}] {name}")

    place_details_json = ''

    if os.path.isfile(f"{data_dir}/place_details_{place_id}.json"):

        # Open local cached file (avoid fees while testing!)
        with open(f"{data_dir}/place_details_{place_id}.json") as json_file:
            place_details_json = json.load(json_file)

    else:

        if not no_requests:
            place_details_json = get_place_details(place_id)

            # # Save the JSON locally so that we can open it again (for testing)
            with open(f"{data_dir}/place_details_{place_id}.json", 'w') as outfile:
                json.dump(place_details_json, outfile)

    row_count += 1

    address = ''
    phone = ''

    if 'result' in place_details_json:
        if 'formatted_address' in place_details_json["result"]:
            address = place_details_json["result"]["formatted_address"]

        if 'formatted_phone_number' in place_details_json["result"]:
            phone = place_details_json["result"]["formatted_phone_number"]

    worksheet.write(row_count, 0, place_id)
    worksheet.write(row_count, 1, name)
    worksheet.write(row_count, 2, address)
    worksheet.write(row_count, 3, phone)
    worksheet.write(row_count, 4, business_status)

workbook.close()