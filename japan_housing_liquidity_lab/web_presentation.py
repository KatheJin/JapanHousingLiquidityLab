"""Read-only buyer-facing formatting; original research results stay untouched."""
METHODS={'raw_unit_price':'未調整の成約単価','quality_all_history':'属性調整（全履歴）',
         'quality_recent_sensitivity':'属性調整（近年感度）','quality_and_time':'属性＋時間調整','time_only':'時間のみ'}


def percent(value):
    return '算出保留' if value is None else f'{value*100:.1f}'.rstrip('0').rstrip('.')+'%'


def unit_price(value):
    return 'データなし' if value is None else f'{value/10000:,.2f} 万円/㎡'


def method_rows(result):
    rows=[]
    for key,method in result['methods'].items():
        d=method['distribution_jpy_m2']
        rows.append({'方法':METHODS[key],'低価格記録割合':percent(method['lower_price_record_fraction']),
                     '低価格記録数':method['lower_price_record_count'],'比較記録数':d['n'],
                     '単価中央値':unit_price(d.get('median')),'第1四分位':unit_price(d.get('p25')),
                     '第3四分位':unit_price(d.get('p75'))})
    return rows


def reasons(result, historical, synthetic):
    out=[]
    if synthetic: out.append('合成デモのため、実在する住宅の価格や購入判断を評価するデータではありません。')
    n=result['comparable_n'] if historical else result['comparables']['n']
    if n<10: out.append(f'厳格な比較記録は{n}件です。最低10件に満たず、少数の取引に左右されるため判断を保留します。')
    if historical:
        spread=result.get('method_fraction_spread')
        if spread is not None:
            out.append(f'方法による低価格記録割合の最大差は{spread*100:.1f}ポイントです。どの調整が現在の割安さを正しく表すか、検証が足りません。')
        out.append('属性・時間調整は学習期間の記録を含む回顧的な計算です。学習窓にも敏感で、独立した予測性能の証明がありません。')
    else:
        mapping={'Unknown or invalid construction year':'建築年が不明または無効です。',
                 'Unknown station distance':'駅までの距離情報が不明です。',
                 'Area outside central 98% training support':'面積が学習データの中心98%の範囲外です。'}
        out.extend(mapping[r] for r in result['reason'] if r in mapping)
        out.append('モデルの誤差幅は過去の開発評価から移したもので、現在の価格を保証する予測区間ではありません。')
    out.append(f"参照は2026Q2までの過去データで、参考日との差は{result['data_lag_days']}日です。現在の即時市場価格は確認できていません。")
    out.append('過去の成約価格と現在の掲載価格は条件が違い、階・改装・向き・管理状態も十分に比較できません。')
    return out
