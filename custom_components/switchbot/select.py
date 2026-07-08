"""Select platform for SwitchBot."""

from datetime import timedelta
import logging

import switchbot
from switchbot import (
    HorizontalOscillationAngle,
    NightLightState,
    SwitchbotOperationError,
    VerticalOscillationAngle,
)

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import SwitchbotConfigEntry, SwitchbotDataUpdateCoordinator
from .entity import SwitchbotEntity, exception_handler

_LOGGER = logging.getLogger(__name__)
PARALLEL_UPDATES = 0

SCAN_INTERVAL = timedelta(days=7)
TIME_FORMAT_12H = "12h"
TIME_FORMAT_24H = "24h"
TIME_FORMAT_OPTIONS = [TIME_FORMAT_12H, TIME_FORMAT_24H]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SwitchbotConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot select platform."""
    coordinator = entry.runtime_data

    if isinstance(coordinator.device, switchbot.SwitchbotMeterProCO2):
        async_add_entities([SwitchBotMeterProCO2TimeFormatSelect(coordinator)], True)
    elif isinstance(coordinator.device, switchbot.SwitchbotStandingFan):
        async_add_entities([SwitchBotStandingFanNightLightSelect(coordinator)])


NIGHT_LIGHT_OFF = "off"
NIGHT_LIGHT_SOFT = "soft"
NIGHT_LIGHT_BRIGHT = "bright"
NIGHT_LIGHT_OPTIONS = [NIGHT_LIGHT_OFF, NIGHT_LIGHT_SOFT, NIGHT_LIGHT_BRIGHT]
NIGHT_LIGHT_TO_STATE = {
    NIGHT_LIGHT_OFF: NightLightState.OFF,
    NIGHT_LIGHT_SOFT: NightLightState.LEVEL_2,
    NIGHT_LIGHT_BRIGHT: NightLightState.LEVEL_1,
}
STATE_TO_NIGHT_LIGHT = {v.value: k for k, v in NIGHT_LIGHT_TO_STATE.items()}


class SwitchBotStandingFanNightLightSelect(SwitchbotEntity, SelectEntity):
    """Night-light setting for SwitchBot Standing Fan (Off / Soft / Bright)."""

    _device: switchbot.SwitchbotStandingFan
    _attr_translation_key = "night_light"
    _attr_options = NIGHT_LIGHT_OPTIONS

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the night-light select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_night_light"

    @property
    def current_option(self) -> str | None:
        """Return the currently selected night-light state."""
        state = self._device.get_night_light_state()
        if state is None:
            return None
        return STATE_TO_NIGHT_LIGHT.get(state)

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Set night-light state."""
        await self._device.set_night_light(NIGHT_LIGHT_TO_STATE[option])
        self.async_write_ha_state()


class SwitchBotMeterProCO2TimeFormatSelect(SwitchbotEntity, SelectEntity):
    """Select entity to set time display format on Meter Pro CO2."""

    _attr_should_poll = True
    _attr_entity_registry_enabled_default = False
    _device: switchbot.SwitchbotMeterProCO2
    _attr_entity_category = EntityCategory.CONFIG
    _attr_translation_key = "time_format"
    _attr_options = TIME_FORMAT_OPTIONS

    def __init__(self, coordinator: SwitchbotDataUpdateCoordinator) -> None:
        """Initialize the select entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.base_unique_id}_time_format"

    @exception_handler
    async def async_select_option(self, option: str) -> None:
        """Change the time display format."""
        _LOGGER.debug("Setting time format to %s for %s", option, self._address)
        is_12h_mode = option == TIME_FORMAT_12H
        await self._device.set_time_display_format(is_12h_mode)
        self._attr_current_option = option
        self.async_write_ha_state()

    async def async_update(self) -> None:
        """Fetch the latest time format from the device."""
        try:
            device_time = await self._device.get_datetime()
        except SwitchbotOperationError:
            _LOGGER.debug(
                "Failed to update time format for %s", self._address, exc_info=True
            )
            return
        self._attr_current_option = (
            TIME_FORMAT_12H if device_time["12h_mode"] else TIME_FORMAT_24H
        )
