import os
import requests
from flask import Flask, render_template, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# Open-Meteo API endpoints
GEOCODE_URL = "https://geocoding-api.open-meteo.com/v1/search"
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/weather')
def get_weather():
    lat = request.args.get('lat')
    lon = request.args.get('lon')
    city = request.args.get('city', '')
    
    if not lat or not lon:
        return jsonify({'error': 'Please provide latitude and longitude.'}), 400

    try:
        # Get weather from Open-Meteo
        params = {
            'latitude': lat,
            'longitude': lon,
            'current': 'temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m',
            'daily': 'weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max',
            'timezone': 'auto',
            'forecast_days': 7
        }
        
        resp = requests.get(WEATHER_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # Get location name if not provided
        if not city:
            city = get_location_name(lat, lon)

        # Transform Open-Meteo data to our dashboard format
        formatted_data = format_weather_data(data, city)
        return jsonify(formatted_data)
        
    except requests.exceptions.RequestException as e:
        return jsonify({'error': f'Weather API Error: {str(e)}'}), 500

def get_location_name(lat, lon):
    """Reverse geocode to get city name"""
    try:
        params = {'latitude': lat, 'longitude': lon, 'count': 1}
        resp = requests.get(GEOCODE_URL, params=params, timeout=5)
        resp.raise_for_status()
        results = resp.json().get('results', [])
        if results:
            return results[0].get('name', 'Unknown')
    except:
        pass
    return 'Unknown Location'

def format_weather_data(data, city):
    """Convert Open-Meteo response to our dashboard format"""
    
    current = data.get('current', {})
    daily = data.get('daily', {})
    
    # Weather code mapping (Open-Meteo to human-readable)
    weather_codes = {
        0: 'Clear Sky',
        1: 'Mostly Clear',
        2: 'Partly Cloudy',
        3: 'Overcast',
        45: 'Fog',
        51: 'Light Drizzle',
        53: 'Moderate Drizzle',
        55: 'Heavy Drizzle',
        61: 'Light Rain',
        63: 'Moderate Rain',
        65: 'Heavy Rain',
        71: 'Light Snow',
        73: 'Moderate Snow',
        75: 'Heavy Snow',
        80: 'Light Rain Showers',
        81: 'Moderate Rain Showers',
        82: 'Heavy Rain Showers',
        95: 'Thunderstorm'
    }
    
    # Current weather
    weather_code = current.get('weather_code', 0)
    condition = weather_codes.get(weather_code, 'Unknown')
    
    # Format current
    formatted_current = {
        'temp': current.get('temperature_2m', '--'),
        'feels_like': current.get('apparent_temperature', '--'),
        'humidity': current.get('relative_humidity_2m', '--'),
        'wind_speed': current.get('wind_speed_10m', '--'),
        'condition': condition,
        'precipitation': current.get('precipitation', 0),
        'unit': 'metric'
    }
    
    # Format forecast (7 days)
    formatted_forecast = []
    for i in range(len(daily.get('time', []))):
        date = daily['time'][i]
        weather_code = daily['weather_code'][i] if i < len(daily['weather_code']) else 0
        condition = weather_codes.get(weather_code, 'Unknown')
        
        # Convert date to readable format
        date_obj = datetime.fromisoformat(date)
        date_str = date_obj.strftime('%a %b %d')
        
        formatted_forecast.append({
            'date': date_str,
            'condition': condition,
            'high': daily['temperature_2m_max'][i] if i < len(daily['temperature_2m_max']) else '--',
            'low': daily['temperature_2m_min'][i] if i < len(daily['temperature_2m_min']) else '--',
            'precipitation_probability': daily['precipitation_probability_max'][i] if i < len(daily['precipitation_probability_max']) else 0
        })
    
    # Generate AI-like summary (since we don't have Gemini)
    ai_summary = generate_ai_summary(formatted_current, formatted_forecast)
    
    # Generate smart recommendations
    recommendations = generate_recommendations(formatted_current, formatted_forecast)
    
    return {
        'location': {
            'name': city,
            'country': ''
        },
        'current': formatted_current,
        'forecast': formatted_forecast,
        'ai_summary': ai_summary,
        'recommendations': recommendations,
        'rate_limit': {
            'limit': 'Unlimited',
            'remaining': 'Unlimited'
        }
    }

def generate_ai_summary(current, forecast):
    """Generate a dynamic AI-like weather summary"""
    temp = current.get('temp', 20)
    condition = current.get('condition', 'Unknown')
    humidity = current.get('humidity', 50)
    
    # Determine weather vibe
    if temp > 30:
        vibe = "hot and sunny"
    elif temp > 20:
        vibe = "warm and pleasant"
    elif temp > 10:
        vibe = "cool and comfortable"
    else:
        vibe = "cold and chilly"
    
    # Check for rain in forecast
    rain_days = [day for day in forecast if day.get('precipitation_probability', 0) > 50]
    
    summary = f"Today's weather is {vibe} with {condition.lower()}. "
    
    if rain_days:
        days_str = ', '.join([day['date'] for day in rain_days[:3]])
        summary += f"Rain is expected on {days_str}. "
    else:
        summary += "No rain is expected in the coming days. "
    
    if humidity > 70:
        summary += "High humidity may make it feel warmer. "
    elif humidity < 30:
        summary += "Low humidity - stay hydrated! "
    
    return summary

def generate_recommendations(current, forecast):
    """Generate smart recommendations based on weather"""
    recs = []
    temp = current.get('temp', 20)
    condition = current.get('condition', '')
    precipitation = current.get('precipitation', 0)
    
    # Check rain now
    if precipitation and precipitation > 2:
        recs.append('☔ Carry an umbrella - rain is falling now.')
    elif 'Rain' in condition or 'Drizzle' in condition:
        recs.append('☔ Light rain expected - bring an umbrella.')
    
    # Check for rain in forecast
    rain_days = [day for day in forecast if day.get('precipitation_probability', 0) > 60]
    if rain_days:
        days_str = ', '.join([day['date'] for day in rain_days[:3]])
        recs.append(f'🌧️ Rain expected on {days_str}. Plan outdoor activities accordingly.')
    
    # Check for no rain
    if not rain_days and not condition.lower() in ['rain', 'drizzle']:
        recs.append('☀️ No rain expected. Great time for outdoor activities!')
    
    # Temperature recommendations
    if temp > 30:
        recs.append('🥵 High temperature! Stay hydrated and avoid direct sun.')
    elif temp > 25:
        recs.append('🌤️ Pleasant warm weather - enjoy your day!')
    elif temp < 10:
        recs.append('🥶 Chilly out there! Wear warm layers.')
    
    # Humidity
    humidity = current.get('humidity', 50)
    if humidity > 80:
        recs.append('💨 High humidity - it might feel stickier than the actual temperature.')
    
    # Wind
    wind = current.get('wind_speed', 0)
    if wind > 30:
        recs.append('💨 Strong winds today. Secure any loose items.')
    
    if not recs:
        recs.append('✅ Conditions look stable. Enjoy your day!')
    
    return recs

if __name__ == '__main__':
    app.run(debug=True, port=5000)