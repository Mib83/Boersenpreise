"""Setup errors must identify ENTSO-E versus InfluxDB without secrets."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, patch
from test_api import api
from api_test_package.const import DEFAULTS

class FlowBase:
    def __init_subclass__(cls, **kwargs): pass

stubs={name:types.ModuleType(name) for name in (
    'probatio','homeassistant','homeassistant.config_entries','homeassistant.core',
    'homeassistant.helpers','homeassistant.helpers.selector','homeassistant.helpers.aiohttp_client')}
stubs['homeassistant.config_entries'].ConfigFlow=FlowBase
stubs['homeassistant.config_entries'].OptionsFlow=FlowBase
stubs['homeassistant'].config_entries=stubs['homeassistant.config_entries']
stubs['homeassistant.core'].callback=lambda fn:fn
stubs['homeassistant.helpers'].selector=stubs['homeassistant.helpers.selector']
stubs['homeassistant.helpers.aiohttp_client'].async_get_clientsession=lambda hass:None
spec=importlib.util.spec_from_file_location('api_test_package.config_flow',Path(__file__).resolve().parents[1]/'custom_components/boersenpreise/config_flow.py')
flow=importlib.util.module_from_spec(spec)
with patch.dict(sys.modules,{**stubs,'api_test_package.api':api}): spec.loader.exec_module(flow)

class SetupTests(unittest.IsolatedAsyncioTestCase):
    async def test_service_specific_failures(self):
        for enabled,fetch_error,write_error,code in [
            (False,api.AccessError(),None,'entsoe_invalid_auth'),
            (False,api.ConnectionError(),None,'entsoe_cannot_connect'),
            (True,None,api.AccessError(),'influx_invalid_auth'),
            (True,None,api.ConnectionError(),'influx_cannot_connect')]:
            data={**DEFAULTS,'token':' test-token ','influx_enabled':enabled,'influx_org':'org','influx_token':'influx-test'}
            fetch=AsyncMock(return_value=[{'ts':1,'eur_mwh':10}],side_effect=fetch_error)
            write=AsyncMock(side_effect=write_error)
            with patch.object(flow,'fetch_day',fetch),patch.object(flow,'write_influx',write):
                with self.assertRaises(flow.ConfigurationError) as caught: await flow.validate(None,data)
            self.assertEqual(str(caught.exception),code)
            if fetch_error: write.assert_not_awaited()

    async def test_no_prices_does_not_test_influx(self):
        data={**DEFAULTS,'token':'test-token','influx_enabled':True,'influx_org':'org','influx_token':'influx-test'}
        write=AsyncMock()
        with patch.object(flow,'fetch_day',AsyncMock(return_value=[])),patch.object(flow,'write_influx',write):
            with self.assertRaises(flow.ConfigurationError) as caught: await flow.validate(None,data)
        self.assertEqual(str(caught.exception),'entsoe_no_prices'); write.assert_not_awaited()

    async def test_success_strips_token_and_optional_influx(self):
        data={**DEFAULTS,'token':' test-token '}
        write=AsyncMock()
        with patch.object(flow,'fetch_day',AsyncMock(return_value=[{'ts':1,'eur_mwh':10}])),patch.object(flow,'write_influx',write):
            await flow.validate(None,data)
        self.assertEqual(data['token'],'test-token'); write.assert_not_awaited()

    async def test_color_picker_values_saved_without_losing_colors(self):
        data={**DEFAULTS,'token':'test-token','high_color':[255,0,0],'low_limit':0,'low_color':[0,0,255],'price_levels':[{'limit':5,'color':[0,255,0]}]}
        with patch.object(flow,'fetch_day',AsyncMock(return_value=[{'ts':1,'eur_mwh':10}])):
            await flow.validate(None,data)
        self.assertEqual(data['high_color'],'#ff0000')
        self.assertEqual(data['low_color'],'#0000ff')
        self.assertEqual(data['price_levels'],[{'limit':5.0,'color':'#00ff00'}])

    async def test_schema_uses_picker_for_all_colors_and_converts_old_defaults(self):
        defaults={}
        def required(key,default):
            defaults[key]=default
            return key
        selector_stubs={
            'TextSelector':lambda config:config,
            'TextSelectorConfig':lambda **kwargs:kwargs,
            'TextSelectorType':types.SimpleNamespace(PASSWORD='password'),
            'ColorRGBSelector':lambda:{'color_rgb':{}},
            'ObjectSelector':lambda config:{'object':config},
        }
        with patch.multiple(flow.vol,Required=required,Schema=lambda fields:fields,Coerce=lambda kind:kind,create=True),patch.multiple(flow.selector,**selector_stubs,create=True):
            fields=flow.schema(DEFAULTS)
        self.assertEqual(fields['high_color'],{'color_rgb':{}})
        self.assertEqual(fields['low_color'],{'color_rgb':{}})
        self.assertEqual(fields['price_levels']['object']['fields']['color']['selector'],{'color_rgb':{}})
        self.assertEqual(defaults['high_color'],[239,68,68])
        self.assertEqual(defaults['low_color'],[34,197,94])
        self.assertEqual(defaults['price_levels'][0]['color'],[34,197,94])
