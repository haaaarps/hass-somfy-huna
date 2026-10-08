"""Constants for the Somfy Huna integration."""

DOMAIN = "somfy_huna"

MANUFACTURER_ID = 1480
DEFAULT_NAME = "MyHunaBlind"

CONF_INVERT = "invert_position"

UUID_SYSTEM_ID = "00002a23-0000-1000-8000-00805f9b34fb"
UUID_BATTERY = "00002a19-0000-1000-8000-00805f9b34fb"
UUID_CHALLENGE = "4ad9759f-6df4-40f7-b0ec-7c007cb8995c"
UUID_CHALLENGE_RESPONSE = "f322fa7d-f61e-4934-9e56-c2a50c3bf863"
UUID_POSITION = "53667942-6c69-6e64-506f-736974696f6e"
UUID_ADJUST = "53667942-6c69-6e64-4164-6a7374436d64"

# Adjust commands. Open and close go through the position characteristic
# instead of top (2) / bottom (3): in testing a "top" command stopped as soon
# as the connection closed, while a position move carries on. 4 and 5
# re-program the blind's end limits and are deliberately not defined.
CMD_STOP = 1

POSITION_FULL = 51200  # 0xC800 = 100 % travel on the position characteristic
ADVERT_POSITION_FULL = 255

BATTERY_BANDS = {0: "critical", 1: "low", 2: "medium", 3: "high"}
