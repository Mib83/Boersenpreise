"""Only validated color settings may be edited through the compact view."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]/'custom_components/boersenpreise'
pkg=types.ModuleType('color_test_package');pkg.__path__=[str(ROOT)];sys.modules[pkg.__name__]=pkg
spec=importlib.util.spec_from_file_location('color_test_package.color_settings',ROOT/'color_settings.py')
settings=importlib.util.module_from_spec(spec);spec.loader.exec_module(settings)
from color_test_package.const import DEFAULTS

class ColorSettingsTests(unittest.TestCase):
    def test_projection_is_descending_and_contains_no_credentials(self):
        result=settings.color_options({**DEFAULTS,'token':'secret','influx_token':'secret2'})
        self.assertEqual(set(result),{'high_color','low_color','price_levels'})
        self.assertEqual([row['limit'] for row in result['price_levels']],[10,5])
        self.assertNotIn('secret',str(result))

    def test_save_preserves_connections_and_discards_removed_limit(self):
        existing={'token':'secret','influx_org':'org','low_limit':0}
        changes={'high_color':'#FF0000','low_color':[0,0,255],'price_levels':[{'limit':20,'color':'#ffff00'},{'limit':5,'color':'#00ff00'}]}
        result=settings.merge_color_options(existing,changes)
        self.assertEqual(result['token'],'secret')
        self.assertEqual(result['influx_org'],'org')
        self.assertEqual(result['low_color'],'#0000ff')
        self.assertNotIn('low_limit',result)
        self.assertIn('low_limit',existing)
        self.assertEqual([row['limit'] for row in result['price_levels']],[5,20])

    def test_extra_keys_and_empty_zones_rejected(self):
        base={'high_color':'#ff0000','low_color':'#0000ff','price_levels':[{'limit':5,'color':'#00ff00'}]}
        for changes in ({**base,'token':'overwrite'},{**base,'low_limit':0},{**base,'price_levels':[]}):
            with self.assertRaises(ValueError):settings.merge_color_options({},changes)
