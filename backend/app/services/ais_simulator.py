import random
from datetime import datetime, timedelta
from typing import List, Dict
from geopy.distance import geodesic

# Lista de puertos con coordenadas básicas
PORTS = [
    {"name": "Houston", "lat": 29.75, "lon": -95.36},
    {"name": "Singapore", "lat": 1.29, "lon": 103.85},
    {"name": "Rotterdam", "lat": 51.92, "lon": 4.48},
    {"name": "Panama", "lat": 8.98, "lon": -79.52},
    {"name": "Shanghai", "lat": 31.23, "lon": 121.47},
    {"name": "Santos", "lat": -23.95, "lon": -46.33}
]

# Simulación de buques en operación
VESSELS = [
    {"name": "Ever Giant", "type": "Tanker"},
    {"name": "Ocean Pearl", "type": "Bulk"},
    {"name": "Phoenix Star", "type": "Product"},
    {"name": "Atlantic Wave", "type": "Crude"},
    {"name": "Arctic Queen", "type": "LNG"}
]

def random_coordinates_near(lat, lon, radius_km=50):
    """Devuelve coordenadas aleatorias cercanas a un punto base"""
    offset_lat = random.uniform(-0.3, 0.3)
    offset_lon = random.uniform(-0.3, 0.3)
    return round(lat + offset_lat, 4), round(lon + offset_lon, 4)

def simulate_eta_and_state(position, destination):
    """Calcula ETA ficticia y estado del buque"""
    distance_nm = geodesic(position, destination).nautical
    speed_knots = random.choice([12, 14, 16, 18])  # velocidad promedio
    eta_hours = distance_nm / speed_knots
    eta = datetime.utcnow() + timedelta(hours=eta_hours)

    if distance_nm < 5:
        status = "At Port"
    elif distance_nm < 25:
        status = "Idle"
    else:
        status = "In Transit"

    return eta.isoformat(), speed_knots, round(distance_nm, 2), status

def get_fake_ais_data() -> List[Dict]:
    """Genera lista de buques con coordenadas, destino, ETA y estado"""
    data = []

    for vessel in VESSELS:
        origin = random.choice(PORTS)
        destination = random.choice([p for p in PORTS if p != origin])

        lat, lon = random_coordinates_near(origin["lat"], origin["lon"])
        eta, speed, distance, status = simulate_eta_and_state((lat, lon), (destination["lat"], destination["lon"]))

        data.append({
            "name": vessel["name"],
            "type": vessel["type"],
            "lat": lat,
            "lon": lon,
            "origin": origin["name"],
            "destination": destination["name"],
            "eta": eta,
            "speed_knots": speed,
            "distance_nm": distance,
            "status": status
        })

    return data
