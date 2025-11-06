from flask import Flask, request, jsonify, render_template, make_response
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
import requests
import datetime
import json
import csv
from io import StringIO

# Try to import config, use defaults if not available
try:
    from config import GOOGLE_MAPS_API_KEY
except ImportError:
    GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY_HERE"

app = Flask(__name__)

# MongoDB Configuration
app.config["MONGO_URI"] = "mongodb://localhost:27017/weather_app"
mongo = PyMongo(app)

# --- New: safe helper to get a MongoDB collection ---
def get_collection_safe(name):
    """
    Return the specified collection object. If the database is not initialized,
    return None. Callers should check the return value and respond with a
    500 error or an appropriate message when None is returned.
    """
    # Prefer the initialized `mongo.db` when available
    db = getattr(mongo, 'db', None)
    # `pymongo.database.Database` does not support truth-value testing
    # (bool(db) raises NotImplementedError). Compare explicitly with None.
    if db is not None:
        return getattr(db, name, None)

    # Fallback: try to obtain the database from the underlying pymongo client
    client = getattr(mongo, 'cx', None) or getattr(mongo, 'client', None)
    # Similarly, avoid truth-value testing on client; check for None instead.
    if client is not None:
        # Try to infer the database name from configuration
        db_name = app.config.get('MONGO_DBNAME') or app.config.get('MONGO_URI', '').rsplit('/', 1)[-1]
        try:
            if db_name:
                return client[db_name][name]
        except Exception:
            return None

    return None

# --- Helper Functions ---
def validate_date(date_str):
    try:
        datetime.datetime.strptime(date_str, '%Y-%m-%d')
        return True
    except ValueError:
        return False

def get_location_coords(location):
    """Geocode location to get latitude and longitude."""
    # Check if location is already in lat,lon format
    if ',' in location:
        try:
            parts = location.split(',')
            lat = float(parts[0].strip())
            lon = float(parts[1].strip())
            # Validate lat/lon ranges
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                # Use reverse geocoding to get actual city name
                location_name = get_city_from_coords(lat, lon)
                return lat, lon, location_name
        except (ValueError, IndexError):
            pass
    
    # Try geocoding API for location name
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={location}&count=1"
    response = requests.get(url, timeout=10)
    if response.status_code == 200 and response.json().get("results"):
        data = response.json()["results"][0]
        return data["latitude"], data["longitude"], data.get("name", location)
    return None, None, None

def get_city_from_coords(lat, lon):
    """Reverse geocode coordinates to get city name."""
    try:
        # Use Nominatim reverse geocoding (free, no API key needed)
        url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&accept-language=en"
        headers = {'User-Agent': 'WeatherApp/1.0'}
        response = requests.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            address = data.get('address', {})
            
            # Try to get city name in order of preference
            city = (address.get('city') or 
                   address.get('town') or 
                   address.get('village') or 
                   address.get('municipality') or
                   address.get('county') or
                   address.get('state') or
                   data.get('display_name', '').split(',')[0])
            
            # Add country for context
            country = address.get('country', '')
            if city and country:
                return f"{city}, {country}"
            elif city:
                return city
    except Exception as e:
        print(f"Reverse geocoding error: {e}")
    
    # Fallback to coordinates if reverse geocoding fails
    return f"Location ({lat:.4f}, {lon:.4f})"

def get_weather_data(lat, lon, start_date, end_date):
    """Fetch historical weather data from Open-Meteo."""
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={start_date}&end_date={end_date}&daily=temperature_2m_mean"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def get_current_weather(lat, lon):
    """Fetch current weather from Open-Meteo."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,apparent_temperature,is_day,precipitation,rain,showers,snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,wind_direction_10m,wind_gusts_10m&temperature_unit=celsius&wind_speed_unit=kmh&precipitation_unit=mm"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def get_forecast(lat, lon):
    """Fetch 5-day weather forecast from Open-Meteo."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,apparent_temperature_min,sunrise,sunset,precipitation_sum,rain_sum,showers_sum,snowfall_sum,precipitation_hours,wind_speed_10m_max,wind_gusts_10m_max,wind_direction_10m_dominant&temperature_unit=celsius&wind_speed_unit=kmh&precipitation_unit=mm&forecast_days=5"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    return None

def get_weather_description(code):
    """Convert weather code to description and icon."""
    weather_codes = {
        0: {"description": "Clear sky", "icon": "☀️"},
        1: {"description": "Mainly clear", "icon": "🌤️"},
        2: {"description": "Partly cloudy", "icon": "⛅"},
        3: {"description": "Overcast", "icon": "☁️"},
        45: {"description": "Foggy", "icon": "🌫️"},
        48: {"description": "Depositing rime fog", "icon": "🌫️"},
        51: {"description": "Light drizzle", "icon": "🌦️"},
        53: {"description": "Moderate drizzle", "icon": "🌦️"},
        55: {"description": "Dense drizzle", "icon": "🌧️"},
        61: {"description": "Slight rain", "icon": "🌧️"},
        63: {"description": "Moderate rain", "icon": "🌧️"},
        65: {"description": "Heavy rain", "icon": "🌧️"},
        71: {"description": "Slight snow", "icon": "🌨️"},
        73: {"description": "Moderate snow", "icon": "❄️"},
        75: {"description": "Heavy snow", "icon": "❄️"},
        77: {"description": "Snow grains", "icon": "🌨️"},
        80: {"description": "Slight rain showers", "icon": "🌦️"},
        81: {"description": "Moderate rain showers", "icon": "🌧️"},
        82: {"description": "Violent rain showers", "icon": "⛈️"},
        85: {"description": "Slight snow showers", "icon": "🌨️"},
        86: {"description": "Heavy snow showers", "icon": "❄️"},
        95: {"description": "Thunderstorm", "icon": "⛈️"},
        96: {"description": "Thunderstorm with slight hail", "icon": "⛈️"},
        99: {"description": "Thunderstorm with heavy hail", "icon": "⛈️"}
    }
    return weather_codes.get(code, {"description": "Unknown", "icon": "🌡️"})

# --- API Routes ---

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/config', methods=['GET'])
def get_config():
    """Return API configuration to frontend"""
    return jsonify({
        'google_maps_api_key': GOOGLE_MAPS_API_KEY
    })

@app.route('/api/locations/search', methods=['GET'])
def search_locations():
    """Search for locations with autocomplete."""
    query = request.args.get('q', '')
    if not query or len(query) < 2:
        return jsonify([])
    
    try:
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={query}&count=10&language=en&format=json"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            results = []
            
            if data.get('results'):
                for item in data['results']:
                    location_parts = []
                    
                    # Add name
                    if item.get('name'):
                        location_parts.append(item['name'])
                    
                    # Add admin areas
                    if item.get('admin1'):
                        location_parts.append(item['admin1'])
                    
                    # Add country
                    if item.get('country'):
                        location_parts.append(item['country'])
                    
                    display_name = ', '.join(location_parts)
                    
                    results.append({
                        'name': item.get('name', ''),
                        'display_name': display_name,
                        'latitude': item.get('latitude'),
                        'longitude': item.get('longitude'),
                        'country': item.get('country', ''),
                        'admin1': item.get('admin1', ''),
                        'id': item.get('id')
                    })
            
            return jsonify(results)
    except Exception as e:
        print(f"Location search error: {e}")
        return jsonify([])
    
    return jsonify([])

# Current Weather
@app.route('/api/weather/current', methods=['POST'])
def get_current_weather_api():
    data = request.get_json()
    location = data.get('location')
    
    if not location:
        return jsonify({"error": "Location is required"}), 400
    
    lat, lon, found_location_name = get_location_coords(location)
    if not lat:
        return jsonify({"error": f"Could not find location: {location}"}), 404
    
    weather_data = get_current_weather(lat, lon)
    if not weather_data or 'current' not in weather_data:
        return jsonify({"error": "Could not retrieve current weather data."}), 500
    
    current = weather_data['current']
    weather_info = get_weather_description(current.get('weather_code', 0))
    
    return jsonify({
        'location': found_location_name,
        'latitude': lat,
        'longitude': lon,
        'temperature': current.get('temperature_2m'),
        'feels_like': current.get('apparent_temperature'),
        'humidity': current.get('relative_humidity_2m'),
        'wind_speed': current.get('wind_speed_10m'),
        'wind_direction': current.get('wind_direction_10m'),
        'precipitation': current.get('precipitation'),
        'cloud_cover': current.get('cloud_cover'),
        'pressure': current.get('pressure_msl'),
        'weather_description': weather_info['description'],
        'weather_icon': weather_info['icon'],
        'is_day': current.get('is_day')
    }), 200

# 5-Day Forecast
@app.route('/api/weather/forecast', methods=['POST'])
def get_forecast_api():
    data = request.get_json()
    location = data.get('location')
    
    if not location:
        return jsonify({"error": "Location is required"}), 400
    
    lat, lon, found_location_name = get_location_coords(location)
    if not lat:
        return jsonify({"error": f"Could not find location: {location}"}), 404
    
    forecast_data = get_forecast(lat, lon)
    if not forecast_data or 'daily' not in forecast_data:
        return jsonify({"error": "Could not retrieve forecast data."}), 500
    
    daily = forecast_data['daily']
    forecast_list = []
    
    for i in range(min(5, len(daily['time']))):
        weather_info = get_weather_description(daily['weather_code'][i])
        forecast_list.append({
            'date': daily['time'][i],
            'temp_max': daily['temperature_2m_max'][i],
            'temp_min': daily['temperature_2m_min'][i],
            'precipitation': daily.get('precipitation_sum', [0])[i],
            'wind_speed': daily.get('wind_speed_10m_max', [0])[i],
            'weather_description': weather_info['description'],
            'weather_icon': weather_info['icon']
        })
    
    return jsonify({
        'location': found_location_name,
        'latitude': lat,
        'longitude': lon,
        'forecast': forecast_list
    }), 200

# CREATE
@app.route('/api/weather', methods=['POST'])
def create_weather_record():
    data = request.get_json()
    location = data.get('location')
    start_date = data.get('start_date')
    end_date = data.get('end_date')

    if not all([location, start_date, end_date]):
        return jsonify({"error": "Missing required fields"}), 400

    if not validate_date(start_date) or not validate_date(end_date):
        return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
    
    if start_date > end_date:
        return jsonify({"error": "Start date cannot be after end date."}), 400

    lat, lon, found_location_name = get_location_coords(location)
    if not lat:
        return jsonify({"error": f"Could not find location: {location}"}), 404

    weather_data = get_weather_data(lat, lon, start_date, end_date)
    if not weather_data or 'daily' not in weather_data:
        return jsonify({"error": "Could not retrieve weather data."}), 500

    # Insert into MongoDB - store as native JSON/dict
    new_record = {
        'location': found_location_name,
        'start_date': start_date,
        'end_date': end_date,
        'temperatures': weather_data['daily'],  # Store as dict directly
        'created_at': datetime.datetime.utcnow()
    }
    
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500
    result = coll.insert_one(new_record)
    
    # Convert for response
    response_data = {
        'id': str(result.inserted_id),
        'location': new_record['location'],
        'start_date': new_record['start_date'],
        'end_date': new_record['end_date'],
        'temperatures': json.dumps(new_record['temperatures'])  # Convert to JSON string for frontend
    }

    return jsonify(response_data), 201

# READ (All) - MongoDB version
@app.route('/api/weather/history', methods=['GET'])
def get_history():
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500
    records = coll.find()
    result = []
    for record in records:
        result.append({
            'id': str(record['_id']),
            'location': record['location'],
            'start_date': record['start_date'],
            'end_date': record['end_date'],
            'temperatures': json.dumps(record['temperatures'])  # Convert to JSON string
        })
    return jsonify(result)

# UPDATE - MongoDB version
@app.route('/api/weather/history/<id>', methods=['PUT'])
def update_record(id):
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500
    try:
        record = coll.find_one({'_id': ObjectId(id)})
        if not record:
            return jsonify({"error": "Record not found"}), 404
    except:
        return jsonify({"error": "Invalid record ID"}), 400
    
    data = request.get_json()
    
    new_location = data.get('location')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    
    if not new_location:
        return jsonify({"error": "Location is required for update"}), 400
    
    # Validate dates if provided
    if start_date and end_date:
        if not validate_date(start_date) or not validate_date(end_date):
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD."}), 400
        
        if start_date > end_date:
            return jsonify({"error": "Start date cannot be after end date."}), 400
        
        # Re-validate location and fetch new data
        lat, lon, found_location_name = get_location_coords(new_location)
        if not lat:
            return jsonify({"error": f"Could not find location: {new_location}"}), 404
        
        weather_data = get_weather_data(lat, lon, start_date, end_date)
        if not weather_data or 'daily' not in weather_data:
            return jsonify({"error": "Could not retrieve weather data."}), 500
        
        # Update MongoDB document
        coll.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'location': found_location_name,
                'start_date': start_date,
                'end_date': end_date,
                'temperatures': weather_data['daily'],
                'updated_at': datetime.datetime.utcnow()
            }}
        )
    else:
        # Only update location name
        coll.update_one(
            {'_id': ObjectId(id)},
            {'$set': {
                'location': new_location,
                'updated_at': datetime.datetime.utcnow()
            }}
        )
    
    # Fetch updated record
    updated_record = coll.find_one({'_id': ObjectId(id)})
    return jsonify({
        'id': str(updated_record['_id']),
        'location': updated_record['location'],
        'start_date': updated_record['start_date'],
        'end_date': updated_record['end_date'],
        'temperatures': json.dumps(updated_record['temperatures'])
    })

# DELETE - MongoDB version
@app.route('/api/weather/history/<id>', methods=['DELETE'])
def delete_record(id):
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500
    try:
        result = coll.delete_one({'_id': ObjectId(id)})
        if result.deleted_count == 0:
            return jsonify({"error": "Record not found"}), 404
        return jsonify({"message": "Record deleted successfully"})
    except:
        return jsonify({"error": "Invalid record ID"}), 400, 200


@app.route('/api/weather/history', methods=['DELETE'])
def clear_history():
    """Clear all weather history records.

    Safety: require explicit confirmation either as query param `?confirm=true`
    or JSON body `{"confirm": true}`. This prevents accidental deletions.
    Returns the number of deleted documents.
    """
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500

    # Require explicit confirmation to avoid accidental mass-deletes
    confirm_q = request.args.get('confirm', '').lower() == 'true'
    confirm_json = False
    try:
        body = request.get_json(silent=True) or {}
        confirm_json = bool(body.get('confirm') is True)
    except Exception:
        confirm_json = False

    if not (confirm_q or confirm_json):
        return jsonify({
            "error": "Confirmation required to clear history. Provide ?confirm=true or JSON {'confirm': true} in request body."
        }), 400

    try:
        result = coll.delete_many({})
        return jsonify({
            'message': 'All weather history records deleted',
            'deleted_count': int(result.deleted_count)
        }), 200
    except Exception as e:
        return jsonify({"error": "Failed to delete records", "details": str(e)}), 500

# EXPORT - JSON - MongoDB version
@app.route('/api/export/json', methods=['GET'])
def export_json():
    """Export all weather records as JSON."""
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500
    records = coll.find()
    result = []
    for record in records:
        result.append({
            'id': str(record['_id']),
            'location': record['location'],
            'start_date': record['start_date'],
            'end_date': record['end_date'],
            'temperatures': record['temperatures']  # Keep as dict for JSON export
        })
    
    response = make_response(json.dumps(result, indent=2))
    response.headers['Content-Type'] = 'application/json'
    response.headers['Content-Disposition'] = 'attachment; filename=weather_data.json'
    return response

# EXPORT - CSV - MongoDB version
@app.route('/api/export/csv', methods=['GET'])
def export_csv():
    """Export all weather records as CSV."""
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500
    records = coll.find()
    
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Location', 'Start Date', 'End Date', 'Average Temperature', 'Min Temperature', 'Max Temperature'])
    
    for record in records:
        temps = record['temperatures']['temperature_2m_mean']
        avg_temp = sum(temps) / len(temps) if temps else 0
        min_temp = min(temps) if temps else 0
        max_temp = max(temps) if temps else 0
        
        writer.writerow([
            str(record['_id']),
            record['location'],
            record['start_date'],
            record['end_date'],
            f"{avg_temp:.1f}",
            f"{min_temp:.1f}",
            f"{max_temp:.1f}"
        ])
    
    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = 'attachment; filename=weather_data.csv'
    return response

# EXPORT - Markdown - MongoDB version
@app.route('/api/export/markdown', methods=['GET'])
def export_markdown():
    """Export all weather records as Markdown."""
    coll = get_collection_safe('weather_history')
    if coll is None:
        return jsonify({"error": "Database not initialized"}), 500
    records = coll.find()
    
    md_content = "# Weather History Data\n\n"
    md_content += f"*Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*\n\n"
    
    for record in records:
        temps = record['temperatures']['temperature_2m_mean']
        avg_temp = sum(temps) / len(temps) if temps else 0
        min_temp = min(temps) if temps else 0
        max_temp = max(temps) if temps else 0
        
        md_content += f"## {record['location']}\n\n"
        md_content += f"- **Date Range:** {record['start_date']} to {record['end_date']}\n"
        md_content += f"- **Average Temperature:** {avg_temp:.1f}°C\n"
        md_content += f"- **Min Temperature:** {min_temp:.1f}°C\n"
        md_content += f"- **Max Temperature:** {max_temp:.1f}°C\n"
        md_content += f"- **Record ID:** {str(record['_id'])}\n\n"
        
        # Add Google Maps and YouTube links
        md_content += f"### Links\n"
        md_content += f"- [View on Google Maps](https://www.google.com/maps/search/?api=1&query={record['location'].replace(' ', '+')})\n"
        md_content += f"- [YouTube Videos](https://www.youtube.com/results?search_query={record['location'].replace(' ', '+')}+travel)\n\n"
        md_content += "---\n\n"
    
    response = make_response(md_content)
    response.headers['Content-Type'] = 'text/markdown'
    response.headers['Content-Disposition'] = 'attachment; filename=weather_data.md'
    return response

if __name__ == '__main__':
    app.run(debug=True, port=5001)
