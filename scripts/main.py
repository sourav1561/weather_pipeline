import os
import time
import requests
import pandas as pd

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
POP_PATH = os.path.join(BASE_DIR, "..", "data", "population.csv")

# Load the population CSV
population_df = pd.read_csv(POP_PATH)
population_df = population_df.head(50)

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
        response = None
        for attempt in range(3):  # retry up to 3 times on server errors
            response = requests.get(api_url, timeout=10)
            if response.status_code == 200:
                break
            time.sleep(2)
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

# ---------- Task 3.2: Convert API results to a DataFrame and merge ----------
weather_df = pd.DataFrame(weather_rows)
merged_df = pd.merge(population_df, weather_df, on="City", how="inner")

print("Rows after merge:", len(merged_df))
print(merged_df.head(10))

# ---------- Task 3.3: Data cleaning and normalization ----------
clean_df = merged_df.copy()

print("Null values before cleaning:")
print(clean_df.isnull().sum())

# Convert numeric columns (invalid values become NaN)
clean_df["Population"] = pd.to_numeric(clean_df["Population"], errors="coerce")
clean_df["Temperature"] = pd.to_numeric(clean_df["Temperature"], errors="coerce")
clean_df["Windspeed"] = pd.to_numeric(clean_df["Windspeed"], errors="coerce")

# Remove rows that are missing essential values
clean_df = clean_df.dropna(subset=["Country", "City", "Population", "Temperature"])

# Missing text values get the word "null"
for col in clean_df.columns:
    if not pd.api.types.is_numeric_dtype(clean_df[col]):
        clean_df[col] = clean_df[col].fillna("null")

# Enforce explicit data types
clean_df["Population"] = clean_df["Population"].astype("int64")
clean_df["Temperature"] = clean_df["Temperature"].astype("float64")
clean_df["Windspeed"] = clean_df["Windspeed"].astype("float64")

# Derived columns: Fahrenheit and a Cold/Mild/Hot category
clean_df["Temperature_F"] = (clean_df["Temperature"] * 9 / 5 + 32).round(1)
clean_df["Temperature_Category"] = pd.cut(
    clean_df["Temperature"],
    bins=[-100, 10, 25, 100],
    labels=["Cold", "Mild", "Hot"],
    right=False,
).astype(str)

print("Null values after cleaning:")
print(clean_df.isnull().sum())
print(clean_df.dtypes)
print(clean_df[["City", "Country", "Population", "Temperature", "Temperature_F", "Temperature_Category"]].head(10))
print(clean_df["Temperature_Category"].value_counts())
print("Final row count:", len(clean_df))

# ---------- Task 4.3: Load into BigQuery ----------
from google.cloud import bigquery
from google.oauth2 import service_account

PROJECT_ID = "tensile-sorter-512407-e9"
KEY_PATH = os.path.join(BASE_DIR, "gcp-key.json")
TABLE_ID = f"{PROJECT_ID}.global_weather_data.current_weather_stats"

credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
client = bigquery.Client(credentials=credentials, project=PROJECT_ID)

# WRITE_TRUNCATE replaces the table each run, so rows never duplicate
job_config = bigquery.LoadJobConfig(write_disposition="WRITE_TRUNCATE")
load_job = client.load_table_from_dataframe(clean_df, TABLE_ID, job_config=job_config)
load_job.result()  # wait for the load to finish
print(f"Loaded {load_job.output_rows} rows into {TABLE_ID}")
