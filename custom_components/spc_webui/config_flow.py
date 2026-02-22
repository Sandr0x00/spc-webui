import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

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
)
from .spc import SPCLoginError, SPCSession

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_URL): str,
        vol.Required(CONF_USERID): str,
        vol.Required(CONF_PASSWORD): str,
        vol.Optional(CONF_POLL_INTERVAL, default=DEFAULT_POLL_INTERVAL): vol.Coerce(int),
        vol.Optional(CONF_EDP_PORT, default=DEFAULT_EDP_PORT): vol.Coerce(int),
        vol.Optional(CONF_EDP_SYSTEM_ID, default=DEFAULT_EDP_SYSTEM_ID): vol.Coerce(int),
    }
)


class SPCWebUIConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle user setup of the SPC WebUI integration."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            url = user_input[CONF_URL]
            userid = user_input[CONF_USERID]
            password = user_input[CONF_PASSWORD]
            poll_interval = user_input.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
            edp_port = user_input.get(CONF_EDP_PORT, DEFAULT_EDP_PORT)
            edp_system_id = user_input.get(CONF_EDP_SYSTEM_ID, DEFAULT_EDP_SYSTEM_ID)

            spc = SPCSession(url=url, userid=userid, password=password)
            try:
                await spc.login()
            except SPCLoginError:
                errors["base"] = "invalid_auth"
            except Exception:
                errors["base"] = "cannot_connect"
            finally:
                await spc.aclose()

            if not errors:
                await self.async_set_unique_id(spc.serial_number)

                return self.async_create_entry(
                    title=url,
                    data={
                        CONF_URL: url,
                        CONF_USERID: userid,
                        CONF_PASSWORD: password,
                        CONF_POLL_INTERVAL: poll_interval,
                        CONF_EDP_PORT: edp_port,
                        CONF_EDP_SYSTEM_ID: edp_system_id,
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SPCWebUIOptionsFlow()


class SPCWebUIOptionsFlow(config_entries.OptionsFlow):
    """Options flow to tweak polling interval after setup."""

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_poll = self.config_entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)
        current_edp_port = self.config_entry.data.get(CONF_EDP_PORT, DEFAULT_EDP_PORT)
        current_edp_system_id = self.config_entry.data.get(CONF_EDP_SYSTEM_ID, DEFAULT_EDP_SYSTEM_ID)

        schema = vol.Schema(
            {
                vol.Optional(CONF_POLL_INTERVAL, default=current_poll): vol.Coerce(int),
                vol.Optional(CONF_EDP_PORT, default=current_edp_port): vol.Coerce(int),
                vol.Optional(CONF_EDP_SYSTEM_ID, default=current_edp_system_id): vol.Coerce(int),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
