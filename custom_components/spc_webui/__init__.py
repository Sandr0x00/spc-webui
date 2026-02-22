import logging
from datetime import timedelta

import httpx
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import (
    CONF_EDP_PORT,
    CONF_EDP_SYSTEM_ID,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    CONF_URL,
    CONF_USERID,
    DEFAULT_EDP_PORT,
    DEFAULT_EDP_SYSTEM_ID,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    MANUFACTURER,
    PLATFORMS,
)
from .edp import EdpListener
from .spc import SPCError, SPCSession

LOGGER = logging.getLogger(__name__)

# Map EDP event class codes to zone state mutations.
# Each value is a dict merged into the zone's data.
EDP_ZONE_EVENTS = {
    "ZO": {"input": "open", "status": "actuated"},
    "ZC": {"input": "closed", "status": "normal"},
    "ZD": {"status": "tamper"},
    "BA": {"status": "actuated"},
    "BR": {"status": "normal"},
    "FA": {"status": "actuated"},
    "FR": {"status": "normal"},
}

# Map EDP event class codes to arm state values.
EDP_ARM_EVENTS = {
    "CG": "fullset",
    "OG": "unset",
    "NL": "partset",
}


async def async_setup_entry(hass, entry):
    url = entry.data[CONF_URL]
    userid = entry.data[CONF_USERID]
    password = entry.data[CONF_PASSWORD]

    poll_seconds = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )
    poll_interval = timedelta(seconds=int(poll_seconds))

    edp_port = int(entry.options.get(
        CONF_EDP_PORT,
        entry.data.get(CONF_EDP_PORT, DEFAULT_EDP_PORT),
    ))
    edp_system_id = int(entry.options.get(
        CONF_EDP_SYSTEM_ID,
        entry.data.get(CONF_EDP_SYSTEM_ID, DEFAULT_EDP_SYSTEM_ID),
    ))

    spc = SPCSession(url=url, userid=userid, password=password)
    await spc.login()

    async def update():
        try:
            return {
                "arm_state": await spc.get_arm_state(),
                "zones": {zone["zone_id"]: zone
                          for zone in await spc.get_zones()},
            }

        except SPCError as e:
            # Treat as hard failure. Show unavailable.
            raise UpdateFailed(str(e)) from e

        except (httpx.HTTPError, ValueError) as e:
            raise UpdateFailed(f"SPC communication error: {e!s}") from e

    coordinator = DataUpdateCoordinator(
        hass,
        LOGGER,
        config_entry=entry,
        name="SPC WebUI",
        update_interval=poll_interval,
        update_method=update,
        always_update=False,
    )
    await coordinator.async_config_entry_first_refresh()

    alarm_device_id = (DOMAIN, f"{spc.serial_number}-alarm")
    alarm_device_info = DeviceInfo({
        "identifiers": {alarm_device_id},
        "name": (spc.site or "SPC Panel"),
        "manufacturer": MANUFACTURER,
        "model": spc.model,
        "serial_number": spc.serial_number,
    })

    def get_zone_device_info(zone):
        return DeviceInfo({
            "identifiers": {(DOMAIN, f"{spc.serial_number}-zone{zone["zone_id"]}")},
            "name": f"Zone {zone["zone_id"]} {zone["zone_name"]}",
            "manufacturer": MANUFACTURER,
            "model": f"{spc.model} Zone",
            "via_device": alarm_device_id,
        })

    # Start EDP listener if configured.
    edp_listener = None
    if edp_port > 0:
        def on_edp_event(event):
            data = coordinator.data
            if data is None:
                return

            cls = event.event_class

            if cls in EDP_ARM_EVENTS:
                new_data = {**data, "arm_state": EDP_ARM_EVENTS[cls]}
                coordinator.async_set_updated_data(new_data)
                return

            if cls in EDP_ZONE_EVENTS:
                zone_id = event.device_id
                zones = data.get("zones", {})
                if zone_id in zones:
                    updated_zone = {**zones[zone_id], **EDP_ZONE_EVENTS[cls]}
                    new_zones = {**zones, zone_id: updated_zone}
                    new_data = {**data, "zones": new_zones}
                    coordinator.async_set_updated_data(new_data)
                else:
                    LOGGER.debug(
                        "EDP event for unknown zone %d (class=%s)",
                        zone_id, cls,
                    )
                return

            LOGGER.debug("EDP unhandled event class: %s", cls)

        edp_listener = EdpListener(
            port=edp_port,
            system_id=edp_system_id,
            callback=on_edp_event,
        )
        await edp_listener.start()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "spc": spc,
        "coordinator": coordinator,
        "alarm_device_info": alarm_device_info,
        "get_zone_device_info": get_zone_device_info,
        "unique_prefix": f"spc{spc.serial_number}",
        "edp_listener": edp_listener,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            if data.get("edp_listener"):
                await data["edp_listener"].stop()
            await data["spc"].aclose()
    return unload_ok
