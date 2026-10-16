"""Validated color-only settings, independent of network credentials."""
from .prices import price_levels, color_hex, lower_price_rule


def color_options(settings):
    """Safe projection for the compact editor, highest price first."""
    return {
        "high_color": color_hex(settings["high_color"]),
        "price_levels": list(reversed(price_levels(settings))),
        "low_color": lower_price_rule(settings)["color"],
    }


def merge_color_options(existing, changes):
    if not isinstance(changes, dict) or set(changes) != {"high_color", "price_levels", "low_color"}:
        raise ValueError("Nur Farben und Preis Zohnen können hier gespeichert werden")
    levels = price_levels(changes)
    if not levels:
        raise ValueError("Bitte mindestens eine Preiszone hinzufügen")
    result = {**existing, "price_levels": levels,
              "high_color": color_hex(changes["high_color"]),
              "low_color": color_hex(changes["low_color"])}
    result.pop("low_limit", None)
    return result
