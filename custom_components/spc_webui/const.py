DOMAIN = "spc_webui"
MANUFACTURER = "Vanderbilt"

CONF_URL = "url"
CONF_USERID = "userid"
CONF_PASSWORD = "password"
CONF_POLL_INTERVAL = "poll_interval"
CONF_EDP_PORT = "edp_port"
CONF_EDP_SYSTEM_ID = "edp_system_id"

DEFAULT_POLL_INTERVAL = 30
DEFAULT_EDP_PORT = 0
DEFAULT_EDP_SYSTEM_ID = 0

PLATFORMS = [
    "alarm_control_panel",
    "binary_sensor",
    "sensor",
    "switch",
]
