"""Cover platform for Somfy Huna blinds."""

from __future__ import annotations

from typing import Any

from homeassistant.components.cover import (
    ATTR_POSITION,
    CoverDeviceClass,
    CoverEntity,
    CoverEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import HunaConfigEntry
from .const import CONF_INVERT
from .device import HunaDevice
from .entity import HunaEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HunaConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    async_add_entities(
        [HunaCover(entry.runtime_data, entry.options.get(CONF_INVERT, False))]
    )


class HunaCover(HunaEntity, CoverEntity):
    """The blind itself.

    The blind's travel is taken as 0 % at its top limit and 100 % at its
    bottom limit; Home Assistant wants 100 = open. The invert option swaps
    that for blinds that turn out to be the other way round.
    """

    _attr_name = None
    _attr_device_class = CoverDeviceClass.SHADE
    _attr_supported_features = (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.STOP
        | CoverEntityFeature.SET_POSITION
    )

    def __init__(self, device: HunaDevice, invert: bool) -> None:
        super().__init__(device)
        self._invert = invert
        self._attr_unique_id = device.address

    @property
    def current_cover_position(self) -> int | None:
        if self._device.travel is None:
            return None
        travel = round(self._device.travel * 100)
        return travel if self._invert else 100 - travel

    @property
    def is_closed(self) -> bool | None:
        position = self.current_cover_position
        return None if position is None else position == 0

    def _heading(self) -> int | None:
        """+1 while opening, -1 while closing, None if unknown or still."""
        device = self._device
        if not device.moving or device.target_travel is None or device.travel is None:
            return None
        if device.target_travel == device.travel:
            return None
        down = device.target_travel > device.travel
        return -1 if down != self._invert else 1

    @property
    def is_opening(self) -> bool:
        return self._heading() == 1

    @property
    def is_closing(self) -> bool:
        return self._heading() == -1

    async def async_open_cover(self, **kwargs: Any) -> None:
        await self.async_set_cover_position(**{ATTR_POSITION: 100})

    async def async_close_cover(self, **kwargs: Any) -> None:
        await self.async_set_cover_position(**{ATTR_POSITION: 0})

    async def async_stop_cover(self, **kwargs: Any) -> None:
        await self._device.async_stop()

    async def async_set_cover_position(self, **kwargs: Any) -> None:
        position = kwargs[ATTR_POSITION]
        travel = position if self._invert else 100 - position
        await self._device.async_set_travel(travel / 100)
