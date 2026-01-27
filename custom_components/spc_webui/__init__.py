import logging
from datetime import timedelta

from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)
import httpx

from .const import (
    DOMAIN,
    PLATFORMS,
    CONF_URL,
    CONF_USERID,
    CONF_PASSWORD,
    CONF_POLL_INTERVAL,
    DEFAULT_POLL_INTERVAL,
)
from .spc import SPCSession, SPCLoginError


LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry):
    url = entry.data[CONF_URL]
    userid = entry.data[CONF_USERID]
    password = entry.data[CONF_PASSWORD]

    poll_seconds = entry.options.get(
        CONF_POLL_INTERVAL,
        entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL),
    )
    poll_interval = timedelta(seconds=int(poll_seconds))

    spc = SPCSession(url=url, userid=userid, password=password)
    await spc.login()

    async def update():
        try:
            return await spc.get_state()
        
        except SPCLoginError as e:
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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "spc": spc,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry):
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id, None)
        if data:
            await data["spc"].aclose()
    return unload_ok
