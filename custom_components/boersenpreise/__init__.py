"""Börsenpreise Home Assistant integration."""
from datetime import date
from pathlib import Path
import probatio as vol
from homeassistant.components import frontend, panel_custom, websocket_api
from homeassistant.components.http import StaticPathConfig
from homeassistant.const import Platform
from .const import DOMAIN, NAME, VERSION
from .coordinator import PriceArchive


async def async_setup(hass, config):
    hass.data.setdefault(DOMAIN, {})
    websocket_api.async_register_command(hass, ws_day)
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
