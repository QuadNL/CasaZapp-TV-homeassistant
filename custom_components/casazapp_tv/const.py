"""Constants for the CasaZapp TV integration."""

from datetime import timedelta
import logging

DOMAIN = "casazapp_tv"
LOGGER = logging.getLogger(__package__)

# The summary is asked again this often; what plays comes at once through the server's events.
SCAN_INTERVAL = timedelta(seconds=60)

# Events after which the summary is read again at once.
REFRESH_EVENTS = {"streams-changed", "taken-over", "sync-progress"}

ATTR_CHANNEL_ID = "channel_id"
ATTR_MINUTES = "minutes"
ATTR_START = "start"
ATTR_STOP = "stop"
ATTR_TITLE = "title"
ATTR_TAKEOVER = "takeover"
ATTR_RECORDING_ID = "recording_id"
ATTR_STREAM_ID = "stream_id"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"

SERVICE_RECORD = "record"
SERVICE_STOP_RECORDING = "stop_recording"
SERVICE_DELETE_RECORDING = "delete_recording"
SERVICE_STOP_STREAM = "stop_stream"
