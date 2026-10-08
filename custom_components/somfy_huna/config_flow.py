"""Config flow for Somfy Huna blinds."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import callback

from .const import CONF_INVERT, DEFAULT_NAME, DOMAIN, MANUFACTURER_ID


def _is_huna(info: BluetoothServiceInfoBleak) -> bool:
    return MANUFACTURER_ID in info.manufacturer_data or (info.name or "").startswith(
        DEFAULT_NAME
    )


def _label(info: BluetoothServiceInfoBleak) -> str:
    return f"{info.name or DEFAULT_NAME} ({info.address})"


class HunaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Add a blind found over Bluetooth."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None
        self._discovered: dict[str, BluetoothServiceInfoBleak] = {}

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return HunaOptionsFlow()

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": _label(discovery_info)}
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._discovery is not None
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data={CONF_ADDRESS: self._discovery.address},
            )
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {vol.Required(CONF_NAME, default=_label(self._discovery)): str}
            ),
            description_placeholders={"name": _label(self._discovery)},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input.get(CONF_NAME) or _label(self._discovered[address]),
                data={CONF_ADDRESS: address},
            )

        configured = self._async_current_ids()
        for info in async_discovered_service_info(self.hass, connectable=True):
            if info.address not in configured and _is_huna(info):
                self._discovered[info.address] = info
        if not self._discovered:
            return self.async_abort(reason="no_devices_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_ADDRESS): vol.In(
                        {a: _label(i) for a, i in self._discovered.items()}
                    ),
                    vol.Optional(CONF_NAME): str,
                }
            ),
        )


class HunaOptionsFlow(OptionsFlow):
    """Per-blind options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_INVERT,
                        default=self.config_entry.options.get(CONF_INVERT, False),
                    ): bool
                }
            ),
        )
