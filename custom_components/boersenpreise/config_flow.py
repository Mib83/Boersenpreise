"""UI setup and editable options."""
from datetime import datetime
import probatio as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, NAME, DEFAULTS
from .prices import validate_settings, price_levels, BERLIN
from .api import fetch_day, write_influx, AccessError, ConnectionError


def schema(values):
    fields = {vol.Required("token", default=values.get("token", "")): selector.TextSelector(
        selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))}
    for key, default in DEFAULTS.items():
        if key in ("green_limit", "yellow_limit", "green_color", "yellow_color"):
            continue
        value = values.get(key, default)
        field = vol.Required(key, default=value)
        if key == "influx_token":
            fields[field] = selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD))
        elif isinstance(default, bool):
            fields[field] = bool
        elif isinstance(default, float):
            fields[field] = vol.Coerce(float)
        else:
            fields[field] = str
    level_defaults = values["price_levels"] if "price_levels" in values else price_levels({**DEFAULTS, **values})
    fields[vol.Required("price_levels", default=level_defaults)] = selector.ObjectSelector({
        "multiple": True,
        "label_field": "limit",
        "description_field": "color",
        "fields": {
            "limit": {"label": "Preisobergrenze", "required": True,
                      "selector": {"number": {"mode": "box", "step": "any", "unit_of_measurement": "ct/kWh"}}},
            "color": {"label": "Farbe (#RRGGBB)", "required": True, "default": "#22c55e",
                      "selector": {"text": {}}},
        },
    })
    return vol.Schema(fields)


class ConfigurationError(Exception):
    """A safe, translated error identifying the failing service."""


async def validate(hass, data):
    data.update({**DEFAULTS, **data})
    validate_settings(data)
    data["price_levels"] = price_levels(data)
    session = async_get_clientsession(hass)
    try:
        rows = await fetch_day(session, data["token"].strip(), datetime.now(BERLIN).date())
    except AccessError:
        raise ConfigurationError("entsoe_invalid_auth") from None
    except ConnectionError:
        raise ConfigurationError("entsoe_cannot_connect") from None
    if not rows:
        raise ConfigurationError("entsoe_no_prices")
    if data["influx_enabled"]:
        try:
            await write_influx(session, data, rows[:1])
        except AccessError:
            raise ConfigurationError("influx_invalid_auth") from None
        except ConnectionError:
            raise ConfigurationError("influx_cannot_connect") from None
    data["token"] = data["token"].strip()


class BoersenpreiseConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id("DE-LU")
        self._abort_if_unique_id_configured()
        errors = {}
        if user_input is not None:
            try:
                await validate(self.hass, user_input)
            except ConfigurationError as err:
                errors["base"] = str(err)
            except ValueError:
                errors["base"] = "invalid_settings"
            else:
                return self.async_create_entry(title=NAME, data=user_input)
        return self.async_show_form(step_id="user", data_schema=schema(user_input or DEFAULTS), errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return BoersenpreiseOptionsFlow()


class BoersenpreiseOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await validate(self.hass, user_input)
            except ConfigurationError as err:
                errors["base"] = str(err)
            except ValueError:
                errors["base"] = "invalid_settings"
            else:
                return self.async_create_entry(title="", data=user_input)
        values = {**DEFAULTS, **self.config_entry.data, **self.config_entry.options}
        return self.async_show_form(step_id="init", data_schema=schema(user_input or values), errors=errors)
