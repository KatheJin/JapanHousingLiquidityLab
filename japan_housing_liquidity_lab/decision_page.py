"""One subject, three independent comparison panels. Never starts HTTP on analysis."""
from datetime import date,datetime,timezone,timedelta
from pathlib import Path
import json
import os

import pandas as pd
import streamlit as st
from . import historical_query as history
from . import on_demand as demand
from . import on_demand_page
from .web_adapter import home_query


@st.cache_data(show_spinner=False)
def history_resources(root):
    return history.load(Path(root))


@st.cache_resource(show_spinner=False)
def area_resources(root):
    from . import area_comparison
    return area_comparison.load(Path(root))


def compare_areas(resources,query):
    from . import area_comparison
    return area_comparison.compare(resources,query)


def start_search(query,destination,*,pages,details,consent):
    """Explicit click boundary; never mutate the original comparison subject."""
    if not consent:raise ValueError('Local private collection confirmation required')
    from .pg_admin import local_environment
    local_environment()
    task=demand.create(dict(query),destination=destination,max_pages=int(pages),max_details=int(details),strict_station=True)
    demand.start(task)
    return task


def render_history(result):
    st.metric('歴史的な比較取引記録数',result['comparable_n'])
    distribution=result.get('raw_distribution',{})
    records=result.get('records',[])
    periods=[r['quarter'] for r in records if r.get('quarter')]
    if periods:st.caption(f"一致記録の実際の期間：{min(periods)}～{max(periods)}。取得済みの2026Q2にも未収録取引・後日改訂の可能性があります。")
    if distribution.get('median') is not None:
        st.write(f"原単価の中央値 {distribution['median']/10000:,.1f}万円/㎡ ／ 中央50%の範囲 {distribution['p25']/10000:,.1f}～{distribution['p75']/10000:,.1f}万円/㎡（属性・時期未調整、判断材料となる精度を保証する値ではありません）")
    counts=result['cohort_counts']
    st.caption(f"2018～2022拡張 {counts['expanded_2018_2022']}件 ／ 2023～2026既存期間 {counts['existing_2023_2026']}件")
    st.warning('歴史価格の正式な属性・時間・老化調整は利用不可です。原取引の件数・価格を表示します。この制約は現在掲載の検索を妨げません。')
    st.caption('過去の安い取引の割合は、将来より安く購入できる確率ではありません。匿名取引記録であり市場全件数・現在の在庫ではありません。')
    if result['comparable_n']<10:st.warning('比較記録が10件未満です。価格競争力は判断できません。')
    with st.expander('歴史的な成約明細を開く'):
        records=pd.DataFrame(result['records'])
        if records.empty:st.info('一致する記録はありません。自動的に条件を緩めていません。')
        else:
            records['単価万円/㎡']=records.raw_unit_price_jpy_m2/10000
            columns=['quarter','total_price_raw','単価万円/㎡','area_m2','age_at_trade','station','walk_raw','construction_year','layout','structure','municipality','town']
            columns=[c for c in columns if c in records]+[c for c in records if c not in columns]
            st.dataframe(records[columns].rename(columns={'quarter':'成約四半期','total_price_raw':'成約総額円','area_m2':'面積㎡','age_at_trade':'取引時築年数','station':'駅','walk_raw':'徒歩原表記','construction_year':'建築年','layout':'間取り','structure':'構造','municipality':'市区町村','town':'町名'}),hide_index=True)
    with st.expander('取得範囲・四半期・欠損と出典'):
        st.dataframe(pd.DataFrame(result['quarterly']),hide_index=True)
        st.json({k:result[k] for k in ['source','missing_fields','walk_filter','adjustment','warnings']})
    st.download_button('歴史比較JSONを保存',json.dumps(result,ensure_ascii=False,allow_nan=False),file_name='decision-history.json',mime='application/json',key='decision_history_download')


REASON_LABELS={
    'Cross-market hedonic contrasts have no independent validation; formal price and rank unavailable':'地区間の価格差は独立検証が不足し、正式価格・推奨順位は利用不可',
    'Recent joint-profile support below10':'直近の近い住宅属性の記録が10件未満',
    '2025 station-level development error sample below30':'2025年の駅別誤差評価記録が30件未満',
    'Candidate order changes materially across model definitions':'モデル定義によって候補の順番が大きく変化',
    'High-price tail shows systematic underprediction in prior Phase2 experiments':'高価格帯では従来実験に系統的な過小予測あり',
    'Target joint-profile or market sample support insufficient; no model-only recommendation':'対象市場または近い属性の記録が不足。予測値だけでは候補にしません',
    'Known nonnegative exact walking minutes required':'地域比較には既知の正確な徒歩分が必要',
    'Area outside central98% model support':'面積がモデルの中心98%の適用範囲外',
    'Target market absent from model training period':'対象の行政区・駅がモデル適用期間のデータに存在しません'}


def reason_label(text):
    if str(text).startswith('Required property feature missing: '):return '地域比較に必要な住宅属性が不足'
    if str(text).startswith('Unseen or pooled '):return '指定した住宅属性を既存モデルが独立したカテゴリとして扱えません'
    return REASON_LABELS.get(text,'研究上の留保あり（詳細は研究JSON）')


def diagnostic_range(candidate):
    values=[x['relative_gap_pct'] for x in candidate.get('diagnostic_by_method',{}).values() if x.get('relative_gap_pct') is not None]
    return f'{min(values):+.1f}～{max(values):+.1f}%' if values else '未評価'


EVIDENCE_GROUPS={
    'multi_model_agreement':'複数モデルが近い価格水準を示す',
    'model_disagreement':'モデルによって判断が分かれる',
    'insufficient_sample':'直近の比較記録が不足'}


def raw_profile_text(profile):
    """Present service-provided raw quartiles without generating new estimates."""
    profile=profile or {}
    prices=profile.get('raw_unit_price_jpy_m2') or {}
    median=prices.get('median');q1=prices.get('q1');q3=prices.get('q3')
    return ('表示不可' if median is None else f'{median/10000:,.1f}',
            '表示不可' if q1 is None or q3 is None else f'{q1/10000:,.1f}～{q3/10000:,.1f}')


def render_regions(result):
    st.warning('地区間の価格差は未検証です。以下は研究用の比較候補で、購入推奨・信頼できる順位・現在の査定価格ではありません。正式な調整価格は利用不可です。')
    common=result.get('common_attributes',{})
    st.caption(f"統一比較期：{result.get('reference_quarter','不明')}。現在の即時価格ではありません。全候補で同じ住宅属性を用います。")
    st.write(f"共通条件：{common.get('area_m2','不明')}㎡ ／ {str(common.get('construction_year') or '不明').removesuffix('年')}年築（比較期の築年数 {common.get('age_at_reference','不明')}） ／ {common.get('layout','不明')} ／ {common.get('structure','不明')} ／ 徒歩 {common.get('walk_minutes','不明')}分")
    target=result.get('target') or {}
    st.write('対象市場：',target.get('municipality',''),target.get('station',''),'／ 近い属性の記録：',target.get('support_n',0),'／ 直近記録：',target.get('recent_support_n',0))
    target_unit=target.get('diagnostic_reference_unit_price_jpy_m2')
    if target_unit is not None:st.metric('対象の研究用参考単価（万円/㎡・正式価格ではありません）',f'{target_unit/10000:,.1f}')
    profile=target.get('historical_joint_profile') or {}
    if profile:
        raw_median,raw_iqr=raw_profile_text(profile)
        st.caption(f"地区比較用の条件帯の実取引：{profile.get('period_start') or '不明'}～{profile.get('period_end') or '不明'}、有効価格 {profile.get('valid_price_n',0)}件。原単価中央値 {raw_median}、中央50% {raw_iqr} 万円/㎡。時期・属性未調整で、上のモデル参考値とは別の統計です。歴史明細とは比較期・築年数・徒歩の条件帯が異なります（詳細JSONに条件を保存）。")
        if profile.get('valid_price_n',0)<10:st.info('対象の近い属性の有効価格が10件未満のため、原単価の分布も表示を控えています。')
    primary_reasons=[r for r in target.get('reasons',[]) if not str(r).startswith('Cross-market')]
    if primary_reasons:st.caption('対象の留保：'+' / '.join(dict.fromkeys(reason_label(r) for r in primary_reasons)))
    if result.get('status')=='unavailable':st.info('相近い価格水準を判断できません。支持不足・適用範囲・入力条件を確認してください。')
    candidates=result.get('candidates',[])
    if candidates:
        st.caption('近い属性の記録は2023Q1～2026Q2、直近は2025Q3～2026Q2です。実際の取得範囲は詳細を参照してください。2026Q2は不完全・改訂の可能性があります。原単価は取引時点の未調整分布です。')
        st.caption('複数モデル一致：各モデルの価格差が±10%以内、モデル間の差の幅が5ポイント以内、直近の近い属性が10件以上。これは統計的な信頼区間や地区価格差の検証を意味しません。条件を緩めて件数を増やしません。')
        for code,label in EVIDENCE_GROUPS.items():
            group=[c for c in candidates if c.get('evidence_group','insufficient_sample')==code]
            st.markdown(f'**{label}：{len(group)}地域**')
            if not group:
                st.caption('この区分の候補はありません。')
                continue
            if code=='insufficient_sample':st.info('直近の近い属性の記録が10件未満です。複数モデルの値が近くても、価格水準が近いと判断できません。')
            elif code=='model_disagreement':st.info('モデルの選び方で地区の差が変わります。精密な順位や有利な地区として扱えません。')
            rows=[]
            for c in group:
                raw_median,raw_iqr=raw_profile_text(c.get('historical_joint_profile'))
                unit=c.get('diagnostic_reference_unit_price_jpy_m2');spread=c.get('diagnostic_gap_spread_percentage_points')
                rows.append({'地域・駅':c['municipality']+' / '+c['station'],'研究用標準化単価（万円/㎡）':None if unit is None else round(unit/10000,1),'モデルによる対象との差':diagnostic_range(c),'モデル間の差の幅（ポイント）':None if spread is None else round(spread,1),'近い属性の記録':c.get('support_n',0),'直近の記録':c.get('recent_support_n',0),'原単価中央値（万円/㎡）':raw_median,'原単価中央50%（万円/㎡）':raw_iqr})
            st.dataframe(pd.DataFrame(rows),hide_index=True)
    else:st.info('表示できる候補地区がありません。予測値だけで候補を作成しません。')
    with st.expander('研究用の標準化価格・差・誤差・順位感度（購入推奨ではありません）'):
        st.caption('正式な参考価格・差は利用不可のままです。下表は同じ属性を各市場に置いたモデルの診断値です。経験誤差やモデル間差は校正済み予測区間ではありません。')
        diagnostic=[]
        for c in [target]+candidates:
            unit=c.get('diagnostic_reference_unit_price_jpy_m2');gap=c.get('diagnostic_relative_gap_pct')
            diagnostic.append({'市場':c.get('municipality','')+' / '+c.get('station',''),'研究用単価万円/㎡':None if unit is None else round(unit/10000,1),'研究用差%':None if gap is None else round(gap,1),'支持記録':c.get('support_n',0),'直近支持記録':c.get('recent_support_n',0),'留保':' / '.join(dict.fromkeys(reason_label(x) for x in c.get('reasons',[]))),'順位感度':json.dumps(c.get('rank_stability',{}),ensure_ascii=False),'不確実性':json.dumps(c.get('uncertainty',{}),ensure_ascii=False)})
        st.dataframe(pd.DataFrame(diagnostic),hide_index=True)
        st.caption('全入力・モデル別値・取得期間・生の価格分布・出典・元の研究留保を省略せず保存しています。')
        st.json(result,expanded=False)
    st.download_button('地区比較研究JSONを保存',json.dumps(result,ensure_ascii=False,allow_nan=False),file_name='decision-regions.json',mime='application/json',key='decision_regions_download')
    return candidates


def launch_search(query,destination,slot,*,pages,details,consent):
    if not consent:
        st.info('検索前に「限定したSUUMO取得とローカル私的利用を確認」をチェックしてください。まだ取得していません。')
        return
    try:
        task=start_search(query,destination,pages=pages,details=details,consent=consent)
        tasks=dict(st.session_state.get('decision_tasks',{}))
        tasks[slot]={'task_id':task,'destination':destination or {'municipality':query['市区町村名'],'station':query['最寄駅：名称']}}
        st.session_state['decision_tasks']=tasks
    except Exception:
        st.error('掲載検索に接続できません。データベース接続と収集設定を確認してください。歴史・地域比較の結果は保持されます。自動で再試行したり、在庫0件と判断したりしません。')


def render_search_task(slot):
    task=st.session_state.get('decision_tasks',{}).get(slot)
    if task:
        destination=task['destination']
        st.write('掲載検索：'+destination['municipality']+' / '+destination['station'])
        on_demand_page.render_task(task['task_id'],key_prefix='decision_'+slot+'_')


def render():
    st.header('住宅比較：歴史・現在掲載・他地域')
    st.info('住宅条件は一度だけ入力します。歴史比較・地区研究ではネット収集せず、「掲載を調べる」を押した地域だけ限定検索します。')
    root=str(Path(os.environ.get('JHLL_DATA_ROOT',Path(__file__).resolve().parents[1])))
    try:df,metadata=history_resources(root)
    except Exception:df=metadata=None
    current=st.session_state.get('housing_subject',{})
    today=datetime.now(timezone(timedelta(hours=9))).date()
    if st.session_state.get('decision_tasks'):st.info('入力の再比較や別候補への切替は、実行中の検索を自動停止しません。必要なら先に下の検索パネルで一時停止してください。観測履歴はデータベースに保持されます。')
    with st.form('decision_subject_form'):
        a,b=st.columns(2)
        with a:
            city=st.text_input('比較する市区町村',value=current.get('市区町村名',''))
            town=st.text_input('比較する町名（任意）',value=current.get('地区名',''))
            station=st.text_input('比較する最寄駅',value=current.get('最寄駅：名称',''))
            area=st.number_input('比較する面積㎡',min_value=0.,value=float(current['面積（㎡）']) if current.get('面積（㎡）') else None)
            built=st.number_input('固定する建築年',min_value=1800,max_value=today.year,value=int(current['建築年'].removesuffix('年')) if current.get('建築年') else None)
        with b:
            walk=st.number_input('駅までの徒歩分（任意）',min_value=0.,value=float(current['最寄駅：距離（分）']) if current.get('最寄駅：距離（分）') else None)
            layout=st.text_input('比較する間取り（不明は空欄）',value=current.get('間取り',''))
            structure=st.text_input('比較する構造（不明は空欄）',value=current.get('建物の構造',''))
            price=st.number_input('比較する掲載価格万円',min_value=0.,value=float(current['asking_price_jpy'])/10000 if current.get('asking_price_jpy') else None)
            reference=st.date_input('住宅入力の参考日',value=date.fromisoformat(current.get('reference_date',today.isoformat())))
        coverage=metadata['coverage'] if metadata else []
        start=st.selectbox('歴史比較開始',coverage,index=0) if coverage else '2018Q1'
        end=st.selectbox('歴史比較終了',coverage,index=len(coverage)-1) if coverage else '2026Q2'
        walk_filter=st.checkbox('歴史・掲載の厳格比較に徒歩±5分を使う',value=False)
        submitted=st.form_submit_button('この住宅で歴史と地域を比較')
    if submitted:
        for key in ['decision_subject','decision_history','decision_regions','decision_history_error','decision_region_error','decision_tasks']:
            st.session_state.pop(key,None)
        try:
            q=home_query(city,town,station,walk,area,built,None,layout,structure,price,reference)
            if walk_filter:
                if walk is None:raise ValueError('Walking time required')
                q['walk_tolerance_minutes']=5
            st.session_state['housing_subject']=dict(q);st.session_state['decision_subject']=dict(q)
            if df is None:st.session_state['decision_history_error']=True
            else:
                try:st.session_state['decision_history']=history.search(df,q|{'history_start':start,'history_end':end},metadata)
                except Exception:st.session_state['decision_history_error']=True
            try:
                with st.spinner('取得済み履歴と既存モデルから地区を比較しています…'):
                    st.session_state['decision_regions']=compare_areas(area_resources(root),q)
            except Exception:st.session_state['decision_region_error']=True
        except (ValueError,TypeError,KeyError):st.error('市区町村・駅・面積・建築年・掲載価格・日付を確認してください。徒歩を制限する場合は徒歩分も必要です。')
    q=st.session_state.get('decision_subject')
    if not q:return
    st.caption(f"今回の共通入力：{q['市区町村名']} / {q['最寄駅：名称']} / {q['面積（㎡）']}㎡ / {q['建築年']} / {q['間取り']} / {q['建物の構造']} / 参考日 {q['reference_date']}。入力欄の変更は再度「比較」を押すまで結果に反映されません。")
    st.subheader('1. 歴史的な類似成約')
    if st.session_state.get('decision_history_error'):st.error('歴史データを読み込めないか、参考日・比較期間が適用範囲外です。現在掲載の検索は利用できます。架空データには切り替えません。')
    if st.session_state.get('decision_history'):render_history(st.session_state['decision_history'])
    st.subheader('2. 同じ地域の現在掲載')
    st.caption('住宅条件を再入力せずに検索できます。掲載価格が入力価格を超えても除外しません。検索した地域・ページ数・詳細取得上限の範囲内の結果で、市場の全在庫ではありません。')
    consent=st.checkbox('限定したSUUMO取得とローカル私的利用を確認',value=False,key='decision_consent')
    with st.expander('検索の範囲を調整（同じ地域・候補地域で共通）'):
        pages=st.number_input('今回の一覧ページ上限',min_value=1,max_value=20,value=10,key='decision_pages')
        details=st.number_input('今回の詳細取得上限',min_value=1,max_value=30,value=12,key='decision_details')
        st.caption('取得は中央の共有限速・ロックに従います。掲載IDは実住宅の重複を含む可能性があります。実行中の検索は画面を閉じても止まらず、下の状態表示から一時停止できます。')
    if st.button('対象と同じ地域の掲載を調べる',key='decision_search_target'):
        launch_search(q,None,'target',pages=pages,details=details,consent=consent)
    render_search_task('target')
    st.subheader('3. 価格水準の近い地域')
    candidates=[]
    if st.session_state.get('decision_region_error'):st.error('地区比較のデータ・既存モデルを利用できません。歴史比較や現在掲載の検索は引き続き使えます。')
    if st.session_state.get('decision_regions'):candidates=render_regions(st.session_state['decision_regions'])
    if candidates:
        chosen=st.selectbox('掲載を調べたい候補地域',range(len(candidates)),format_func=lambda i:candidates[i]['municipality']+' / '+candidates[i]['station']+'（'+EVIDENCE_GROUPS.get(candidates[i].get('evidence_group'),'研究上の判断不可')+'）',key='decision_destination')
        c=candidates[chosen]
        st.caption('駅名は行政区と原表記の組合せです。MLITとSUUMOの駅表記対応は未検証で、同駅が見つからない場合があります。入力住宅の面積・建築年・間取り等を保ち、町名は引き継がず選択した地域だけ検索します。候補選択だけでは取得しません。')
        if st.button('選択した候補地域の掲載を調べる',key='decision_search_candidate'):
            launch_search(q,{'municipality':c['municipality'],'station':c['station']},'candidate',pages=pages,details=details,consent=consent)
    render_search_task('candidate')
