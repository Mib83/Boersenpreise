"""Offline regression tests; no private credentials needed."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from datetime import date

ROOT = Path(__file__).resolve().parents[1] / 'custom_components/boersenpreise'
pkg = types.ModuleType('price_test_package')
pkg.__path__ = [str(ROOT)]
sys.modules['price_test_package'] = pkg
spec = importlib.util.spec_from_file_location('price_test_package.prices', ROOT / 'prices.py')
prices = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prices)
from price_test_package.const import DEFAULTS


def document(points, curve='A01', resolution='PT15M', end='2025-10-01T01:00Z'):
    return f'''<Publication_MarketDocument xmlns="urn:test"><TimeSeries>
    <currency_Unit.name>EUR</currency_Unit.name><price_Measure_Unit.name>MWH</price_Measure_Unit.name>
    <curveType>{curve}</curveType><Period><timeInterval><start>2025-10-01T00:00Z</start><end>{end}</end></timeInterval>
    <resolution>{resolution}</resolution>{''.join(f'<Point><position>{i}</position><price.amount>{v}</price.amount></Point>' for i,v in points)}
    </Period></TimeSeries></Publication_MarketDocument>'''


class PricesTest(unittest.TestCase):
    def test_negative_price_and_conversion(self):
        rows=prices.parse_prices(document([(1,-50),(2,100)]))
        self.assertEqual([r['eur_mwh']/10 for r in rows],[-5,10])
        self.assertEqual(rows[1]['ts']-rows[0]['ts'],900)

    def test_a01_gaps_stay_missing(self):
        self.assertEqual(len(prices.parse_prices(document([(1,50),(3,70)]))),2)

    def test_a03_constant_sections(self):
        rows=prices.parse_prices(document([(1,50),(3,-10)],'A03'))
        self.assertEqual([r['eur_mwh'] for r in rows],[50,50,-10,-10])

    def test_hourly_rejected(self):
        with self.assertRaises(ValueError): prices.parse_prices(document([(1,50)],resolution='PT60M'))

    def test_invalid_nonfinite_rejected(self):
        with self.assertRaises(ValueError): prices.parse_prices(document([(1,'NaN')]))

    def test_no_data_and_other_ack(self):
        xml='<Acknowledgement_MarketDocument><Reason><code>999</code><text>No matching data found</text></Reason></Acknowledgement_MarketDocument>'
        self.assertEqual(prices.parse_prices(xml),[])
        with self.assertRaises(ValueError): prices.parse_prices(xml.replace('No matching data found','Invalid query'))

    def test_dst_and_complete_day(self):
        for day,count in [('2025-10-01',96),('2025-10-26',100),('2026-03-29',92)]:
            start,end=prices.day_bounds(day)
            self.assertEqual((end-start).total_seconds()/900,count)
            rows=[{'ts':ts,'eur_mwh':0} for ts in range(int(start.timestamp()),int(end.timestamp()),900)]
            self.assertTrue(prices.complete_day(day,rows))
            self.assertFalse(prices.complete_day(day,rows[:-1]))

    def test_line_protocol_idempotent(self):
        row={'ts':1759276800,'eur_mwh':100.0}
        self.assertEqual(prices.influx_lines([row]),'boersenpreise,zone=DE-LU eur_mwh=100.0,ct_kwh=10.0 1759276800')

    def test_settings(self):
        self.assertEqual(prices.validate_settings(dict(DEFAULTS)),DEFAULTS)
        for changes in ({'green_limit':10}, {'green_color':'red'}, {'import_start':'2025-09-30'}, {'influx_enabled':True}):
            with self.assertRaises(ValueError): prices.validate_settings({**DEFAULTS,**changes})

    def test_unexpected_document_rejected(self):
        with self.assertRaises(ValueError): prices.parse_prices('<html/>')


if __name__=='__main__': unittest.main()
