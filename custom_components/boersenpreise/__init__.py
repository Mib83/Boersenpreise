"""Börsenpreise Home Assistant integration."""
from datetime import date
from pathlib import Path
import probatio as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from .const import DOMAIN, NAME, VERSION, DEFAULTS
from .coordinator import PriceArchive
from .color_settings import color_options, merge_color_options


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    websocket_api.async_register_command(hass, ws_day)
    websocket_api.async_register_command(hass, ws_colors)
    await hass.http.async_register_static_paths([
        StaticPathConfig(f"/{DOMAIN}/panel.js", str(Path(__file__).parent / "panel.js"), False)
    ])
    return True


async def async_setup_entry(hass, entry):
    archive = PriceArchive(hass, entry)
    hass.data[DOMAIN]["archive"] = archive
    await archive.start()
    try:
        await panel_custom.async_register_panel(hass, frontend_url_path=DOMAIN,
            webcomponent_name="boersenpreise-panel", sidebar_title=NAME,
            sidebar_icon="mdi:chart-bar", module_url=f"/{DOMAIN}/panel.js?v={VERSION}")
        await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    except Exception:
        await archive.stop()
        hass.data[DOMAIN].pop("archive", None)
        frontend.async_remove_panel(hass, DOMAIN)
        raise
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    return True


async def async_options_updated(hass, entry):
    archive = hass.data.get(DOMAIN, {}).get("archive")
    settings = {**DEFAULTS, **entry.data, **entry.options}
    connection_keys = ("token", "import_start", "influx_enabled", "influx_url", "influx_org", "influx_bucket", "influx_token")
    if archive and all(archive.settings.get(key) == settings.get(key) for key in connection_keys):
        archive.settings = settings
        archive.notify()
        return
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass, entry):
    if not await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR]):
        return False
    archive = hass.data[DOMAIN].pop("archive", None)
    if archive:
        await archive.stop()
    frontend.async_remove_panel(hass, DOMAIN)
    return True


@websocket_api.websocket_command({vol.Required("type"): "boersenpreise/day", vol.Required("day"): str})
@websocket_api.async_response
async def ws_day(hass, connection, msg):
    try:
        day = date.fromisoformat(msg["day"]).isoformat()
    except ValueError:
        connection.send_error(msg["id"], "invalid_date", "Ungültiges Datum")
        return
    archive = hass.data.get(DOMAIN, {}).get("archive")
    if archive is None:
        connection.send_error(msg["id"], "not_loaded", "Integration nicht geladen")
        return
    connection.send_result(msg["id"], archive.snapshot(day))


@websocket_api.websocket_command({vol.Required("type"): "boersenpreise/colors",
                                   vol.Optional("settings"): dict})
@websocket_api.require_admin
@websocket_api.async_response
async def ws_colors(hass, connection, msg):
    """Read or update colors without exposing tokens or contacting services."""
    archive = hass.data.get(DOMAIN, {}).get("archive")
    if archive is None:
        connection.send_error(msg["id"], "not_loaded", "Integration nicht geladen")
        return
    entry = archive.entry
    if "settings" in msg:
        try:
            options = merge_color_options(entry.options, msg["settings"])
        except (ValueError, TypeError):
            connection.send_error(msg["id"], "invalid_settings", "Bitte eindeutige Preise, gültige Farben und mindestens eine Preiszone eingeben")
            return
        hass.config_entries.async_update_entry(entry, options=options)
        # Keep the current view consistent while the entry reload is scheduled.
        archive.settings.update(options)
    connection.send_result(msg["id"], color_options(archive.settings))
