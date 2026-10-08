"""Somfy Huna blind: passive state from advertisements, connect on demand."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import logging

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from homeassistant.components import bluetooth
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .const import (
    ADVERT_POSITION_FULL,
    CMD_STOP,
    MANUFACTURER_ID,
    POSITION_FULL,
    UUID_ADJUST,
    UUID_BATTERY,
    UUID_CHALLENGE,
    UUID_CHALLENGE_RESPONSE,
    UUID_POSITION,
    UUID_SYSTEM_ID,
)

_LOGGER = logging.getLogger(__name__)

# Key used by the vendor app's challenge-response.
_KEY = bytes(range(16))

# Connecting is the slow part of a command, so the link is kept for a short
# while afterwards: a stop or a second move then goes out immediately.
_HOLD_SECONDS = 20

# A command the blind acknowledged does not always start the motor. Each move
# is checked against the blind's own broadcast and sent again if nothing
# happened.
_VERIFY_SECONDS = 6
_RESEND_ATTEMPTS = 2
_AT_TARGET = 0.02

_ADVERT_MOVING = 0x80
_ADVERT_BATTERY_MASK = 0x03


def challenge_response(system_id: bytes, challenge: bytes) -> bytes:
    """Answer the blind's challenge the way the vendor app does."""
    if len(system_id) < 8 or len(challenge) < 13:
        raise HomeAssistantError("Unexpected challenge from blind")
    iv = bytes(
        [
            0x53, 0x4F, 0x20, 0x48, 0x61,
            system_id[7] ^ 114,
            system_id[6] ^ 97,
            system_id[5] ^ 108,
            system_id[4] ^ 100,
            system_id[3] ^ 66,
            challenge[0] ^ 108,
            challenge[2] ^ 197,
            challenge[4] ^ 116,
            challenge[8] ^ 97,
            challenge[10] ^ 110,
            challenge[12] ^ 100,
        ]
    )
    padder = padding.PKCS7(128).padder()
    encryptor = Cipher(algorithms.AES(_KEY), modes.CBC(iv)).encryptor()
    encrypted = encryptor.update(padder.update(challenge) + padder.finalize())
    encrypted += encryptor.finalize()
    return b"\x00" + encrypted[:16]


class HunaDevice:
    """One blind.

    State (travel, moving, battery band) is read from the advertisement the
    blind broadcasts anyway, so nothing connects to it until a command is
    sent.
    """

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        self.hass = hass
        self.address = address
        self.name = name
        self.travel: float | None = None  # 0.0 .. 1.0 as reported by the blind
        self.target_travel: float | None = None
        self.moving = False
        self.battery_band: int | None = None
        self.battery_percent: int | None = None
        self.available = False
        self._listeners: list[Callable[[], None]] = []
        self._lock = asyncio.Lock()
        self._client: BleakClientWithServiceCache | None = None
        self._release: asyncio.TimerHandle | None = None
        self._verify: asyncio.Task[None] | None = None

    @callback
    def async_add_listener(self, listener: Callable[[], None]) -> CALLBACK_TYPE:
        self._listeners.append(listener)
        return lambda: self._listeners.remove(listener)

    @callback
    def _notify(self) -> None:
        for listener in list(self._listeners):
            listener()

    @callback
    def async_start(self) -> list[CALLBACK_TYPE]:
        """Start listening for advertisements; returns the unsubscribers."""
        if info := bluetooth.async_last_service_info(
            self.hass, self.address, connectable=False
        ):
            self._handle_advertisement(info, bluetooth.BluetoothChange.ADVERTISEMENT)
        return [
            bluetooth.async_register_callback(
                self.hass,
                self._handle_advertisement,
                {"address": self.address, "connectable": False},
                bluetooth.BluetoothScanningMode.PASSIVE,
            ),
            bluetooth.async_track_unavailable(
                self.hass, self._handle_unavailable, self.address, connectable=False
            ),
        ]

    @callback
    def _handle_advertisement(
        self,
        info: bluetooth.BluetoothServiceInfoBleak,
        change: bluetooth.BluetoothChange,
    ) -> None:
        self.available = True
        # firmware id (2) + last 3 MAC bytes (3) + travel (1) + status (1);
        # status = battery band in the low bits, 0x80 set while the motor runs
        data = info.manufacturer_data.get(MANUFACTURER_ID)
        if data and len(data) >= 7:
            self.travel = min(data[5], ADVERT_POSITION_FULL) / ADVERT_POSITION_FULL
            self.moving = bool(data[6] & _ADVERT_MOVING)
            self.battery_band = data[6] & _ADVERT_BATTERY_MASK
            if not self.moving:
                self.target_travel = None
        self._notify()

    @callback
    def _handle_unavailable(self, info: bluetooth.BluetoothServiceInfoBleak) -> None:
        self.available = False
        self._notify()

    async def async_stop(self) -> None:
        self._cancel_verify()
        await self._command(UUID_ADJUST, bytes([CMD_STOP]))
        self.target_travel = None
        self._notify()

    async def async_set_travel(self, travel: float) -> None:
        """Move to a travel fraction, 0.0 .. 1.0 in the blind's own scale."""
        self._cancel_verify()
        travel = max(0.0, min(1.0, travel))
        payload = int(POSITION_FULL * travel).to_bytes(2, "big")
        started_from = self.travel
        await self._command(UUID_POSITION, payload)
        self.target_travel = travel
        self._notify()
        self._verify = self.hass.async_create_background_task(
            self._async_verify_move(travel, payload, started_from),
            f"somfy_huna verify {self.address}",
        )

    async def _async_verify_move(
        self, travel: float, payload: bytes, started_from: float | None
    ) -> None:
        for attempt in range(1, _RESEND_ATTEMPTS + 1):
            await asyncio.sleep(_VERIFY_SECONDS)
            if (
                self.moving
                or self.travel is None
                or self.travel != started_from
                or abs(self.travel - travel) <= _AT_TARGET
            ):
                return
            _LOGGER.info(
                "%s did not start moving; sending the move again (%s of %s)",
                self.name,
                attempt,
                _RESEND_ATTEMPTS,
            )
            try:
                await self._command(UUID_POSITION, payload)
            except HomeAssistantError as err:
                _LOGGER.warning("%s", err)

    @callback
    def _cancel_verify(self) -> None:
        if self._verify is not None and self._verify is not asyncio.current_task():
            self._verify.cancel()
        self._verify = None

    async def async_shutdown(self) -> None:
        """Stop checking and drop any held connection."""
        self._cancel_verify()
        async with self._lock:
            await self._disconnect()

    async def _async_release(self) -> None:
        async with self._lock:
            await self._disconnect()

    async def _command(self, uuid: str, payload: bytes) -> None:
        async with self._lock:
            self._cancel_release()
            try:
                try:
                    client = await self._ensure_connected()
                    await client.write_gatt_char(uuid, payload, response=True)
                except (BleakError, TimeoutError) as err:
                    # A held link can die quietly; try once more from scratch.
                    _LOGGER.debug("%s: retrying after %s", self.name, err)
                    await self._disconnect()
                    client = await self._ensure_connected()
                    await client.write_gatt_char(uuid, payload, response=True)
            except (BleakError, TimeoutError) as err:
                await self._disconnect()
                raise HomeAssistantError(
                    f"Could not send command to {self.name}: {err}"
                ) from err
            self._release = self.hass.loop.call_later(
                _HOLD_SECONDS, self._schedule_release
            )

    async def _ensure_connected(self) -> BleakClientWithServiceCache:
        if self._client is not None and self._client.is_connected:
            return self._client
        ble_device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if ble_device is None:
            raise HomeAssistantError(
                f"{self.name} is not in range of a connectable Bluetooth adapter or proxy"
            )
        client = await establish_connection(
            BleakClientWithServiceCache, ble_device, self.name
        )
        self._client = client
        system_id = await client.read_gatt_char(UUID_SYSTEM_ID)
        challenge = await client.read_gatt_char(UUID_CHALLENGE)
        await client.write_gatt_char(
            UUID_CHALLENGE_RESPONSE,
            challenge_response(bytes(system_id), bytes(challenge)),
            response=True,
        )
        try:
            battery = await client.read_gatt_char(UUID_BATTERY)
            self.battery_percent = battery[0]
        except BleakError as err:
            _LOGGER.debug("%s: battery read failed: %s", self.name, err)
        return client

    @callback
    def _cancel_release(self) -> None:
        if self._release is not None:
            self._release.cancel()
            self._release = None

    @callback
    def _schedule_release(self) -> None:
        self._release = None
        self.hass.async_create_task(self._async_release())

    async def _disconnect(self) -> None:
        self._cancel_release()
        client, self._client = self._client, None
        if client is not None:
            try:
                await client.disconnect()
            except (BleakError, TimeoutError) as err:
                _LOGGER.debug("%s: disconnect failed: %s", self.name, err)
