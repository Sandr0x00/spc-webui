from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.alarm_control_panel import (
    AlarmControlPanelEntity,
    AlarmControlPanelEntityFeature,
)
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up SPC alarm control panel entities from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    spc = data["spc"]

    device_name = (spc.site or spc.model or "SPC Panel")

    async_add_entities(
        [
            SPCAllAreasAlarm(
                coordinator=coordinator,
                spc=spc,
                device_name=device_name,
            )
        ]
    )


def spc_to_ha_state(spc_state):
    """Map SPC alarm state strings to Home Assistant alarm states."""
    return {
        "unset": "disarmed",
        "fullset": "armed_away",
    }.get(spc_state)


class SPCAllAreasAlarm(CoordinatorEntity, AlarmControlPanelEntity):
    """Alarm entity representing all SPC areas."""

    _attr_code_arm_required = False
    _attr_supported_features = AlarmControlPanelEntityFeature.ARM_AWAY

    def __init__(self, coordinator, spc, device_name):
        super().__init__(coordinator)
        self.spc = spc
        self._device_name = device_name

        device_id = f"spc_{spc.serial_number}"

        self._device_id = device_id
        self._attr_unique_id = f"{device_id}_all_areas"
        self._attr_name = "All Areas"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, device_id)},
            "name": device_name,
            "manufacturer": "Vanderbilt",
            "model": spc.model,
            "serial_number": spc.serial_number,
        }

    @property
    def alarm_state(self):
        return spc_to_ha_state(self.coordinator.data)

    async def async_alarm_disarm(self, code=None):
        await self.spc.set_state("unset")
        await self.coordinator.async_request_refresh()

    async def async_alarm_arm_away(self, code=None):
        await self.spc.set_state("fullset")
        await self.coordinator.async_request_refresh()
