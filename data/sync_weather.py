import urllib.request
import json
import os

WEATHER_URL = 'https://wttr.in/Victoria,BC?format=j1'
OUTPUT_FILE = "/home/codar/data/weather.txt"

def sync_weather():
    print("Fetching extended live weather data...")
    try:
        req = urllib.request.Request(WEATHER_URL, headers={'User-Agent': 'curl/7.68.0'})
        response = urllib.request.urlopen(req)
        
        # Convert the downloaded JSON data into a Python dictionary
        weather_data = json.loads(response.read().decode('utf-8'))
        
        # 1. Grab current conditions
        current_cond = weather_data['current_condition'][0]['weatherDesc'][0]['value']
        current_temp = weather_data['current_condition'][0]['temp_C']
        
        # 2. Grab tomorrow's temperatures (index 1 is tomorrow)
        tomorrow_max = weather_data['weather'][1]['maxtempC']
        tomorrow_min = weather_data['weather'][1]['mintempC']
        
        # 3. Grab tomorrow's weather condition. 
        # The 'hourly' array breaks the day into 3-hour chunks. Index 4 represents 12:00 PM (noon).
        tomorrow_cond = weather_data['weather'][1]['hourly'][4]['weatherDesc'][0]['value']
        
        # 4. Stitch it into an even better sentence!
        spoken_forecast = (
            f"The current weather is {current_cond} at {current_temp} degrees. "
            f"Tonight's low will drop to {tomorrow_min}. "
            f"Tomorrow will be {tomorrow_cond} with a high of {tomorrow_max} degrees."
        )
        
        # Save it to the text file
        with open(OUTPUT_FILE, 'w') as f:
            f.write(spoken_forecast)
            
        print(f"Success! Weather updated: {spoken_forecast}")

    except Exception as e:
        print(f"Error fetching weather: {e}")

if __name__ == "__main__":
    sync_weather()
