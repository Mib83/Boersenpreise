"""Current and next quarter-hour prices."""
from datetime import datetime, timedelta, timezone
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.event import async_track_utc_time_change
from .const import DOMAIN, NAME, VERSION
from .prices import BERLIN


async def async_setup_entry(hass, entry, async_add_entities):
    archive = hass.data[DOMAIN]["archive"]
    async_add_entities([PriceSensor(archive, entry, offset) for offset in (0, 900)])


class PriceSensor(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False
    _attr_native_unit_of_measurement = "ct/kWh"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:currency-eur"

    def __init__(self, archive, entry, offset):
        self.archive = archive
        self.offset = offset
        self._attr_unique_id = f"{entry.entry_id}_{offset}"
        self._attr_name = "Aktueller Börsenpreis" if offset == 0 else "Nächster Börsenpreis"
        self._attr_device_info = {"identifiers": {(DOMAIN, entry.entry_id)}, "name": NAME,
                                  "manufacturer": "ENTSO-E", "model": "Day-Ahead DE-LU", "sw_version": VERSION}

    async def async_added_to_hass(self):
        self.async_on_remove(async_dispatcher_connect(self.hass, DOMAIN+"_updated", self.async_write_ha_state))
        self.async_on_remove(async_track_utc_time_change(self.hass, self._tick, minute=[0, 15, 30, 45], second=0))

    @callback
    def _tick(self, now):
        self.async_write_ha_state()

    @property
    def native_value(self):
        now = datetime.now(timezone.utc).timestamp()
        ts = int(now // 900)*900+self.offset
        key = datetime.fromtimestamp(ts, BERLIN).date().isoformat()
        row = next((r for r in self.archive.days.get(key, []) if r["ts"] == ts), None)
        return row["eur_mwh"]/10 if row else None

    @property
    def available(self):
        return self.native_value is not None
