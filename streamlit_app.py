"""Japanese private-beta prototype. Start only on loopback until deployment approval."""
from datetime import date, datetime, timezone, timedelta
import json
import os
from pathlib import Path
import uuid

import pandas as pd
import streamlit as st
from japan_housing_liquidity_lab import web_adapter as ui
from japan_housing_liquidity_lab import listings
from japan_housing_liquidity_lab import web_presentation as display

st.set_page_config(page_title='住まいの判断ノート',page_icon='🏠',layout='wide')
st.title('住まいの判断ノート')
st.caption('東京都・中古マンション｜歴史的な取引参考と掲載観測の研究用プロトタイプ')
st.warning('購入の推奨・将来の値上がり予測は行いません。2026Q2までのデータは現在の即時価格ではなく、不完全・改訂の可能性があります。')
today=datetime.now(timezone(timedelta(hours=9))).date()
developer_demo=os.environ.get('JHLL_ENABLE_REAL')=='0' or os.environ.get('JHLL_ENABLE_DEMO')=='1'
real_enabled=os.environ.get('JHLL_ENABLE_REAL')!='0'
mode=st.sidebar.radio('データ', ['合成デモ','ローカル実データ'] if developer_demo else ['ローカル実データ'])
synthetic=mode=='合成デモ'
page=st.sidebar.radio('ページ',['住宅価格分析','過去の購入機会','地域と予算','掲載追跡','歴史成約分析'])
if page=='歴史成約分析':
    synthetic=False;mode='ローカル実データ'
st.info('合成デモ｜全て架空のデータです。実際の住宅の判断には使えません。' if synthetic else 'ローカル実データ｜過去の成約記録を使用します。現在の在庫・即時価格ではありません。')
if not synthetic:
    st.caption('出典：国土交通省「不動産情報ライブラリ」取引価格情報を加工した独自研究。公式の価格査定ではありません。 https://www.reinfolib.mlit.go.jp/')
st.sidebar.info('合成デモ：全て架空。価格モデルは学習済みモデルではなく画面確認用の固定値です。' if synthetic else '実データ：歴史成約分析では公開取引の明細を表示・保存できます。掲載の私有記録は別管理です。')
st.sidebar.caption('入力と履歴はこの接続のセッション内だけ。更新・切断で失う可能性があります。個人情報は入力しないでください。')
if st.sidebar.button('このセッションの入力・結果を消去'):
    st.session_state.clear();st.rerun()


def download(result, key):
    st.download_button('分析結果をJSON保存',json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),
                       file_name=key+'.json',mime='application/json',key=key+'_download')


def resources(need):
    if synthetic:
        b,df=ui.demo();return b,df,'2026-11-08'
    return ui.load_real(Path(os.environ.get('JHLL_DATA_ROOT',Path(__file__).parent)),need)


def home_form(age_mode):
    c1,c2,c3=st.columns(3)
    with c1:
        city=st.text_input('市区町村',value='架空区' if synthetic else '')
        town=st.text_input('町名（任意）')
        station=st.text_input('最寄駅',value='架空駅' if synthetic else '')
        walk=st.number_input('駅までの徒歩分（不明は空欄）',min_value=0,value=10 if synthetic else None)
    with c2:
        area=st.number_input('専有面積（㎡）',min_value=0.,value=70. if synthetic else None)

        year=st.number_input('建築年（西暦）',min_value=1800,max_value=today.year,value=2005 if synthetic else None) if age_mode=='建築年' else None
        age=st.number_input('築年数（年差）',min_value=0,max_value=150,value=None) if age_mode=='築年数' else None
        layout=st.text_input('間取り（不明は空欄）',value='2LDK' if synthetic else '')
    with c3:
        structure=st.text_input('構造（不明は空欄）',value='RC' if synthetic else '')
        price=st.number_input('掲載総額（万円）',min_value=0.,value=6000. if synthetic else None)
        reference=st.date_input('参考日',value=today)
    return city,town,station,walk,area,year,age,layout,structure,price,reference


if page=='歴史成約分析':
    from japan_housing_liquidity_lab.history_page import render
    render()
elif page in ['住宅価格分析','過去の購入機会']:
    historical=page=='過去の購入機会'
    st.header(page)
    st.info('比較範囲：既存Task 005/006の2023Q1～2026Q2。Task 008の拡張モデルへ自動置換しません。')
    st.caption('実参照モデル：全履歴／時間項ありは2023Q1～2026Q2、近年モデルは2025Q3～2026Q2に適合。経験誤差の評価は2025年開発集です。新たな独立テスト結果ではありません。')
    age_mode=st.radio('築年の入力方法',['建築年','築年数'],horizontal=True)
    with st.form('home_'+mode):
        values=home_form(age_mode)
        if historical:
            start=st.text_input('比較開始四半期',value='2023Q1');end=st.text_input('比較終了四半期',value='2026Q2')
        submitted=st.form_submit_button('分析する')
    if submitted:
        st.session_state.pop('home_result',None)
        try:
            q=ui.home_query(*values)
            if historical: q.update(history_start=start,history_end=end)
            with st.spinner('既存の参照方法で集計しています…'):
                b,df,available=resources('home');result=ui.analyze_home(b,df,q,historical)
            st.session_state['home_result']=(page,mode,dict(result=result,input=q,data_mode=mode,available_on=available))
        except (ValueError,OSError,KeyError,TypeError) as exc:
            st.error('入力・データを確認してください。期間は取得済み範囲内、参考日はデータ取得日以降が必要です。')
            with st.expander('詳細（入力の個人情報を含めないでください）'): st.text(str(exc))
    saved=st.session_state.get('home_result')
    if saved and saved[:2]==(page,mode):
        payload=saved[2];r=payload['result'];st.error('判断できません：この結果だけで購入や割安さを判断できません。')
        st.subheader('判断を保留する理由')
        for reason in display.reasons(r,historical,synthetic): st.write('・'+reason)
        if synthetic:
            st.warning('架空データの画面デモです。モデル参考価格は固定値、表示割合は固定生成した架空記録から計算しています。繰り返す四半期の棒グラフも生成規則によるもので、実市場の価格・季節性・購入確率を示しません。')
        st.caption(f"データ取得確認日 {payload['available_on']} ｜ 参考期 2026Q2 ｜ 時差 {r['data_lag_days']}日 ｜ {mode}")
        if not historical:
            c=r['comparables'];st.metric('厳格な比較取引件数',c['n'])
            st.caption('同市区町村・駅、任意の町名、面積±20%、築年数±10年、直近4四半期。10件未満は不足です。')
            labels={'all_history_no_time':'全履歴（時間項なし）','recent_no_time':'近年のみ','history_with_time':'全履歴＋取引時期'}
            rows=[dict(方法=labels[k],参考総額_万円=v['total_price']/10000,参考単価=display.unit_price(v['unit_price']),掲載偏差=f"{v['deviation_pct']:+.1f}%",経験誤差下限_万円=v['empirical_total_range'][0]/10000,経験誤差上限_万円=v['empirical_total_range'][1]/10000) for k,v in r['model_references'].items()]
            st.dataframe(pd.DataFrame(rows),hide_index=True)
            st.warning('誤差幅は2025年開発評価から移した経験的な範囲です。信頼できる校正済み予測区間ではありません。')
            if 'median' in c: st.write('比較取引単価：中央値',display.unit_price(c['median']),'、四分位範囲',display.unit_price(c['p25']), '～',display.unit_price(c['p75']))
        else:
            st.metric('歴史的な厳格比較取引件数',r['comparable_n'])
            raw=r['methods']['raw_unit_price'];distribution=raw['distribution_jpy_m2']
            st.subheader('過去の比較記録の概要（未調整）')
            a,b=st.columns(2)
            a.metric('過去の成約単価の中央値',display.unit_price(distribution.get('median')))
            b.metric('入力した掲載単価',display.unit_price(float(payload['input']['asking_price_jpy'])/float(payload['input']['面積（㎡）'])))
            st.write('過去の単価の中央50%：',display.unit_price(distribution.get('p25')),'～',display.unit_price(distribution.get('p75')))
            st.metric('掲載単価を下回る過去記録の割合（未調整）',display.percent(raw['lower_price_record_fraction']))
            st.caption(f"分子：掲載単価を下回る{raw['lower_price_record_count']}記録／分母：比較対象の{r['comparable_n']}記録。10件未満は割合を算出保留します。比較期間：{r['historical_window'][0]}～{r['historical_window'][1]}。")
            st.warning('これは過去の比較記録のうち何件が入力単価より低かったかという集計です。「65%」でも、将来65%の確率で安い住宅を買えるという意味ではありません。現在の在庫や将来の供給、購入可能性を測定していません。低い成約単価だけで住宅の総合的な良さも判断できません。')
            with st.expander('高度な分析：5つの研究方法・四半期分布・全研究明細',expanded=False):
                st.caption('方法は選別・統合していません。割合は%表示、単価は万円/㎡。丸め前の値とその他の統計は下の完全明細とJSON保存に残します。')
                st.dataframe(pd.DataFrame(display.method_rows(r)),hide_index=True)
                if synthetic: st.warning('この表の価格・割合と下の棒グラフは全て架空データです。同じ高さの棒はデータ生成規則によるもので、実市場の規則ではありません。')
                st.bar_chart(pd.DataFrame([{'四半期':x['quarter'],'比較記録数':x['comparable_n']} for x in r['quarterly']]).set_index('四半期'))
                st.caption('未取得四半期の欠損はゼロ取引を意味しません。')
                st.warning('Task 008で学習窓への感度を確認しています。旧調整は学習記録を含む回顧的計算で、方法の差は実際の優位性を証明しません。')
                st.json(r,expanded=False)
        st.caption('階・内装・向き・管理状態の違い、掲載価格と成約価格の違いが残ります。')
        download(payload,'home_analysis')

elif page=='地域と予算':
    st.header('地域と予算')
    st.info('歴史的な成約サンプルの比較です。現在販売中の住宅ではありません。鉄道・車・自転車・混合交通の所要時間は未検証です。')
    with st.form('budget_'+mode):
        c1,c2=st.columns(2)
        with c1:
            lo=st.number_input('予算下限（万円）',min_value=0.,value=0.)
            hi=st.number_input('予算上限（万円）',min_value=0.,value=6000.)
            area=st.number_input('最小面積（㎡）',min_value=0.,value=40.)
            age=st.number_input('最大築年数（取引時）',min_value=0,value=40)
        with c2:
            walk=st.number_input('駅までの徒歩上限（分）',min_value=0,value=15)
            cities=st.text_input('比較市区町村（カンマ区切り・空欄は全地域）')
            start=st.text_input('開始四半期',value='2025Q1')
            end=st.text_input('終了四半期',value='2026Q2')
            reference=st.date_input('参考日',value=today)
        modes=st.multiselect('交通手段（時間の絞込みには未対応）',['public_transport','private_car','bicycle','mixed'],default=['public_transport'])
        go=st.form_submit_button('地域を比較する')
    if go:
        st.session_state.pop('budget_result',None)
        try:
            b,df,available=resources('location')
            q=dict(reference_date=str(reference),history_start=start,history_end=end,budget_min_jpy=lo*10000,budget_max_jpy=hi*10000,min_area_m2=area,max_age=age,max_walk_minutes=walk,municipalities=[x.strip() for x in cities.split(',') if x.strip()],transport_modes=modes)
            r=ui.budget(df,q,available)
            st.session_state['budget_result']=(mode,dict(result=r,data_mode=mode,available_on=available))
        except (ValueError,OSError,KeyError,TypeError): st.error('条件またはデータを確認してください。開始～終了の全四半期が必要です。')
    saved=st.session_state.get('budget_result')
    if saved and saved[0]==mode:
        payload=saved[1];r=payload['result'];st.metric('条件に一致した歴史記録数',r['matched_n'])
        st.caption('予算などの絞込み後30件未満では価格・面積・築年数の要約を保留します。閾値は信頼性保証ではありません。')
        for title,key in [('市区町村','regions'),('市区町村＋駅','stations'),('間取り分布','layouts')]:
            st.subheader(title)
            table=pd.DataFrame(r[key])
            fields={'municipality':'市区町村','station':'駅','n':'条件一致記録数','period_sample_n':'期間内全条件前記録数','area_median':'面積中央値_㎡','area_p25':'面積第1四分位','area_p75':'面積第3四分位','age_median':'取引時築年数中央値','age_p25':'築年数第1四分位','age_p75':'築年数第3四分位','modal_layout':'最多間取り','total_jpy_median':'成約総額中央値_円','period_min':'最初の四半期','period_max':'最後の四半期','layout':'間取り'}
            st.dataframe(table[[c for c in fields if c in table]].rename(columns=fields),hide_index=True)
        st.warning('通勤時間：不明。駅までの徒歩分を全行程の通勤時間として使っていません。')
        download(payload,'budget_analysis')

else:
    st.header('気になる住宅の掲載追跡')
    st.info('この接続のセッション内だけで保持します。継続利用には履歴ZIPをダウンロードし、次回journal.jsonを再インポートしてください。今回取得済みの実掲載は0件。手入力でも利用権利が必要です。')
    journal_key='journal_demo' if synthetic else 'journal_real'
    batches=st.session_state.get(journal_key,[])
    with st.form('manual_'+mode):
        a,b=st.columns(2)
        with a:
            source=st.text_input('情報源名',value='SYNTHETIC-A' if synthetic else '')
            lid=st.text_input('媒体ごとの掲載ID',value='SYNTHETIC-1' if synthetic else '')
            price=st.number_input('観測価格（万円）',min_value=0.,value=6000. if synthetic else None)
            observed=st.text_input('観測日時（日本時間・例 2026-11-08T12:00:00+09:00）',value=datetime.now(timezone(timedelta(hours=9))).isoformat(timespec='seconds'))
            state=st.selectbox('観測結果',['present','missing','failed','partial','provider_withdrawn','provider_sold'],format_func=lambda x:{'present':'掲載を確認','missing':'固定IDを完全確認し非観測','failed':'確認失敗','partial':'部分確認のみ','provider_withdrawn':'提供元が撤回を明示','provider_sold':'提供元が成約を明示（主張）'}[x])
        with b:
            pid=st.text_input('同一住宅の内部ID（任意・未入力なら分離）')
            match=st.text_input('別掲載と同一住戸である確認根拠（結合時必須）')
            evidence=st.text_input('観測の確認根拠（個人情報を除く参照ID）')
            rights=st.text_input('利用・保管権利の根拠（参照ID）')
            permitted=st.checkbox('必要な使用権利と観測の完全性を確認しました')
        st.caption('住所や棟名だけで同一住戸と決めないでください。missingは個別IDの完全確認時のみ。失敗・部分確認は消失ではありません。')
        with st.expander('住宅属性（任意・未知値を推定しません）'):
            attrs={}
            for label,field in [('市区町村','municipality'),('町名','town'),('最寄駅','station'),('間取り','layout'),('構造','structure')]:
                value=st.text_input(label,key='tracking_'+mode+'_'+field)
                if value.strip(): attrs[field]=value.strip()
            for label,field in [('面積（㎡）','area_m2'),('徒歩分','walk_minutes'),('建築年','built_year')]:
                value=st.number_input(label,min_value=0.,value=None,key='tracking_'+mode+'_'+field)
                if value is not None: attrs[field]=value
        add=st.form_submit_button('観測を記録する')
    if add:
        try:
            if not permitted: raise ValueError('権利と完全性の確認が必要です。')
            incoming=ui.manual_batch(source,lid,price,observed,state,evidence,rights,synthetic,pid,match,**attrs)
            batches=ui.append_batches(batches,[incoming]);st.session_state[journal_key]=batches;st.success('観測を記録しました。')
        except (ValueError,TypeError,KeyError,OSError): st.error('記録できません。ID・日時・権利・同一住戸根拠・属性・入力順を確認してください。')
    upload=st.file_uploader('許可済みJSON／CSV（最大2MB・JSON履歴も可）',type=['json','csv'],key='upload_'+mode)
    meta=st.file_uploader('CSVの場合は権利・確認範囲を含むメタデータJSON',type=['json'],key='metadata_'+mode)
    consent=st.checkbox('取り込む資料の使用権利を確認し、不要な個人情報を除去しました',key='upload_consent_'+mode)
    if st.button('ファイルを取り込む'):
        try:
            if not upload or not consent: raise ValueError()
            incoming=ui.import_bytes(upload.name,upload.getvalue(),meta.getvalue() if meta else None)
            if any((x['data_kind']=='synthetic')!=synthetic for x in incoming): raise ValueError()
            batches=ui.append_batches(batches,incoming);st.session_state[journal_key]=batches;st.success('取込み完了。同じ観測の再取込みでは増殖しません。')
        except (ValueError,KeyError,TypeError,OSError,UnicodeError): st.error('取込みできません。形式・権利・実／合成の区分・観測日時順を確認してください。')
    if batches:
        r=listings.replay(batches)
        st.caption('消失日時は確認時刻です。実際の掲載終了・成約日ではありません。全消失は全ての監視済み媒体のみを意味します。')
        states={'partial_disappearance':'一部媒体で消失確認','full_disappearance':'全監視媒体で消失確認','presence_observed':'掲載確認あり','unknown_coverage':'確認不完全・同定未確定'}
        st.dataframe(pd.DataFrame([{'住宅ID':p['property_id'],'観測状態':states[p['state']],'最初の媒体消失確認':p['first_source_disappeared_at'],'全監視媒体の初回消失確認':p['first_full_disappeared_at']} for p in r['properties']]),hide_index=True)
        kinds={'price_down':'価格低下','price_up':'価格上昇','price_unchanged':'価格不変','listing_disappeared':'媒体内掲載が非観測・終了確認','source_disappearance':'媒体で全掲載消失を確認','first_source_disappearance':'最初の媒体消失確認','reappeared':'同じ掲載が再出現','new_listing_linked':'別掲載を同一住戸へ結合','attributes_changed':'属性変更','identity_review_required':'同一住戸の再確認が必要','observation_incomplete':'確認不完全','property_state_changed':'住宅集約状態の変更','listing_start_conflict':'掲載開始日が不一致'}
        events=pd.DataFrame([{'確認日時':e['observed_at'],'住宅ID':e['property_id'],'媒体':e.get('source'),'出来事':kinds.get(e['kind'],e['kind'])} for e in r['events']]);st.dataframe(events,hide_index=True)
        price_rows=[dict(観測日時=s['observed_at'],媒体=s['source'],掲載ID=s['listing_id'],価格_万円=s['record']['price_jpy']/10000) for s in r['snapshots'] if s.get('record') and s['record'].get('price_jpy')]
        if price_rows:
            chart=pd.DataFrame(price_rows);st.dataframe(chart,hide_index=True)
            chart['媒体掲載']=chart['媒体']+' / '+chart['掲載ID']
            st.line_chart(chart,x='観測日時',y='価格_万円',color='媒体掲載')
        st.caption('CSVは表計算での式実行を防ぐため、一部文字列に先頭のアポストロフィを付けます。元の値と履歴の復元にはjournal.jsonを使ってください。')
        st.download_button('履歴JSON＋CSVをZIP保存',ui.journal_zip(batches),file_name='listing-history.zip',mime='application/zip')
        if os.environ.get('JHLL_LOCAL_SAVE')=='1' and os.environ.get('JHLL_RUNTIME','local')=='local':
            if st.button('このPCの専用フォルダに履歴を保存'):
                sid=st.session_state.setdefault('storage_id',uuid.uuid4().hex)
                folder=Path(__file__).parent/'data/web-sessions'/sid;folder.mkdir(parents=True,exist_ok=True)
                path=folder/(uuid.uuid4().hex+'.json');path.write_text(json.dumps(dict(version=listings.VERSION,batches=batches),ensure_ascii=False),encoding='utf-8')
                st.success('ローカルのdata/web-sessions内へ保存しました。別ユーザーの履歴は読み込みません。')

with st.expander('試用とフィードバック'):
    st.write('報告には画面名・期待した動作・実際の動作・合成モードかどうかを記入してください。個人住所・価格入力・スクリーンショットの個人情報は除去してください。自動送信や外部アクセス解析は行いません。')
    st.caption('Task 011 / local prototype. クラウド公開・アクセス制御・許諾データ配信は未実施です。')

