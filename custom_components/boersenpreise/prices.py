"""Pure ENTSO-E parsing, time ranges and Influx line protocol."""
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import re
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

BERLIN = ZoneInfo("Europe/Berlin")


def day_bounds(day):
    day = date.fromisoformat(day) if isinstance(day, str) else day
    start = datetime.combine(day, datetime.min.time(), BERLIN)
    end = datetime.combine(day + timedelta(days=1), datetime.min.time(), BERLIN)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def parse_prices(xml):
    """Expand A01/A03 curves without inventing values for gaps in A01."""
    root = ET.fromstring(xml)
    for node in root.iter():
        node.tag = node.tag.split("}")[-1]
    if root.tag == "Acknowledgement_MarketDocument":
        reasons = " ".join(n.text or "" for n in root.findall(".//Reason/text")).lower()
        if "no matching data" in reasons or "no data found" in reasons:
            return []
        raise ValueError("ENTSO-E hat die Anfrage abgelehnt")
    if root.tag != "Publication_MarketDocument":
        raise ValueError("Unerwartete ENTSO-E-Antwort")
    result = {}
    for series in root.findall(".//TimeSeries"):
        # DE-LU also publishes EXAA (sequence 2). Never mix it into SDAC.
        sequence = series.findtext("classificationSequence_AttributeInstanceComponent.position")
        contract = series.findtext("contract_MarketAgreement.type")
        if sequence not in (None, "1") or contract not in (None, "A01"):
            continue
        if series.findtext("currency_Unit.name") != "EUR" or series.findtext("price_Measure_Unit.name") != "MWH":
            raise ValueError("Unerwartete Währung oder Preiseinheit")
        curve = series.findtext("curveType", "A01")
        if curve not in ("A01", "A03"):
            raise ValueError("Nicht unterstützter Kurventyp")
        for period in series.findall("Period"):
            resolution = period.findtext("resolution")
            if resolution != "PT15M":
                raise ValueError("Keine echten Viertelstundenwerte erhalten")
            start = datetime.fromisoformat(period.findtext("timeInterval/start").replace("Z", "+00:00"))
            end = datetime.fromisoformat(period.findtext("timeInterval/end").replace("Z", "+00:00"))
            count = int((end-start).total_seconds() / 900)
            points = sorted((int(p.findtext("position")), Decimal(p.findtext("price.amount"))) for p in period.findall("Point"))
            for index, (position, value) in enumerate(points):
                if not value.is_finite() or not 1 <= position <= count:
                    raise ValueError("Ungültiger Preispunkt")
                stop = points[index+1][0] if curve == "A03" and index+1 < len(points) else (count+1 if curve == "A03" else position+1)
                for pos in range(position, stop):
                    timestamp = int(start.timestamp()) + (pos-1)*900
                    price = float(value)
                    if timestamp in result and result[timestamp] != price:
                        raise ValueError("Widersprüchliche Preisreihen erhalten")
                    result[timestamp] = price
    return [{"ts": ts, "eur_mwh": price} for ts, price in sorted(result.items())]


def complete_day(day, rows):
    start, end = day_bounds(day)
    expected = set(range(int(start.timestamp()), int(end.timestamp()), 900))
    return {r["ts"] for r in rows} == expected


def influx_lines(rows):
    return "\n".join(
        f"boersenpreise,zone=DE-LU eur_mwh={r['eur_mwh']},ct_kwh={r['eur_mwh']/10} {r['ts']}"
        for r in rows
    )


def price_levels(settings):
    """Normalize dynamic levels, preserving pre-v0.0.3 configuration."""
    levels = settings.get("price_levels")
    if levels is None:
        levels = [{"limit": settings["green_limit"], "color": settings["green_color"]},
                  {"limit": settings["yellow_limit"], "color": settings["yellow_color"]}]
    if not isinstance(levels, list):
        raise ValueError("Preisziele müssen eine Liste sein")
    normalized = []
    for level in levels:
        if not isinstance(level, dict) or set(level) != {"limit", "color"}:
            raise ValueError("Jedes Preisziel benötigt Preis und Farbe")
        try:
            limit = float(level["limit"])
        except (ValueError, TypeError):
            raise ValueError("Ungültiges Preisziel") from None
        color = level["color"]
        if isinstance(level["limit"], bool) or not float("-inf") < limit < float("inf"):
            raise ValueError("Ungültiges Preisziel")
        if not isinstance(color, str) or not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
            raise ValueError("Farben bitte als #RRGGBB eingeben")
        normalized.append({"limit": limit, "color": color.lower()})
    normalized.sort(key=lambda level: level["limit"])
    if len({level["limit"] for level in normalized}) != len(normalized):
        raise ValueError("Preisziele dürfen nicht doppelt vorkommen")
    return normalized


def validate_settings(settings):
    from .const import START
    start = date.fromisoformat(settings["import_start"])
    if start < date.fromisoformat(START) or start > datetime.now(BERLIN).date():
        raise ValueError("Importstart muss zwischen 01.10.2025 und heute liegen")
    low, high = float(settings["green_limit"]), float(settings["yellow_limit"])
    if "price_levels" not in settings and not (float("-inf") < low < high < float("inf")):
        raise ValueError("Die erste Farbgrenze muss kleiner als die zweite sein")
    price_levels(settings)
    for key in ("green_color", "yellow_color", "high_color"):
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", settings[key]):
            raise ValueError("Farben bitte als #RRGGBB eingeben")
    if settings["influx_enabled"]:
        from urllib.parse import urlsplit
        url = urlsplit(settings["influx_url"])
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError("Ungültige InfluxDB-Adresse")
        if not all(settings[k].strip() for k in ("influx_org", "influx_bucket", "influx_token")):
            raise ValueError("InfluxDB-Zugang ist unvollständig")
    return settings
