"""Phase 3 real-only historical page; business rules stay in historical_query."""
from pathlib import Path
import json
import os
import pandas as pd
import streamlit as st
from . import historical_query as history
from .web_adapter import home_query
from .expansion import qi,qs

def render():
    st.header('歴史的な成約記録を調べる')
    st.info('実取引データ専用。2018～2022拡張データと2023～2026既存モデル期間を分けて表示します。')
    try:
        df,metadata=history.load(Path(os.environ.get('JHLL_DATA_ROOT',Path(__file__).resolve().parents[1])))
    except (ValueError,OSError,KeyError):
        st.error('実データを読み込めません。管理者に確認してください。架空データには切り替えません。');return
    st.caption(f"出典：{metadata['source']} ｜ {metadata['records']:,}記録 ｜ 取得確認 {metadata['available_on']} ｜ 実収録 {metadata['coverage'][0]}～{metadata['coverage'][-1]}。公表日は不明。")
    modes={'同じ市区町村＋駅':'strict_station','同じ市区町村':'municipality','指定した市区町村＋駅を比較':'selected_locations'}
    with st.form('phase3_history'):
        a,b=st.columns(2)
        with a:
            city=st.text_input('対象の市区町村');town=st.text_input('対象の町名（任意）');station=st.text_input('対象の最寄駅')
            area=st.number_input('対象の専有面積（㎡）',min_value=0.,value=None)
            year=st.number_input('対象の建築年',min_value=1800,max_value=2100,value=None)
            walk=st.number_input('対象の駅徒歩分（任意）',min_value=0,value=None)
        with b:
            layout=st.text_input('対象の間取り（任意）');structure=st.text_input('対象の構造（任意）')
            price=st.number_input('対象の掲載価格（万円）',min_value=0.,value=None)
            reference=st.date_input('比較の参考日')
            start=st.selectbox('歴史比較の開始',metadata['coverage'])
            calendar=[qs(i) for i in range(qi(metadata['coverage'][0]),qi(metadata.get('calendar_end',metadata['coverage'][-1]))+1)]
            end=st.selectbox('歴史比較の終了',calendar,index=calendar.index(metadata['coverage'][-1]))
        use_walk=st.checkbox('徒歩分の許容範囲を使う（既定は制限なし）',value=False)
        tolerance=st.number_input('徒歩分の許容差（±分）',min_value=0,value=5)
        scope=st.selectbox('比較範囲',list(modes))
        pairs=st.text_area('比較先（指定比較のみ：1行に 市区町村|駅）')
        go=st.form_submit_button('歴史取引を検索')
    st.caption('面積±20%、取引時築年数と対象の参考日築年数の差±10年。入力した町名・間取り・構造は完全一致。徒歩分の制限は任意です。有効時は区間全体が許容範囲内の記録だけ採用し、距離不明は別表示します。')
    if go:
        st.session_state.pop('phase3_result',None)
        try:
            q=home_query(city,town,station,walk,area,year,None,layout,structure,price,reference)
            q.update(history_start=start,history_end=end)
            if use_walk:q['walk_tolerance_minutes']=tolerance
            locations=[]
            if modes[scope]=='selected_locations':
                for line in pairs.splitlines():
                    parts=line.split('|')
                    if len(parts)!=2:raise ValueError('比較先は市区町村|駅で入力してください。')
                    locations.append(dict(municipality=parts[0].strip(),station=parts[1].strip()))
            st.session_state['phase3_result']=history.search(df,q,metadata,mode=modes[scope],locations=locations or None)
        except (ValueError,TypeError,KeyError):st.error('市区町村・駅・面積・建築年・価格、期間と比較先の書式を確認してください。')
    r=st.session_state.get('phase3_result')
    if not r:return
    if r['source']['data_sha256']!=metadata['data_sha256']:
        st.session_state.pop('phase3_result',None);st.warning('データ版が更新されました。再検索してください。');return
    st.metric('歴史的な比較取引記録数',r['comparable_n'])
    st.write('2018～2022拡張：',r['cohort_counts']['expanded_2018_2022'],'件 ／ 2023～2026既存期間：',r['cohort_counts']['existing_2023_2026'],'件')
    st.warning('調整価格：利用不可。研究診断を正式な調整価格として表示しません。')
    if r['comparable_n']<10:st.warning('10件未満の小標本です。価格競争力の判断はできません。')
    for warning in r['warnings']:st.caption(warning)
    if r['valid_price_n']:
        st.metric('未調整の成約単価中央値（万円/㎡）',f"{r['raw_distribution']['median']/10000:,.2f}")
    st.bar_chart(pd.DataFrame([x for x in r['quarterly'] if x['acquired']]).set_index('quarter')['n'])
    states={'acquired_matches':'取得済・一致あり','acquired_zero':'取得済・一致0件','not_acquired':'公開確認済・未取得','not_published':'未公開（将来期または確認済）','publication_unverified':'公開状況未確認・未取得'}
    calendar=pd.DataFrame(r['quarterly']);calendar['state']=calendar.state.map(states)
    st.dataframe(calendar.rename(columns={'quarter':'四半期','n':'一致件数','state':'取得・公開状態'}),hide_index=True)
    if r['walk_filter']['enabled']:
        st.info(f"徒歩条件前 {r['walk_filter']['base_n']}件、距離不明で除外 {r['walk_filter']['unknown_n']}件、区間の一部だけ重なる記録 {r['walk_filter']['interval_overlap_only_n']}件。")
        with st.expander('徒歩距離不明の記録（検索件数には含めない）'):st.dataframe(pd.DataFrame(r['walk_unknown_records']),hide_index=True)
    table=pd.DataFrame(r['records'])
    with st.expander('実際の比較取引明細（全件）',expanded=False):
        if table.empty:st.info('条件に一致する記録はありません。条件を自動で緩めません。')
        else:
            show=table.copy();show['raw_unit_price_man_m2']=show.raw_unit_price_jpy_m2/10000
            labels={'quarter':'取引四半期','municipality':'市区町村','town':'町名','station':'駅','walk_raw':'駅距離原表記','area_m2':'面積㎡','construction_year':'建築年','age_at_trade':'取引時築年数','layout':'間取り','structure':'構造','total_price_raw':'成約総額円（原表記）','raw_unit_price_jpy_m2':'未調整単価円/㎡','raw_unit_price_man_m2':'未調整単価万円/㎡','source_file':'元ファイル','source_row':'元行','cohort':'データ区分','adjustment_reason':'調整不可理由'}
            priority=['quarter','total_price_raw','raw_unit_price_man_m2','raw_unit_price_jpy_m2','area_m2','age_at_trade','station','walk_raw','walk_status','municipality','town','construction_year','layout','structure','cohort','adjustment_status','adjustment_reason']
            order=priority+[c for c in show if c not in priority]
            st.dataframe(show[order].rename(columns=labels),hide_index=True)
    with st.expander('出典・欠損・検索条件'):
        st.json({k:v for k,v in r.items() if k!='records'},expanded=False)
    st.download_button('検索結果JSONを保存',json.dumps(r,ensure_ascii=False,allow_nan=False),file_name='historical-comparison.json',mime='application/json')
    if not table.empty:
        safe=table.map(lambda v:"'"+v if isinstance(v,str) and v.startswith(('=','+','-','@')) else v)
        st.download_button('比較明細CSVを保存',safe.to_csv(index=False).encode('utf-8-sig'),file_name='historical-records.csv',mime='text/csv')
