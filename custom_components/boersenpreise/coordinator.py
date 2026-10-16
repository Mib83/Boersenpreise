"""Persistent price archive and resumable background import."""
import asyncio
from datetime import date, datetime, timedelta
import hashlib
import json
import time
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send
from .api import fetch_day, write_influx, AccessError, ConnectionError
from .const import DEFAULTS, DOMAIN
from .prices import BERLIN, complete_day, day_bounds, price_levels, lower_price_rule


class PriceArchive:
    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        self.settings = {**DEFAULTS, **entry.data, **entry.options}
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}")
        self.days = {}
        self.written = {}
        self.error = None
        self.influx_error = None
        self.task = None
        self.session = async_get_clientsession(hass)
        self.destination = hashlib.sha256(json.dumps([self.settings[k] for k in (
            "influx_url", "influx_org", "influx_bucket")]).encode()).hexdigest()

    async def start(self):
        saved = await self.store.async_load() or {}
        self.days = saved.get("days", {})
        self.written = saved.get("written", {}) if saved.get("destination") == self.destination else {}
        self.task = self.hass.async_create_background_task(self.run(), f"{DOMAIN} import")

    async def stop(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        await self.save()

    async def save(self):
        await self.store.async_save({"days": self.days, "written": self.written, "destination": self.destination})

    def notify(self):
        async_dispatcher_send(self.hass, DOMAIN + "_updated")

    async def retrieve(self, day):
        rows = await fetch_day(self.session, self.settings["token"], day)
        key = day.isoformat()
        if rows:
            self.days[key] = rows
            self.written.pop(key, None)
            await self.save()

    async def export(self, key):
        await write_influx(self.session, self.settings, self.days[key])
        self.written[key] = True
        self.influx_error = None
        await self.save()

    async def run(self):
        live_at = 0
        retry = {}
        influx_at = 0
        while True:
            today = datetime.now(BERLIN).date()
            try:
                if time.monotonic() >= live_at:
                    live_at = time.monotonic() + 900
                    await self.retrieve(today)
                    await asyncio.sleep(1)
                    await self.retrieve(today + timedelta(days=1))
                    self.error = None
                day = date.fromisoformat(self.settings["import_start"])
                while day < today:
                    key = day.isoformat()
                    if not complete_day(day, self.days.get(key, [])) and time.monotonic() >= retry.get(key, 0):
                        retry[key] = time.monotonic() + 3600
                        await self.retrieve(day)
                        self.error = None
                        break
                    day += timedelta(days=1)
            except (AccessError, ConnectionError, ValueError):
                self.error = "ENTSO-E-Abruf fehlgeschlagen. Zugang und Verbindung prüfen; erneuter Versuch folgt."
                live_at = min(live_at, time.monotonic()+60)
                await asyncio.sleep(30)
            if self.settings["influx_enabled"] and time.monotonic() >= influx_at:
                key = next((key for key in sorted(self.days) if not self.written.get(key)), None)
                if key:
                    try:
                        await self.export(key)
                    except (AccessError, ConnectionError):
                        self.influx_error = "InfluxDB-Schreiben fehlgeschlagen. Lokale Preise bleiben erhalten; Wiederholung folgt."
                        influx_at = time.monotonic() + 60
            self.notify()
            await asyncio.sleep(2)

    def snapshot(self, day):
        settings = {k: self.settings[k] for k in ("green_limit", "yellow_limit", "green_color", "yellow_color", "high_color", "import_start")}
        settings["price_levels"] = price_levels(self.settings)
        lower = lower_price_rule(self.settings)
        settings["low_limit"], settings["low_color"] = lower["limit"], lower["color"]
        today = datetime.now(BERLIN).date()
        total = max(0, (today-date.fromisoformat(self.settings["import_start"])).days)
        complete = sum(1 for key, rows in self.days.items() if self.settings["import_start"] <= key < today.isoformat() and complete_day(key, rows))
        start, end = day_bounds(day)
        return {"day": day, "prices": self.days.get(day, []), "settings": settings,
                "start_ts": int(start.timestamp()), "end_ts": int(end.timestamp()),
                "expected": int((end-start).total_seconds()/900),
                "complete": complete, "total": total, "error": self.error,
                "influx_error": self.influx_error, "influx_enabled": self.settings["influx_enabled"],
                "influx_pending": sum(not self.written.get(k, False) for k in self.days) if self.settings["influx_enabled"] else 0}
