"""Buyer-facing listing results: no network or database access in these UI checks."""
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from japan_housing_liquidity_lab import on_demand_page as ui

SOURCE="from japan_housing_liquidity_lab.on_demand_page import render_task\nrender_task('a'*32,key_prefix='review_')"


def row(listing_id='synthetic-1', **kw):
    return dict(listing_id=listing_id,price_jpy=30000000,unit_price_jpy_m2=1200000,
        area_m2=25,built_year=2005,age=21,municipality='試験区',town='試験町',station='試験駅',
        walk_minutes=10,layout='1K',structure='RC',observed_at='2026-11-10T00:00:00+00:00',
        freshness_seconds=3600,observation_kind='newly_discovered',relaxed_conditions=[],
        url='https://suumo.jp/ms/chuko/tokyo/sc_setagaya/nc_00000001/')|kw


def result(**kw):
    return dict(matched_n=1,approximate_n=0,records=[row()],approximate_records=[],
        old_database_records=[],discovered_ids=5,checked_at='2026-11-10T00:01:00+00:00',
        started_at='2026-11-10T00:00:00+00:00',elapsed_seconds=60,pages_scanned=1,
        candidate_n=3,detail_attempts=1,successful_details=1,pending_pages=2,pending_details=2,
        observation_counts={'newly_discovered':1},list_traversal_complete=False,
        page_evidence=[],failed_details=[],http_statuses=[],server_filters={},criteria={})|kw


def progress(status='partial',**kw):
    return dict(task_id='a'*32,status=status,query={},progress={'jobs_pending':2},result=result(),error=None)|kw


class ListingResultPresentationTests(unittest.TestCase):
    def run_page(self, value):
        with patch.object(ui.demand,'progress',return_value=value):
            app=AppTest.from_string(SOURCE,default_timeout=20).run()
        self.assertFalse(app.exception)
        return app
    def test_live_results_have_no_false_finish_time_and_advanced_progress(self):
        app=self.run_page(progress('running',result=result(live_partial=True)))
        self.assertTrue(any('実行中の部分結果' in x.value for x in app.info))
        self.assertTrue(any('結果確認時点' in x.value for x in app.caption))
        self.assertFalse(any(' ／ 終了 ' in x.value for x in app.caption))
        advanced=next(x for x in app.expander if x.label.startswith('高度な詳細'))
        self.assertIn('jobs_pending',advanced.json[0].value)
        self.assertTrue(any(x.label=='検索を一時停止／待機を解除' for x in app.button))
    def test_failure_keeps_partial_and_old_observations_separate(self):
        stale=row('synthetic-old',observation_kind='old_database',current_check_failed=True)
        app=self.run_page(progress('failed',error='HTTP_301',result=result(run={'error':'HTTP_301'},old_database_records=[stale])))
        self.assertEqual([x.value for x in app.metric],['1','0'])
        self.assertTrue(any('掲載ページの移動' in x.value for x in app.warning))
        self.assertFalse(any('HTTP_301' in x.value for x in app.warning))
        advanced=next(x for x in app.expander if x.label.startswith('高度な詳細'))
        self.assertIn('HTTP_301',advanced.json[0].value)
        old=next(x for x in app.expander if x.label.startswith('旧データベース'))
        self.assertEqual(old.dataframe[0].value.iloc[0]['観測'],'旧DB観測')
        self.assertTrue(any('今回の詳細取得は失敗' in x.value for x in old.warning))
    def test_zero_strict_is_not_zero_inventory_or_mixed_with_approximate(self):
        app=self.run_page(progress(result=result(matched_n=0,records=[],approximate_n=1,
            approximate_records=[row('synthetic-near',relaxed_conditions=['面積差'])])))
        self.assertEqual([x.value for x in app.metric],['0','1'])
        self.assertTrue(any('0件でも在庫0を意味しません' in x.value for x in app.warning))
        self.assertTrue(any('厳格一致は今回確認できませんでした' in x.value for x in app.info))
        self.assertEqual(len(app.dataframe[0].value),1)
    def test_zero_current_matches_surface_relevant_old_observations(self):
        app=self.run_page(progress(result=result(matched_n=0,records=[],approximate_n=0,
            old_database_match_n=2,old_database_records=[row('old-a'),row('old-b')],
            observation_counts={'old_database':39})))
        self.assertEqual([x.value for x in app.metric],['0','0'])
        self.assertTrue(any('条件に合う過去の観測：2掲載ID' in x.value and '今回の詳細確認・一致数には含めません' in x.value for x in app.caption))
        self.assertTrue(any('発見した全ID中の過去観測あり 39' in x.value for x in app.caption))
        self.assertTrue(any('旧データベースの観測' in x.value and '今回の新しい確認結果ではありません' in x.value for x in app.info))
        self.assertFalse(any('下の近似候補' in x.value for x in app.info))
        old=next(x for x in app.expander if x.label.startswith('旧データベース'))
        self.assertEqual(len(old.dataframe[0].value),2)
    def test_units_attributes_links_and_expanded_record(self):
        app=self.run_page(progress())
        record=app.dataframe[0].value.iloc[0]
        self.assertEqual(record['価格万円'],3000);self.assertEqual(record['単価万円/㎡'],120)
        self.assertEqual(record['面積㎡'],25);self.assertEqual(record['築年数'],21)
        self.assertEqual(record['駅'],'試験駅');self.assertEqual(record['間取り'],'1K')
        self.assertEqual(record['取得日時'],'2026-11-10T00:00:00+00:00')
        expanded=next(x for x in app.expander if x.label.startswith('掲載 synthetic-1'))
        self.assertTrue(any('120.00万円/㎡' in x.value and '21年' in x.value for x in expanded.markdown))
        self.assertEqual(expanded.get('link_button')[0].proto.url,record['SUUMO'])
    def test_database_failure_is_not_a_zero_match_result_or_private_error(self):
        with patch.object(ui.demand,'progress',side_effect=RuntimeError('PRIVATE_CONNECTION_DETAIL')):
            app=AppTest.from_string(SOURCE).run()
        self.assertFalse(app.exception);self.assertFalse(app.metric)
        self.assertTrue(any('掲載が0件になったという意味ではありません' in x.value for x in app.error))
        self.assertFalse(any('PRIVATE_CONNECTION_DETAIL' in x.value for x in app.error))
    def test_pause_request_preserves_task_and_uses_only_cooperative_pause(self):
        with patch.object(ui.demand,'progress',return_value=progress('running')),patch.object(ui.demand,'pause') as pause:
            app=AppTest.from_string(SOURCE).run()
            next(x for x in app.button if x.label=='検索を一時停止／待機を解除').click().run()
            pause.assert_called_once_with('a'*32)
            self.assertFalse(app.exception)


if __name__=='__main__':unittest.main()
