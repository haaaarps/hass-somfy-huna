"""Base entity for Somfy Huna blinds."""

from __future__ import annotations

from homeassistant.helpers.device_registry import CONNECTION_BLUETOOTH, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import DOMAIN
from .device import HunaDevice


class HunaEntity(Entity):
    """Entity that follows a blind's advertisements."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, device: HunaDevice) -> None:
        self._device = device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device.address)},
            connections={(CONNECTION_BLUETOOTH, device.address)},
            name=device.name,
            manufacturer="Somfy",
            model="Huna",
        )

    @property
    def available(self) -> bool:
        return self._device.available

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            self._device.async_add_listener(self.async_write_ha_state)
        )
