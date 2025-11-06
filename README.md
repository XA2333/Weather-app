# Weather-app

A small Flask-based web application for querying and storing historical weather data.
The frontend is a single-page app (static JS/CSS), the backend uses Open-Meteo for weather data
and MongoDB (via Flask-PyMongo) to persist saved history records.

## Project structure (brief)

```
app.py
config.py            # Optional: place GOOGLE_MAPS_API_KEY here
requirements.txt
static/               # Frontend static files (app.js, style.css)
templates/            # index.html
README.md
```

## Features

- Query current weather using Open-Meteo
- Query historical weather for a date range and save it to MongoDB
- View saved history (list + details) and export as JSON/CSV/Markdown
- Edit or delete individual history records
- Clear all history records (explicit confirmation required)
- Frontend includes autocomplete for locations and a details view with a map and YouTube link

## Requirements

- Python 3.8+
- MongoDB (local or remote)

Install dependencies listed in `requirements.txt`:

```powershell
python -m pip install -r requirements.txt
```

## Dependencies and what they do

This project uses a mix of third-party and standard-library packages. Below are the
libraries referenced in the code and what role they play:

- Flask: Lightweight web framework used to build the HTTP API and serve the frontend.
- Flask-PyMongo: Flask integration for PyMongo; provides a convenient `mongo` object
  attached to the Flask app for accessing MongoDB.
- pymongo (used indirectly via Flask-PyMongo): The official MongoDB driver for Python.
  It provides `MongoClient`, `Database`, and `Collection` objects used to read/write data.
- bson (bson.objectid.ObjectId): Helper for converting MongoDB ObjectId values to/from strings
  when reading or writing documents (used for record lookups and deletions).
- requests: Used to call external HTTP APIs (Open-Meteo geocoding, forecast/archive, and
  Nominatim reverse geocoding).
- json (stdlib): Serialization/deserialization of JSON when preparing HTTP responses
  and storing payloads in MongoDB.
- csv (stdlib): Producing CSV exports from stored records.
- io.StringIO (stdlib): In-memory file-like buffer used to assemble CSV content before
  returning it as a download response.
- datetime (stdlib): Date parsing/validation and timestamps for created_at/updated_at fields.

Frontend (static JS/CSS) uses no external Node packages—it's plain JavaScript and fetch API.

## Configuration

- Optional: Create `config.py` in the project root and set:

```python
GOOGLE_MAPS_API_KEY = "YOUR_GOOGLE_MAPS_API_KEY"
```

If omitted, the frontend will show a notice and map embedding will be disabled.

- MongoDB: By default the app uses `mongodb://localhost:27017/weather_app` as configured
  in `app.py`. Change `app.config['MONGO_URI']` if you need to point to a different host/db.

## Run (Windows / PowerShell)

1. Ensure MongoDB is running (example):

```powershell
# If MongoDB is installed as a service
net start MongoDB

# Or run mongod directly (adjust path & dbpath)
& "C:\Program Files\MongoDB\Server\<version>\bin\mongod.exe" --dbpath "C:\data\db"
```

2. Install dependencies:

```powershell
python -m pip install -r requirements.txt
```

3. Start the dev server:

```powershell
python app.py
```

The app runs in development mode at: http://127.0.0.1:5001

> Note: This is Flask's development server — not suitable for production. Use a WSGI server
for production deployments (gunicorn/uvicorn/uwsgi behind a reverse proxy).

## API overview

Major endpoints the frontend uses (summary):

- `GET /` — Serve the frontend page
- `GET /api/config` — Returns frontend configuration (e.g. Google Maps API key)
- `GET /api/locations/search?q=...` — Location autocomplete (Open-Meteo geocoding)
- `POST /api/weather/current` — Get current weather
  - Body: `{ "location": "latitude,longitude" }` or a place name
- `POST /api/weather/forecast` — Get 5-day forecast
  - Body: `{ "location": "..." }`
- `POST /api/weather` — Create and save historical weather for a date range
  - Body: `{ "location": "...", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD" }`
- `GET /api/weather/history` — Get all saved history records
- `PUT /api/weather/history/<id>` — Update a record (or just its location)
- `DELETE /api/weather/history/<id>` — Delete a single record
- `DELETE /api/weather/history?confirm=true` or send JSON body `{ "confirm": true }` —
  Clear all history records (confirmation required)
- `GET /api/export/json|csv|markdown` — Export all stored records

Examples (curl):

```powershell
# Delete a single record
curl -X DELETE http://127.0.0.1:5001/api/weather/history/<id>

# Clear all records (confirmation required)
curl -X DELETE "http://127.0.0.1:5001/api/weather/history?confirm=true"

# Or with JSON body
curl -X DELETE http://127.0.0.1:5001/api/weather/history -H "Content-Type: application/json" -d "{\"confirm\": true}"
```

## Frontend notes

- The history list is rendered by `static/app.js` (`fetchHistory()`), which creates
  three action buttons per record: Details, Edit, Delete.
- I fixed an issue where generated inline onclick handlers passed the id without
  quoting; those are now emitted with string ids to avoid JS reference errors.

## Troubleshooting

- If `/api/weather/history` returns 500: ensure MongoDB is running and `MONGO_URI`
  in `app.py` points to the correct database.
- If embedded maps do not appear: set a valid `GOOGLE_MAPS_API_KEY` in `config.py` and
  ensure the key has Maps Embed API enabled.
- If front-end buttons are unresponsive: open the browser DevTools Console and copy
  any JS errors here for debugging.

## Development suggestions (optional)

- Replace inline `onclick` attributes with event delegation using `data-id` attributes
  (safer and easier to maintain).
- Add authentication / authorization for destructive operations (delete/clear).
- Add an audit log collection to track who performed deletes/clears in production.

## Quick checks

```powershell
# Syntax check
python -m py_compile app.py

```

## License

MIT

---

If you'd like the README to include more examples (full request/response bodies),
or a separate API reference file, I can add that next.