"""Network clients. Never log URLs or response bodies containing credentials."""
import asyncio
from decimal import InvalidOperation
from xml.etree.ElementTree import ParseError
from datetime import datetime, timezone
import aiohttp
from .const import ZONE
from .prices import day_bounds, parse_prices, influx_lines


class AccessError(Exception):
    """Access denied."""


class ConnectionError(Exception):
    """Service unavailable or invalid response."""


async def fetch_day(session, token, day):
    start, end = day_bounds(day)
    params = {"securityToken": token, "documentType": "A44", "in_Domain": ZONE,
              "out_Domain": ZONE, "periodStart": start.strftime("%Y%m%d%H%M"),
              "periodEnd": end.strftime("%Y%m%d%H%M")}
    try:
        async with session.get("https://web-api.tp.entsoe.eu/api", params=params,
                               timeout=aiohttp.ClientTimeout(total=45)) as response:
            if response.status in (401, 403):
                raise AccessError("ENTSO-E-Zugang abgelehnt")
            if response.status not in (200, 400):
                raise ConnectionError(f"ENTSO-E HTTP {response.status}")
            return [r for r in parse_prices(await response.text()) if start.timestamp() <= r["ts"] < end.timestamp()]
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, ParseError, InvalidOperation, TypeError):
        raise ConnectionError("ENTSO-E-Abruf fehlgeschlagen") from None


async def write_influx(session, settings, rows):
    if not rows:
        return
    try:
        async with session.post(settings["influx_url"].rstrip("/") + "/api/v2/write",
                params={"org": settings["influx_org"], "bucket": settings["influx_bucket"], "precision": "s"},
                headers={"Authorization": "Token " + settings["influx_token"], "Content-Type": "text/plain; charset=utf-8"},
                data=influx_lines(rows).encode(), timeout=aiohttp.ClientTimeout(total=30)) as response:
            if response.status in (401, 403):
                raise AccessError("InfluxDB-Zugang abgelehnt")
            if response.status != 204:
                raise ConnectionError(f"InfluxDB HTTP {response.status}")
    except (aiohttp.ClientError, asyncio.TimeoutError):
        raise ConnectionError("InfluxDB nicht erreichbar") from None
