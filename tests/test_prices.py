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

    def test_mixed_sequences_select_sdac_regardless_of_order(self):
        import xml.etree.ElementTree as ET
        first=ET.fromstring(document([(1,50)],'A03'))
        first_series=first[0]
        ns='{urn:test}'
        ET.SubElement(first_series,ns+'classificationSequence_AttributeInstanceComponent.position').text='1'
        second=ET.fromstring(document([(1,90)],'A03'))[0]
        ET.SubElement(second,ns+'classificationSequence_AttributeInstanceComponent.position').text='2'
        for series in ([second,first_series],[first_series,second]):
            root=ET.Element('Publication_MarketDocument')
            root.extend(series)
            rows=prices.parse_prices(ET.tostring(root))
            self.assertEqual([r['eur_mwh'] for r in rows],[50]*4)

    def test_sequence_two_alone_is_not_a_substitute(self):
        xml=document([(1,90)]).replace('<curveType>', '<classificationSequence_AttributeInstanceComponent.position>2</classificationSequence_AttributeInstanceComponent.position><curveType>')
        self.assertEqual(prices.parse_prices(xml),[])

    def test_intraday_contract_is_not_day_ahead(self):
        xml=document([(1,90)]).replace('<curveType>', '<contract_MarketAgreement.type>A07</contract_MarketAgreement.type><curveType>')
        self.assertEqual(prices.parse_prices(xml),[])

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

    def test_legacy_price_levels_are_preserved(self):
        levels=prices.price_levels({**DEFAULTS,'green_limit':-2,'yellow_limit':12,'green_color':'#112233'})
        self.assertEqual(levels,[{'limit':-2.0,'color':'#112233'},{'limit':12.0,'color':'#eab308'}])

    def test_dynamic_price_levels_are_sorted(self):
        data={**DEFAULTS,'price_levels':[{'limit':20,'color':'#FF0000'},{'limit':-5,'color':'#00FF00'},{'limit':10,'color':'#FFFF00'}]}
        self.assertEqual([level['limit'] for level in prices.price_levels(data)],[-5,10,20])
        self.assertEqual(prices.price_levels(data)[0]['color'],'#00ff00')
        prices.validate_settings(data)

    def test_duplicate_or_invalid_price_levels_rejected(self):
        for levels in ([{'limit':5,'color':'#123456'}]*2,[{'limit':float('nan'),'color':'#123456'}],[{'limit':True,'color':'#123456'}],[{'limit':5,'color':'red'}],[{'color':'#123456'}]):
            with self.assertRaises(ValueError):prices.price_levels({**DEFAULTS,'price_levels':levels})

    def test_removing_all_price_levels_is_allowed(self):
        self.assertEqual(prices.price_levels({**DEFAULTS,'price_levels':[]}),[])

    def test_color_picker_roundtrip_and_existing_hex(self):
        self.assertEqual(prices.color_hex([18,52,171]),'#1234ab')
        self.assertEqual(prices.color_rgb('#1234AB'),[18,52,171])
        self.assertEqual(prices.color_hex('#1234AB'),'#1234ab')
        self.assertEqual(prices.price_levels({'price_levels':[{'limit':5,'color':[34,197,94]}]}),[{'limit':5.0,'color':'#22c55e'}])

    def test_invalid_rgb_values_rejected(self):
        for color in ([True,0,0],[256,0,0],[-1,0,0],[1.5,0,0],[0,0],None):
            with self.assertRaises(ValueError):prices.color_hex(color)

    def test_lower_cutoff_and_legacy_appearance(self):
        self.assertEqual(prices.lower_price_rule(DEFAULTS),{'limit':0.0,'color':'#22c55e'})
        self.assertEqual(prices.lower_price_rule({**DEFAULTS,'green_limit':-5})['limit'],-5)
        self.assertEqual(prices.lower_price_rule({**DEFAULTS,'low_limit':0,'low_color':[0,0,255]}),{'limit':0.0,'color':'#0000ff'})
        for cutoff in (6,float('nan'),True):
            with self.assertRaises(ValueError):prices.lower_price_rule({**DEFAULTS,'low_limit':cutoff})

    def test_lower_cutoff_without_targets(self):
        self.assertEqual(prices.lower_price_rule({**DEFAULTS,'price_levels':[],'low_limit':0,'low_color':'#0000ff'}),{'limit':0.0,'color':'#0000ff'})
        self.assertEqual(prices.lower_price_rule({**DEFAULTS,'price_levels':[]})['color'],DEFAULTS['high_color'])

    def test_unexpected_document_rejected(self):
        with self.assertRaises(ValueError): prices.parse_prices('<html/>')


if __name__=='__main__': unittest.main()
