"""Battery sensors for Somfy Huna blinds."""

from __future__ import annotations

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HunaConfigEntry
from .const import BATTERY_BANDS
from .device import HunaDevice
from .entity import HunaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HunaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    device = entry.runtime_data
    async_add_entities([HunaBatteryLevel(device), HunaBatteryPercent(device)])


class HunaBatteryLevel(HunaEntity, SensorEntity):
    """Battery band broadcast by the blind; costs the blind nothing to read."""

    _attr_translation_key = "battery_level"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(BATTERY_BANDS.values())
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: HunaDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.address}_battery_level"

    @property
    def native_value(self) -> str | None:
        return BATTERY_BANDS.get(self._device.battery_band)


class HunaBatteryPercent(HunaEntity, RestoreSensor):
    """Exact battery percentage, refreshed whenever a command connects."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, device: HunaDevice) -> None:
        super().__init__(device)
        self._attr_unique_id = f"{device.address}_battery"

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._device.battery_percent is None and (
            last := await self.async_get_last_sensor_data()
        ):
            if isinstance(last.native_value, (int, float)):
                self._device.battery_percent = int(last.native_value)

    @property
    def native_value(self) -> int | None:
        return self._device.battery_percent
