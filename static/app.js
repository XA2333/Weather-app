// Global variables
let currentRecords = [];
let googleMapsApiKey = '';
let autocompleteTimeout = null;
let selectedLocationData = {};

document.addEventListener('DOMContentLoaded', function() {
    const weatherForm = document.getElementById('weather-form');
    const weatherResult = document.getElementById('weather-result');
    const updateForm = document.getElementById('update-form');
    const currentWeatherForm = document.getElementById('current-weather-form');

    // Fetch API configuration
    fetch('/api/config')
        .then(response => response.json())
        .then(data => {
            googleMapsApiKey = data.google_maps_api_key;
        })
        .catch(error => {
            console.error('Error fetching config:', error);
        });

    // Setup autocomplete for location inputs
    setupAutocomplete('location', 'location-suggestions');
    setupAutocomplete('current-location', 'current-location-suggestions');

    // Fetch and display history on page load
    fetchHistory();

    // Set max date to today for date inputs
    const today = new Date().toISOString().split('T')[0];
    document.getElementById('start-date').setAttribute('max', today);
    document.getElementById('end-date').setAttribute('max', today);
    document.getElementById('update-start-date').setAttribute('max', today);
    document.getElementById('update-end-date').setAttribute('max', today);

    // Current Weather form submission
    currentWeatherForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const inputId = 'current-location';
        const input = document.getElementById(inputId);
        
        // Use selected location data if available (coordinates format)
        let location;
        if (selectedLocationData[inputId] && selectedLocationData[inputId].latitude && selectedLocationData[inputId].longitude) {
            // Use coordinates format for precise location
            location = `${selectedLocationData[inputId].latitude},${selectedLocationData[inputId].longitude}`;
        } else {
            // Fallback to input value (manual entry or GPS coordinates)
            location = input.value;
        }
        
        getCurrentWeather(location);
    });

    // Historical Weather form submission
    weatherForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const inputId = 'location';
        const input = document.getElementById(inputId);
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;

        // Validate dates
        if (new Date(startDate) > new Date(endDate)) {
            showResult('Error: Start date cannot be after end date.', 'error');
            return;
        }

        // Use selected location data if available (coordinates format)
        let location;
        if (selectedLocationData[inputId] && selectedLocationData[inputId].latitude && selectedLocationData[inputId].longitude) {
            // Use coordinates format for precise location
            location = `${selectedLocationData[inputId].latitude},${selectedLocationData[inputId].longitude}`;
        } else {
            // Fallback to input value (manual entry or GPS coordinates)
            location = input.value;
        }

        showResult('Loading...', 'success');

        fetch('/api/weather', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                location: location,
                start_date: startDate,
                end_date: endDate
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                showResult(`Error: ${data.error}`, 'error');
            } else {
                showResult(`✓ Successfully saved weather for ${data.location}!`, 'success');
                weatherForm.reset();
                fetchHistory(); // Refresh history
                
                // Clear selected location data after successful submission
                delete selectedLocationData[inputId];
            }
        })
        .catch(error => {
            showResult(`Error: ${error.message}`, 'error');
        });
    });

    // Update form submission
    updateForm.addEventListener('submit', function(event) {
        event.preventDefault();
        const id = document.getElementById('update-id').value;
        const location = document.getElementById('update-location').value;
        const startDate = document.getElementById('update-start-date').value;
        const endDate = document.getElementById('update-end-date').value;

        // Validate dates
        if (new Date(startDate) > new Date(endDate)) {
            alert('Error: Start date cannot be after end date.');
            return;
        }

        fetch(`/api/weather/history/${id}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                location: location,
                start_date: startDate,
                end_date: endDate
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                alert(`Error: ${data.error}`);
            } else {
                alert('✓ Record updated successfully!');
                closeModal();
                fetchHistory();
            }
        })
        .catch(error => {
            alert(`Error: ${error.message}`);
        });
    });
});

function setupAutocomplete(inputId, dropdownId) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    
    if (!input || !dropdown) return;
    
    input.addEventListener('input', function() {
        const query = this.value.trim();
        
        // Clear previously selected location data when user types
        if (selectedLocationData[inputId]) {
            delete selectedLocationData[inputId];
        }
        
        // Clear previous timeout
        if (autocompleteTimeout) {
            clearTimeout(autocompleteTimeout);
        }
        
        // Hide dropdown if query is too short
        if (query.length < 2) {
            dropdown.classList.remove('show');
            dropdown.innerHTML = '';
            return;
        }
        
        // Show loading
        dropdown.innerHTML = '<div class="autocomplete-loading"><i class="fas fa-spinner fa-spin"></i> Searching...</div>';
        dropdown.classList.add('show');
        
        // Debounce search
        autocompleteTimeout = setTimeout(() => {
            searchLocations(query, dropdown, input);
        }, 300);
    });
    
    // Close dropdown when clicking outside
    document.addEventListener('click', function(e) {
        if (!input.contains(e.target) && !dropdown.contains(e.target)) {
            dropdown.classList.remove('show');
        }
    });
    
    // Handle input focus
    input.addEventListener('focus', function() {
        if (dropdown.innerHTML && this.value.length >= 2) {
            dropdown.classList.add('show');
        }
    });
}

function searchLocations(query, dropdown, input) {
    fetch(`/api/locations/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            if (data.length === 0) {
                dropdown.innerHTML = '<div class="autocomplete-no-results">No locations found</div>';
                return;
            }
            
            let html = '';
            data.forEach(location => {
                html += `
                    <div class="autocomplete-item" onclick="selectLocation('${input.id}', '${dropdown.id}', ${JSON.stringify(location).replace(/"/g, '&quot;')})">
                        <div class="location-name">
                            <i class="fas fa-map-marker-alt"></i> ${location.name}
                            <span class="location-country">${location.country}</span>
                        </div>
                        <div class="location-details">${location.display_name}</div>
                    </div>
                `;
            });
            
            dropdown.innerHTML = html;
            dropdown.classList.add('show');
        })
        .catch(error => {
            console.error('Location search error:', error);
            dropdown.innerHTML = '<div class="autocomplete-no-results">Error searching locations</div>';
        });
}

function selectLocation(inputId, dropdownId, locationData) {
    const input = document.getElementById(inputId);
    const dropdown = document.getElementById(dropdownId);
    
    // Set input value to display name
    input.value = locationData.display_name;
    
    // Store location data for form submission
    selectedLocationData[inputId] = locationData;
    
    // Hide dropdown
    dropdown.classList.remove('show');
}

function getCurrentWeather(location) {
    const display = document.getElementById('current-weather-display');
    display.innerHTML = '<p style="text-align: center;"><i class="fas fa-spinner fa-spin"></i> Loading current weather...</p>';
    
    fetch('/api/weather/current', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location: location })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            display.innerHTML = `<p style="color: red; text-align: center;">${data.error}</p>`;
        } else {
            displayCurrentWeather(data);
            getForecast(location);
        }
    })
    .catch(error => {
        display.innerHTML = `<p style="color: red; text-align: center;">Error: ${error.message}</p>`;
    });
}

function displayCurrentWeather(data) {
    const display = document.getElementById('current-weather-display');
    display.innerHTML = `
        <div class="weather-current-card">
            <div class="location-name">
                <i class="fas fa-map-marker-alt"></i> ${data.location}
            </div>
            <div class="weather-icon">${data.weather_icon}</div>
            <div class="temperature">${data.temperature.toFixed(1)}°C</div>
            <div class="description">${data.weather_description}</div>
            <div class="weather-details-grid">
                <div class="weather-detail-item">
                    <i class="fas fa-thermometer-half"></i>
                    <div class="label">Feels Like</div>
                    <div class="value">${data.feels_like.toFixed(1)}°C</div>
                </div>
                <div class="weather-detail-item">
                    <i class="fas fa-tint"></i>
                    <div class="label">Humidity</div>
                    <div class="value">${data.humidity}%</div>
                </div>
                <div class="weather-detail-item">
                    <i class="fas fa-wind"></i>
                    <div class="label">Wind Speed</div>
                    <div class="value">${data.wind_speed.toFixed(1)} km/h</div>
                </div>
                <div class="weather-detail-item">
                    <i class="fas fa-compress-arrows-alt"></i>
                    <div class="label">Pressure</div>
                    <div class="value">${data.pressure.toFixed(0)} hPa</div>
                </div>
                <div class="weather-detail-item">
                    <i class="fas fa-cloud"></i>
                    <div class="label">Cloud Cover</div>
                    <div class="value">${data.cloud_cover}%</div>
                </div>
                <div class="weather-detail-item">
                    <i class="fas fa-cloud-rain"></i>
                    <div class="label">Precipitation</div>
                    <div class="value">${data.precipitation} mm</div>
                </div>
            </div>
        </div>
    `;
}

function getForecast(location) {
    const display = document.getElementById('forecast-display');
    display.innerHTML = '<p style="text-align: center;"><i class="fas fa-spinner fa-spin"></i> Loading forecast...</p>';
    
    fetch('/api/weather/forecast', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ location: location })
    })
    .then(response => response.json())
    .then(data => {
        if (data.error) {
            display.innerHTML = `<p style="color: red; text-align: center;">${data.error}</p>`;
        } else {
            displayForecast(data);
        }
    })
    .catch(error => {
        display.innerHTML = `<p style="color: red; text-align: center;">Error: ${error.message}</p>`;
    });
}

function displayForecast(data) {
    const display = document.getElementById('forecast-display');
    let html = '<div class="forecast-grid">';
    
    data.forecast.forEach(day => {
        const date = new Date(day.date);
        const dayName = date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });
        
        html += `
            <div class="forecast-day">
                <div class="date">${dayName}</div>
                <div class="icon">${day.weather_icon}</div>
                <div class="temps">
                    <div class="temp-max">${day.temp_max.toFixed(1)}°C</div>
                    <div class="temp-min">${day.temp_min.toFixed(1)}°C</div>
                </div>
                <div class="description">${day.weather_description}</div>
                <div style="font-size: 0.8em; margin-top: 5px;">
                    <i class="fas fa-cloud-rain"></i> ${day.precipitation.toFixed(1)}mm
                </div>
            </div>
        `;
    });
    
    html += '</div>';
    display.innerHTML = html;
}

function getCurrentLocationWeather() {
    if (!navigator.geolocation) {
        alert('Geolocation is not supported by your browser');
        return;
    }
    
    // Clear any previously selected location from autocomplete
    delete selectedLocationData['current-location'];
    
    const display = document.getElementById('current-weather-display');
    display.innerHTML = '<p style="text-align: center;"><i class="fas fa-spinner fa-spin"></i> Getting your location...</p>';
    
    navigator.geolocation.getCurrentPosition(
        function(position) {
            const lat = position.coords.latitude.toFixed(4);
            const lon = position.coords.longitude.toFixed(4);
            getCurrentWeather(`${lat},${lon}`);
        },
        function(error) {
            display.innerHTML = `<p style="color: red; text-align: center;">Error getting location: ${error.message}</p>`;
        }
    );
}

function showPMInfo() {
    document.getElementById('pm-info-modal').style.display = 'block';
}

function closePMInfo() {
    document.getElementById('pm-info-modal').style.display = 'none';
}

function showResult(message, type) {
    const weatherResult = document.getElementById('weather-result');
    weatherResult.textContent = message;
    weatherResult.className = `result-message ${type}`;
    weatherResult.style.display = 'block';
}

function fetchHistory() {
    fetch('/api/weather/history')
        .then(response => response.json())
        .then(data => {
            currentRecords = data;
            const historyContainer = document.getElementById('history-container');
            const noRecords = document.getElementById('no-records');
            
            historyContainer.innerHTML = '';
            
            if (data.length === 0) {
                noRecords.style.display = 'block';
                return;
            }
            
            noRecords.style.display = 'none';
            
            data.forEach(record => {
                const temps = JSON.parse(record.temperatures);
                const avgTemp = calculateAverage(temps.temperature_2m_mean);
                const minTemp = Math.min(...temps.temperature_2m_mean);
                const maxTemp = Math.max(...temps.temperature_2m_mean);
                
                const recordDiv = document.createElement('div');
                recordDiv.className = 'history-item';
                recordDiv.innerHTML = `
                    <h3><i class="fas fa-map-marker-alt"></i>${record.location}</h3>
                    <div class="date-range">
                        <i class="fas fa-calendar"></i>
                        ${formatDate(record.start_date)} to ${formatDate(record.end_date)}
                    </div>
                    <div class="temp-summary">
                        <p><strong>Average:</strong> ${avgTemp.toFixed(1)}°C</p>
                        <p><strong>Min:</strong> ${minTemp.toFixed(1)}°C</p>
                        <p><strong>Max:</strong> ${maxTemp.toFixed(1)}°C</p>
                    </div>
                    <div class="actions">
                        <button onclick="showDetails(${record.id})" class="btn btn-details">
                            <i class="fas fa-eye"></i> Details
                        </button>
                        <button onclick="openUpdateModal(${record.id})" class="btn btn-edit">
                            <i class="fas fa-edit"></i> Edit
                        </button>
                        <button onclick="deleteRecord(${record.id})" class="btn btn-delete">
                            <i class="fas fa-trash"></i> Delete
                        </button>
                    </div>
                `;
                historyContainer.appendChild(recordDiv);
            });
        })
        .catch(error => {
            console.error('Error fetching history:', error);
        });
}

function calculateAverage(arr) {
    return arr.reduce((a, b) => a + b, 0) / arr.length;
}

function formatDate(dateStr) {
    const options = { year: 'numeric', month: 'short', day: 'numeric' };
    return new Date(dateStr).toLocaleDateString('en-US', options);
}

function openUpdateModal(id) {
    const record = currentRecords.find(r => r.id === id);
    if (!record) return;
    
    document.getElementById('update-id').value = record.id;
    document.getElementById('update-location').value = record.location;
    document.getElementById('update-start-date').value = record.start_date;
    document.getElementById('update-end-date').value = record.end_date;
    
    document.getElementById('update-modal').style.display = 'block';
}

function closeModal() {
    document.getElementById('update-modal').style.display = 'none';
}

function showDetails(id) {
    const record = currentRecords.find(r => r.id === id);
    if (!record) return;
    
    const temps = JSON.parse(record.temperatures);
    const detailsTitle = document.getElementById('details-title');
    const detailsContent = document.getElementById('details-content');
    
    detailsTitle.innerHTML = `<i class="fas fa-info-circle"></i> Weather Details - ${record.location}`;
    
    // Build temperature chart
    let tempChart = '<div class="temp-chart">';
    temps.time.forEach((date, index) => {
        tempChart += `
            <div class="temp-entry">
                <span><i class="fas fa-calendar-day"></i> ${formatDate(date)}</span>
                <span><i class="fas fa-thermometer-half"></i> ${temps.temperature_2m_mean[index].toFixed(1)}°C</span>
            </div>
        `;
    });
    tempChart += '</div>';
    
    // Build Google Map embed
    let mapEmbed = '';
    if (googleMapsApiKey && googleMapsApiKey !== 'YOUR_GOOGLE_MAPS_API_KEY_HERE') {
        mapEmbed = `
            <div class="map-container">
                <iframe
                    src="https://www.google.com/maps/embed/v1/place?key=${googleMapsApiKey}&q=${encodeURIComponent(record.location)}"
                    allowfullscreen
                    loading="lazy"
                    referrerpolicy="no-referrer-when-downgrade">
                </iframe>
            </div>
        `;
    } else {
        mapEmbed = `
            <div style="padding: 15px; background: #fff3cd; border: 1px solid #ffc107; border-radius: 8px;">
                <p style="color: #856404; margin: 0;">
                    <i class="fas fa-exclamation-triangle"></i> 
                    <strong>Google Maps API key not configured.</strong><br>
                    Add your API key to <code>config.py</code> to enable map embedding.
                </p>
            </div>
        `;
    }
    
    // Build YouTube search link
    const youtubeSearch = `https://www.youtube.com/results?search_query=${encodeURIComponent(record.location + ' travel guide')}`;
    
    detailsContent.innerHTML = `
        <div class="details-section">
            <h3><i class="fas fa-chart-line"></i> Temperature Data</h3>
            ${tempChart}
        </div>
        <div class="details-section">
            <h3><i class="fas fa-map"></i> Location Map</h3>
            ${mapEmbed}
            <p style="color: #666; margin-top: 10px;">
                <i class="fas fa-external-link-alt"></i> 
                <a href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(record.location)}" target="_blank" style="color: #667eea;">
                    Open in Google Maps
                </a>
            </p>
        </div>
        <div class="details-section">
            <h3><i class="fab fa-youtube"></i> Videos</h3>
            <p style="color: #666;">
                <i class="fas fa-video"></i> 
                <a href="${youtubeSearch}" target="_blank" style="color: #667eea;">
                    Watch videos about ${record.location} on YouTube
                </a>
            </p>
        </div>
    `;
    
    document.getElementById('details-modal').style.display = 'block';
}

function closeDetailsModal() {
    document.getElementById('details-modal').style.display = 'none';
}

function deleteRecord(id) {
    if (!confirm('Are you sure you want to delete this record?')) {
        return;
    }
    
    fetch(`/api/weather/history/${id}`, { method: 'DELETE' })
        .then(response => response.json())
        .then(data => {
            alert('✓ ' + data.message);
            fetchHistory();
        })
        .catch(error => {
            alert(`Error: ${error.message}`);
        });
}

function exportData(format) {
    window.location.href = `/api/export/${format}`;
}

// Close modals when clicking outside
window.onclick = function(event) {
    const updateModal = document.getElementById('update-modal');
    const detailsModal = document.getElementById('details-modal');
    const pmModal = document.getElementById('pm-info-modal');
    
    if (event.target === updateModal) {
        closeModal();
    }
    if (event.target === detailsModal) {
        closeDetailsModal();
    }
    if (event.target === pmModal) {
        closePMInfo();
    }
}
