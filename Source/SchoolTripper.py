import webview
import json
import requests
from openai import OpenAI

google_api_key = ""
openai_api_key = ""

class API:
    def __init__(self):
        self.corrected_country = None
        self.corrected_city = None
        self.date = None
        self.kids = None
        self.restaurant_cache = {}
        self.menu_cache = {}
        self.openai_client = OpenAI(api_key=openai_api_key)

    def set_country_data(self, country):
        self.corrected_country, _ = self.get_place_correction(country, google_api_key)
        return {"country": self.corrected_country}

    def set_city_data(self, city):
        self.corrected_city, _ = self.get_place_correction(city, google_api_key)
        return {"city": self.corrected_city}

    def set_date_data(self, date):
        self.date = date
        return {"date": self.date}

    def get_place_correction(self, input_text, api_key):
        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.location"
        }
        data = {"textQuery": input_text}
        response = requests.post(url, headers=headers, data=json.dumps(data))
        if response.status_code == 200:
            results = response.json().get("places", [])
            if results:
                return results[0]["displayName"]["text"], results[0]["location"]
        return None, None

    def get_place_photo_url(self, photo_reference, api_key):
        return f"https://places.googleapis.com/v1/{photo_reference}/media?key={api_key}&max_width_px=400"

    def get_hostel_info(self):
        if self.corrected_country and self.corrected_city:
            hostels = self.find_hostels(self.corrected_country, self.corrected_city, google_api_key)
            hostel_prices = []
            for h in hostels:
                price = self.get_hotel_price(h["name"], self.corrected_city, self.corrected_country)
                hostel_prices.append(price)
            result = {
                "names": [h["name"] for h in hostels],
                "ratings": [h["rating"] for h in hostels],
                "photo_urls": [h["photo_url"] for h in hostels],
                "prices": hostel_prices
            }
            return result
        return {"names": [], "ratings": [], "photo_urls": [], "prices": []}

    def find_hostels(self, country, city, api_key):
        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.rating,places.photos"
        }
        query = f"hostel, student accommodation or hotel in {city}, {country}"
        data = {
            "textQuery": query,
            "maxResultCount": 3
        }
        response = requests.post(url, headers=headers, json=data)
        results = response.json().get("places", [])
        hostels = []
        for place in results:
            name = place.get("displayName", {}).get("text", "Nincs ilyen hotel")
            rating = place.get("rating", "")
            photo_url = ""
            if place.get("photos"):
                photo_reference = place["photos"][0].get("name", "")
                photo_url = self.get_place_photo_url(photo_reference, api_key)
            hostels.append({
                "name": name,
                "rating": rating,
                "photo_url": photo_url
            })
        return hostels

    def get_hotel_price(self, hotel_name, city, country):
        system_prompt = (
            "You are a Hotel price assistant. Your job is to provide the user with the price for one room for one night. The user will provide:\n\n"
            "{The name of a Hotel} {The hotels location country} {The hotels location city}\n\n"
            "--------------------------------------\n"
            "Follow these rules exactly:\n"
            "1. Only output the price for an adult for one night in one room in HUF.\n"
            "2. Use this format only:{room price in HUF}Ft\n"
            "3. Do not write any other text, explanation, or additional information.\n"
            "4. If the price is not available and only then you can make up a price that would make sense for a hostel.\n"
            "5. Room prices must have no spaces or periods (e.g., 5000Ft NOT 5.000 Ft or 5 000Ft).\n"
            "7. Never add more lines, text, or context.\n"
            "Follow these format and output rules without exception for every answer.\n"
            "------------------------------------\n"
            "Here is an example which you should not under any circumstances deviate from:\n"
            "USER: Test Hostel Hungary Budapest\n"
            "ASSISTANT: 5500Ft\n"
        )
        user_prompt = f"{hotel_name} {country} {city}"
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=20,
                temperature=1,
            )
            result = response.choices[0].message.content.strip()
            return result
        except Exception as e:
            return "Nem található ár."

    def get_restaurants_near_hostel(self, hostel_name, city, country, api_key):
        cache_key = (hostel_name, city, country)
        if cache_key in self.restaurant_cache:
            return self.restaurant_cache[cache_key]

        url = "https://places.googleapis.com/v1/places:searchText"
        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": api_key,
            "X-Goog-FieldMask": "places.displayName,places.rating,places.photos"
        }
        query = f"restaurant near {hostel_name}, {city}, {country}"
        data = {"textQuery": query, "maxResultCount": 4}
        response = requests.post(url, headers=headers, json=data)
        results = response.json().get("places", [])
        restaurants = []
        for place in results:
            name = place.get("displayName", {}).get("text", "N/A")
            rating = place.get("rating", "N/A")
            photo_url = ""
            if place.get("photos"):
                photo_reference = place["photos"][0].get("name", "")
                photo_url = self.get_place_photo_url(photo_reference, api_key)
            restaurants.append({
                "name": name,
                "rating": rating,
                "photo_url": photo_url
            })
        self.restaurant_cache[cache_key] = restaurants
        return restaurants

    def get_restaurants_for_hostel(self, hostel_index):
        hostels = self.find_hostels(self.corrected_country, self.corrected_city, google_api_key)
        if 0 <= hostel_index < len(hostels):
            hostel = hostels[hostel_index]
            return self.get_restaurants_near_hostel(
                hostel['name'], self.corrected_city, self.corrected_country, google_api_key
            )
        return []

    def get_restaurant_menu(self, restaurant_name, city, country):
        cache_key = (restaurant_name, city, country)
        if cache_key in self.menu_cache:
            return self.menu_cache[cache_key]

        system_prompt = (
            "You are a restaurant menu assistant. Your job is to provide the user with 5 different types of meals and their prices from the restaurant the user gives the name for. "
            "The user will provide:\n\n"
            "{The name of a restaurant} {The restaurants location country} {The restaurants location city}\n\n"
            "--------------------------------------\nFollow these rules:\n\n"
            "1. Only answer with the 5 items from the menu.\n"
            "2. Don't answer with any other text other than the 5 items and their prices.\n"
            "3. The first food item should be something that has some kind of pasta in it. The second food item should be something with meat in it. "
            "The third food item should be something that doesn't have meat in it. The fourth food item should be some kind of soup. The fifth food item should be some kind of dessert.\n"
            "4. If you can't find any of the types of food mentioned in rule 3 they can be replaced with anything else from the menu.\n"
            "5. If the restaurants menu isn't available answer with \"Nem találhatóak az adatok.\"\n"
            "6. If you have to use rule 5 then that should be the only text in your answer.\n"
            "7. The price of the food should never contain any spacers. For example it should always be 5000Ft instead of 5.000Ft\n\n"
            "--------------------------------------\nYou should always format your answer this way:\n\n"
            "1. {Name of food item in Hungarian};{Price of food item in hungarian forints}\n"
            "2. {Name of food item in Hungarian};{Price of food item in hungarian forints}\n"
            "3. {Name of food item in Hungarian};{Price of food item in hungarian forints}\n"
            "4. {Name of food item in Hungarian};{Price of food item in hungarian forints}\n"
            "5. {Name of food item in Hungarian};{Price of food item in hungarian forints}\n"
        )
        user_prompt = f"{restaurant_name} {country} {city}"

        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=512,
                temperature=1,
                top_p=1,
            )
            menu_raw = response.choices[0].message.content
        except Exception as e:
            return [{"name": "Nem találhatóak az adatok.", "price": ""}] * 5

        items = []
        if "Nem találhatóak az adatok." in menu_raw:
            items = [{"name": "Nem találhatóak az adatok.", "price": ""}] * 5
        else:
            lines = [line for line in menu_raw.strip().split("\n") if line.strip()]
            for line in lines[:5]:
                try:
                    idx, rest = line.split('.', 1)
                    name, price = rest.split(';')
                    items.append({"name": name.strip(), "price": price.strip()})
                except Exception:
                    items.append({"name": line.strip(), "price": ""})
            while len(items) < 5:
                items.append({"name": "Nem találhatóak az adatok.", "price": ""})

        self.menu_cache[cache_key] = items
        return items

    def get_restaurant_menu_js(self, restaurant_index, hotel_index):
        hostels = self.find_hostels(self.corrected_country, self.corrected_city, google_api_key)
        if 0 <= hotel_index < len(hostels):
            hostel = hostels[hotel_index]
            restaurants = self.get_restaurants_near_hostel(
                hostel['name'], self.corrected_city, self.corrected_country, google_api_key)
            if 0 <= restaurant_index < len(restaurants):
                restaurant = restaurants[restaurant_index]
                return self.get_restaurant_menu(
                    restaurant['name'], self.corrected_city, self.corrected_country
                )
        return [{"name": "Nem találhatóak az adatok.", "price": ""}] * 5

def create_window():
    api = API()
    window = webview.create_window("School Tripper", "./assets/index.html", js_api=api, width=1152, height=648)
    webview.start()

if __name__ == "__main__":
    create_window()