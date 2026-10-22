import os
import time
import requests
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POP_PATH = os.path.join(BASE_DIR, "..", "data", "population.csv")

# Load the population CSV
population_df = pd.read_csv(POP_PATH)

# Fix a sign error in the source file: Mexico City is in the northern hemisphere
population_df.loc[population_df["City"] == "Mexico City", "Latitude"] = 19.4326

print("Cities loaded:", len(population_df))

# Call the Open-Meteo API for every city
weather_rows = []
for _, location in population_df.iterrows():
    api_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={location['Latitude']}&longitude={location['Longitude']}&current_weather=true"
    )
    try:
        response = requests.get(api_url, timeout=10)
        response.raise_for_status()
        current = response.json()["current_weather"]
        weather_rows.append({
            "City": location["City"],
            "Temperature": current["temperature"],
            "Windspeed": current["windspeed"],
        })
    except Exception as error:
        print(f"Failed for {location['City']}: {error}")
    time.sleep(0.2)

print(f"Fetched weather for {len(weather_rows)} cities")
print(weather_rows[:5])
