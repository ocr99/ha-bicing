"""Constants for Bicing."""

DOMAIN = "bicing"
STATION_INFO_ENDPOINT = "https://opendata-ajuntament.barcelona.cat/data/dataset/bd2462df-6e1e-4e37-8205-a4b8e7313b84/resource/f60e9291-5aaa-417d-9b91-612a9de800aa/download/recurs.json"
STATION_STATUS_ENDPOINT = "https://opendata-ajuntament.barcelona.cat/data/dataset/6aa3416d-ce1a-494d-861b-7bd07f069600/resource/1b215493-9e63-4a12-8980-2d7e0fa19f85/download/recurs.json"
TOKEN = "token"

UPDATE_INTERVAL = 10  # minuts
REQUEST_TIMEOUT_SECONDS = 15
RETRY_ATTEMPTS = 2
MAX_RETRY_AFTER_SECONDS = 3600

# Es manté l'últim estat conegut de les estacions durant errors transitoris
# de l'API. Passat aquest període sense una actualització correcta, les
# entitats passen a no estar disponibles mitjançant CoordinatorEntity.
STALE_DATA_TTL_HOURS = 1

CONF_STATION_IDS = "station_ids"
