"""Constants for Börsenpreise."""
DOMAIN = "boersenpreise"
NAME = "Börsenpreise"
VERSION = "0.0.5"
ZONE = "10Y1001A1001A82H"
START = "2025-10-01"
DEFAULTS = {
    "import_start": START,
    "influx_enabled": False,
    "influx_url": "http://localhost:8086",
    "influx_org": "",
    "influx_bucket": "boersenpreise",
    "influx_token": "",
    "green_limit": 5.0,
    "yellow_limit": 10.0,
    "green_color": "#22c55e",
    "yellow_color": "#eab308",
    "high_color": "#ef4444",
}
