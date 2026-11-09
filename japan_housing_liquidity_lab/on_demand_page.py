"""Shared-property on-demand search UI; local private use only."""
from datetime import datetime,timezone,timedelta
import json
import pandas as pd
import streamlit as st
from .web_adapter import home_query
from . import on_demand as demand

def render():
    st.header('現在の類似掲載を調べる（SUUMO）')
    st.info('同じ住宅入力を歴史分析と共有します。地域内の限定した一覧・詳細を確認し、市場全在庫の検索とは異なります。ローカル・私的利用のみ。')
    q=st.session_state.get('housing_subject',{})
    with st.form('demand_subject'):
        a,b=st.columns(2)
        with a:
            city=st.text_input('検索対象の市区町村',value=q.get('市区町村名',''))
            station=st.text_input('検索対象の駅',value=q.get('最寄駅：名称',''))
            area=st.number_input('検索対象の面積㎡',min_value=0.,value=float(q['面積（㎡）']) if q.get('面積（㎡）') else None)
            year=st.number_input('検索対象の建築年',min_value=1800,max_value=2100,value=int(q['建築年'].removesuffix('年')) if q.get('建築年') else None)
        with b:
            layout=st.text_input('検索対象の間取り',value=q.get('間取り',''))
            structure=st.text_input('検索対象の構造',value=q.get('建物の構造',''))
            price=st.number_input('比較中の掲載総額万円（検索上限にはしない）',min_value=0.,value=float(q['asking_price_jpy'])/10000 if q.get('asking_price_jpy') else None)
            walk=st.number_input('検索対象の徒歩分（任意）',min_value=0.,value=float(q['最寄駅：距離（分）']) if q.get('最寄駅：距離（分）') else None)
        strict=st.checkbox('厳格一致を同じ駅に限定',value=True)
        use_walk=st.checkbox('徒歩分±5分で絞る',value=False)
        max_pages=st.number_input('一覧ページ上限（1〜20）',min_value=1,max_value=20,value=10)
        max_details=st.number_input('詳細取得上限（1〜30）',min_value=1,max_value=30,value=12)
        st.caption('厳格：面積±20%、建築年±10年、指定した間取り・構造。近似：同じ行政区、面積±35%、建築年±20年、同じ部屋数系統、他駅・他構造も含む。価格上限なし。徒歩を指定した近似では許容幅をさらに5分広げ、不明を明示します。')
        consent=st.checkbox('ローカル私的利用と限定HTTP取得を確認',value=False)
        go=st.form_submit_button('限定した実掲載検索を開始')
    if go:
        st.session_state.pop('demand_task',None)
        try:
            if not consent:raise ValueError('Confirmation required')
            subject=home_query(city,q.get('地区名','') if city==q.get('市区町村名') else '',station,walk,area,year,None,layout,structure,price,datetime.now(timezone(timedelta(hours=9))).date())
            if use_walk:
                if walk is None:raise ValueError('Walking time required')
                subject['walk_tolerance_minutes']=5
            st.session_state['housing_subject']=subject
            from .pg_admin import local_environment
            local_environment()
            task=demand.create(subject,strict_station=strict,max_pages=int(max_pages),max_details=int(max_details))
            st.session_state['demand_task']=task;demand.start(task)
        except Exception:st.error('入力・利用確認またはDB接続を確認してください。管理者が有効な接続を設定する必要があります。')
    task=st.session_state.get('demand_task')
    if not task:return
    render_task(task)


def render_task(task, key_prefix=''):
    """Display an existing task without requiring another property form."""
    def widget_key(name):return key_prefix+name if key_prefix else None
    try:
        progress=demand.progress(task)
        labels={'queued':'待機中','running':'取得中','waiting_central_worker':'中央収集が使用中。HTTP取得は開始していません','interrupted':'中断・再開可能','partial':'限定予算終了・部分結果','failed':'取得失敗・結果不完全','completed':'限定範囲の確認完了','paused':'利用者が一時停止・再開可能','pause_requested':'停止要求済み・実行中の応答完了を待っています'}
        st.write('状態：',labels.get(progress['status'],progress['status']))
        if progress.get('query'):
            subject=progress['query'];st.caption(f"この結果の条件：{subject['市区町村名']}・{subject.get('最寄駅：名称','')} ／ {subject['面積（㎡）']}㎡ ／ {subject['建築年']} ／ {subject.get('間取り','')}")
        st.json(progress['progress'],expanded=False)
        if progress['status'] in ['queued','running','waiting_central_worker','pause_requested']:
            st.info('状態と結果を更新すると、確認済み部分結果が表示されます。画面を閉じても実行中タスクは止まりません。一時停止は通信間の安全な位置で反映され、実行中の応答は最大タイムアウトまで待ちます。')
            if progress['status']!='pause_requested' and st.button('検索を一時停止／待機を解除',key=widget_key('pause')):demand.pause(task);st.rerun()
        if st.button('状態と結果を更新',key=widget_key('refresh')):st.rerun()
        if progress['status'] in ['waiting_central_worker','interrupted','paused','pause_requested','failed'] and st.button('同じタスクを再開',key=widget_key('retry')):demand.retry(task);st.rerun()
        if progress.get('error'):st.warning('取得できませんでした：'+progress['error'])
        result=progress.get('result')
        if result:
            if result.get('live_partial'):st.info('実行中の部分結果です。まだ確認していない候補があります。')
            if result.get('run',{}).get('error'):st.warning('検索を停止した理由：'+result['run']['error']+'。以下は停止前に確認できた部分結果です。未確認を在庫なしとは扱いません。')
            a,b=st.columns(2)
            a.metric('今回の厳格一致（掲載ID）',result['matched_n'])
            b.metric('今回の近似候補（掲載ID・厳格と重複なし）',result.get('approximate_n',0))
            st.caption(f"一覧 {result.get('pages_scanned','?')} ページ ／ 発見 {result['discovered_ids']} ID ／ 属性の予備候補 {result.get('candidate_n','?')} ／ 詳細取得 {result.get('detail_attempts','?')}（成功 {result.get('successful_details','?')}） ／ HTTP {result.get('http_requests','?')}回")
            st.caption(f"取得開始 {result.get('started_at','不明')} ／ 終了 {result['checked_at']}（UTC） ／ 経過 {result.get('elapsed_seconds',0):.1f} 秒")
            st.warning('0件でも在庫0を意味しません。許可された行政区一覧をページ上限まで調べた部分検索です。サイトの表示順・未確認ページ・未取得詳細による偏りがあります。複数仲介会社の同じ住宅は別の掲載IDとなる場合があります。')
            st.info('公式絞り込みフォームの送信先は robots.txt により取得不可です。回避せず、公開一覧の面積・築年月・間取りを読み、関連する詳細を優先取得します。')
            totals=result.get('advertised_totals',[])
            st.write('サイト表示件数（取得件数ではありません）：',totals or '未確認','／ 一覧末尾まで確認：','はい' if result.get('list_traversal_complete') else 'いいえ')
            st.write('残る一覧ページ入口：',result.get('pending_pages','?'),'／ 残る候補詳細：',result.get('pending_details','?'))
            counts=result.get('observation_counts',{})
            st.caption(f"今回初発見・詳細確認 {counts.get('newly_discovered',0)} ／ 再確認 {counts.get('reconfirmed',0)} ／ 既発見IDの初詳細 {counts.get('previously_discovered_first_detail',0)} ／ 旧DB観測 {counts.get('old_database',0)} ／ 詳細失敗 {counts.get('access_or_parse_failed',0)}")
            if result['matched_n']==0:st.info('厳格一致は今回確認できませんでした。下の近似候補の「条件との差」を確認してください。未確認の範囲に一致住宅がないとは判断できません。')
            show_records('厳格一致',result['records'])
            show_records('条件を広げた近似候補',result.get('approximate_records',[]))
            with st.expander('旧データベースの観測（今回の一致数には含めません）'):
                st.warning('今回詳細を再確認していません。価格・掲載継続は未確認です。今回アクセス失敗した場合も過去の観測を表示します。')
                show_records('旧観測',result.get('old_database_records',[]))
            with st.expander('検索範囲・失敗・取得証拠'):
                st.json({k:result.get(k) for k in ['page_evidence','failed_details','http_statuses','server_filters','criteria']})
            st.download_button('実掲載検索結果JSON',json.dumps(result,ensure_ascii=False,allow_nan=False),file_name='current-listings.json',mime='application/json',key=widget_key('download'))
    except Exception:st.error('タスク状態を取得できません。接続を確認して再試行してください。')


OBSERVATIONS={'newly_discovered':'今回新発見','reconfirmed':'今回再確認','previously_discovered_first_detail':'既発見・今回初詳細','old_database':'旧DB観測'}

def show_records(title,records):
    st.subheader(title)
    if not records:
        st.caption('該当する確認済み記録なし')
        return
    display=[]
    for r in records:
        display.append({'掲載ID':r.get('listing_id'),'価格万円':round(r['price_jpy']/10000,1),'単価万円/㎡':round(r['unit_price_jpy_m2']/10000,2),'面積㎡':r['area_m2'],'築年':r.get('built_year'),'築年数':r.get('age'),'駅':r.get('station'),'徒歩分':r.get('walk_minutes'),'間取り':r.get('layout'),'観測':OBSERVATIONS.get(r.get('observation_kind'),'不明'),'条件との差':'、'.join(r.get('relaxed_conditions',[])),'SUUMO':r.get('url'),'取得日時':r.get('observed_at')})
    st.dataframe(pd.DataFrame(display),hide_index=True,column_config={'SUUMO':st.column_config.LinkColumn('原ページ')})
    for r in records:
        with st.expander(f"掲載 {r.get('listing_id')} · {r['price_jpy']/10000:,.0f}万円 · {r['area_m2']}㎡ · {r.get('station','駅不明')}"):
            st.write(f"{r.get('municipality','')} {r.get('town','')} ／ {r.get('built_year','不明')}年築 ／ {r.get('layout','')} ／ {r.get('structure','構造不明')}")
            st.write('徒歩分：',r.get('walk_minutes','不明'),'（鉄道等を含む通勤時間ではありません）')
            st.write('条件との差：','、'.join(r.get('relaxed_conditions',[])) or '指定した厳格条件内')
            st.caption(f"{OBSERVATIONS.get(r.get('observation_kind'),'観測種別不明')} ／ {r.get('observed_at')} ／ {r.get('freshness_seconds',0)/3600:.1f}時間前")
            if r.get('current_check_failed'):st.warning('今回の詳細取得は失敗。表示は過去の観測です。')
            if r.get('url'):st.link_button('SUUMOの原ページを開く',r['url'])
