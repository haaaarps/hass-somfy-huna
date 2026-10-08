"""Somfy Huna Bluetooth roller blinds."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, Platform
from homeassistant.core import HomeAssistant

from .device import HunaDevice

PLATFORMS = [Platform.COVER, Platform.SENSOR]

type HunaConfigEntry = ConfigEntry[HunaDevice]


async def async_setup_entry(hass: HomeAssistant, entry: HunaConfigEntry) -> bool:
    """Set up one blind."""
    device = HunaDevice(hass, entry.data[CONF_ADDRESS], entry.title)
    entry.runtime_data = device
    for unsubscribe in device.async_start():
        entry.async_on_unload(unsubscribe)
    entry.async_on_unload(device.async_shutdown)
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload(hass: HomeAssistant, entry: HunaConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: HunaConfigEntry) -> bool:
    """Unload one blind."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
