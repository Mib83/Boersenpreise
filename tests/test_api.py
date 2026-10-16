"""HTTP contract tests using fake transport, with no network access."""
import asyncio
import importlib.util
from pathlib import Path
import sys
import types
import unittest

ROOT=Path(__file__).resolve().parents[1]/'custom_components/boersenpreise'
pkg=types.ModuleType('api_test_package'); pkg.__path__=[str(ROOT)]; sys.modules[pkg.__name__]=pkg
transport=types.ModuleType('aiohttp')
transport.ClientError=type('ClientError',(Exception,),{})
transport.ClientTimeout=lambda **kwargs: kwargs
sys.modules.setdefault('aiohttp',transport)
spec=importlib.util.spec_from_file_location('api_test_package.api',ROOT/'api.py')
api=importlib.util.module_from_spec(spec); spec.loader.exec_module(api)

class Response:
    def __init__(self,status,body=''): self.status=status; self.body=body
    async def __aenter__(self): return self
    async def __aexit__(self,*args): return False
    async def text(self): return self.body

class Session:
    def __init__(self,response): self.response=response; self.request=None
    def get(self,url,**kwargs): self.request=(url,kwargs); return self.response
    def post(self,url,**kwargs): self.request=(url,kwargs); return self.response

class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def test_unpublished_tomorrow_is_not_connection_failure(self):
        response=Response(400,'<Acknowledgement_MarketDocument><Reason><code>999</code><text>No matching data found</text></Reason></Acknowledgement_MarketDocument>')
        self.assertEqual(await api.fetch_day(Session(response),'test-token','2025-10-01'),[])

    async def test_auth_failure(self):
        with self.assertRaises(api.AccessError): await api.fetch_day(Session(Response(401)),'test-token','2025-10-01')

    async def test_server_failure(self):
        with self.assertRaises(api.ConnectionError): await api.fetch_day(Session(Response(503)),'test-token','2025-10-01')

    async def test_malformed_xml_does_not_escape(self):
        with self.assertRaises(api.ConnectionError): await api.fetch_day(Session(Response(200,'<broken')),'test-token','2025-10-01')

    async def test_dst_request_is_25_hours_in_utc(self):
        session=Session(Response(400,'<Acknowledgement_MarketDocument><Reason><text>No matching data found</text></Reason></Acknowledgement_MarketDocument>'))
        await api.fetch_day(session,'test-token','2025-10-26')
        params=session.request[1]['params']
        self.assertEqual((params['periodStart'],params['periodEnd']),('202510252200','202510262300'))
        self.assertEqual(params['in_Domain'],params['out_Domain'])

    async def test_influx_write(self):
        session=Session(Response(204))
        settings={'influx_url':'http://localhost:8086/','influx_org':'test org','influx_bucket':'prices','influx_token':'test-token'}
        await api.write_influx(session,settings,[{'ts':100,'eur_mwh':-20}])
        url,kwargs=session.request
        self.assertEqual(url,'http://localhost:8086/api/v2/write')
        self.assertEqual(kwargs['params']['precision'],'s')
        self.assertIn(b'ct_kwh=-2.0',kwargs['data'])
        self.assertNotIn('test-token',url)

    async def test_influx_failure_is_not_marked_successful(self):
        settings={'influx_url':'http://localhost:8086','influx_org':'org','influx_bucket':'prices','influx_token':'test-token'}
        with self.assertRaises(api.ConnectionError):
            await api.write_influx(Session(Response(500)),settings,[{'ts':100,'eur_mwh':20}])

if __name__=='__main__': unittest.main()
