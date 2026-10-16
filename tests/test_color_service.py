"""Exercise color service handlers and update behavior with HA adapters stubbed."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import AsyncMock, Mock, patch

ROOT=Path(__file__).resolve().parents[1]/'custom_components/boersenpreise'
name='service_test_package'
spec=importlib.util.spec_from_file_location(name,ROOT/'__init__.py',submodule_search_locations=[str(ROOT)])
service=importlib.util.module_from_spec(spec)

def require_admin(handler):
    async def wrapped(hass,connection,msg):
        if not connection.user.is_admin: raise PermissionError
        return await handler(hass,connection,msg)
    return wrapped

stubs={key:types.ModuleType(key) for key in ('probatio','homeassistant','homeassistant.components','homeassistant.components.frontend','homeassistant.components.panel_custom','homeassistant.components.websocket_api','homeassistant.components.http','homeassistant.const',name+'.coordinator')}
stubs['probatio'].Required=lambda key:key
stubs['probatio'].Optional=lambda key:key
ws=stubs['homeassistant.components.websocket_api']
ws.websocket_command=lambda schema:lambda handler:handler
ws.async_response=lambda handler:handler
ws.require_admin=require_admin
stubs['homeassistant.components.http'].StaticPathConfig=lambda *args:args
stubs['homeassistant.const'].Platform=types.SimpleNamespace(SENSOR='sensor')
stubs[name+'.coordinator'].PriceArchive=object
with patch.dict(sys.modules,{**stubs,name:service}):spec.loader.exec_module(service)

class ColorServiceTests(unittest.IsolatedAsyncioTestCase):
    def setup_context(self):
        entry=types.SimpleNamespace(data={'token':'private-token'},options={},entry_id='test')
        settings={**service.DEFAULTS,**entry.data}
        archive=types.SimpleNamespace(entry=entry,settings=settings,notify=Mock())
        def update(entry,options):entry.options=options
        entries=types.SimpleNamespace(async_update_entry=Mock(side_effect=update),async_reload=AsyncMock())
        hass=types.SimpleNamespace(data={service.DOMAIN:{'archive':archive}},config_entries=entries)
        connection=types.SimpleNamespace(user=types.SimpleNamespace(is_admin=True),send_result=Mock(),send_error=Mock())
        return hass,entry,archive,connection

    async def test_color_only_save_does_not_reload_or_expose_token(self):
        hass,entry,archive,connection=self.setup_context()
        await service.ws_colors(hass,connection,{'id':1,'settings':{'high_color':'#ff0000','low_color':'#0000ff','price_levels':[{'limit':5,'color':'#00ff00'}]}})
        await service.async_options_updated(hass,entry)
        hass.config_entries.async_reload.assert_not_awaited()
        archive.notify.assert_called_once()
        result=connection.send_result.call_args.args[1]
        self.assertEqual(set(result),{'high_color','low_color','price_levels'})
        self.assertNotIn('private-token',str(result))
        self.assertEqual(entry.data['token'],'private-token')

    async def test_changed_connection_still_reloads(self):
        hass,entry,archive,connection=self.setup_context()
        entry.options={'token':'new-token'}
        await service.async_options_updated(hass,entry)
        hass.config_entries.async_reload.assert_awaited_once_with('test')

    async def test_bad_payload_does_not_write(self):
        hass,entry,archive,connection=self.setup_context()
        await service.ws_colors(hass,connection,{'id':1,'settings':{'token':'overwrite'}})
        hass.config_entries.async_update_entry.assert_not_called()
        connection.send_error.assert_called_once()

    async def test_service_is_wrapped_in_admin_guard(self):
        hass,entry,archive,connection=self.setup_context();connection.user.is_admin=False
        with self.assertRaises(PermissionError):await service.ws_colors(hass,connection,{'id':1})
        connection.send_result.assert_not_called()
        hass.config_entries.async_update_entry.assert_not_called()
