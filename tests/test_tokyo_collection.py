"""Synthetic parser/scheduler fixtures; no portal requests or production writes."""
import unittest
from unittest.mock import patch
from japan_housing_liquidity_lab import tokyo_collection as t

class TokyoCollectionTests(unittest.TestCase):
    def test_official_links_required_for_all_wards(self):
        html=''.join('<a href="/ms/chuko/tokyo/sc_region'+chr(97+i)+'/">'+n+'</a>' for i,n in enumerate(t.WARDS))
        result=t.parse_plan(html)
        self.assertEqual(len(result),24);self.assertEqual(result[0],t.KOMAE)
        self.assertEqual([r['municipality'] for r in result[1:]],list(t.WARDS))
        with self.assertRaises(ValueError):t.parse_plan(html.replace('千代田区','架空区'))
        with self.assertRaises(ValueError):t.parse_plan(html+'<a href="/ms/chuko/tokyo/sc_other/">千代田区</a>')
    def test_komae_first_then_lowest_supported_ward(self):
        regions=[dict(t.KOMAE,successful_unique=5,latest_run=dict(status='paused',updated_at='1'))]
        regions.extend(dict(municipality=n,successful_unique=0,latest_run=None) for n in t.WARDS)
        state=dict(regions=regions)
        self.assertEqual(t.choose(state,'initial')['municipality'],'狛江市')
        regions[0]['latest_run']['status']='completed'
        self.assertEqual(t.choose(state,'initial')['municipality'],'千代田区')
        regions[1].update(successful_unique=50,latest_run=dict(status='paused',updated_at='2'))
        self.assertEqual(t.choose(state,'initial')['municipality'],'中央区')
    def test_initial_does_not_restart_finished_runs_incremental_can(self):
        regions=[dict(municipality=n,successful_unique=1,latest_run=dict(status='completed',updated_at=str(i))) for i,n in enumerate(['狛江市',*t.WARDS])]
        self.assertIsNone(t.choose(dict(regions=regions),'initial'))
        self.assertEqual(t.choose(dict(regions=regions),'incremental')['municipality'],'狛江市')

if __name__=='__main__':unittest.main()
