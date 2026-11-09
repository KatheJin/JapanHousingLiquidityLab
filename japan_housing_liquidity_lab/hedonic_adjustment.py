"""Independent diagnostic decomposition. Never certifies a historical adjusted price."""
import numpy as np
import pandas as pd
from .benchmark import Features
from .expansion import qi

ATTRIBUTE_COLUMNS=['area','minutes','distance_width','municipality','station','distance_kind','layout','structure']

def feature_states(record,target_quarter,reference=None):
    """Construction year stays fixed on the actual aging path; synthetic states are features only."""
    start=Features().transform(pd.DataFrame([record]))
    end=dict(record,quarter=target_quarter)
    physical=Features().transform(pd.DataFrame([end]))
    if qi(target_quarter)<qi(record['quarter']): raise ValueError('Forward comparison required')
    if not np.isfinite(start.age.iloc[0]) or not np.isfinite(physical.age.iloc[0]):
        raise ValueError('Known valid construction year required; do not impute aging')
    quality=start.copy()
    if reference is not None:
        # Reference construction year is evaluated at the historical period.
        rf=Features().transform(pd.DataFrame([dict(reference,quarter=record['quarter'])]))
        if not np.isfinite(rf.age.iloc[0]): raise ValueError('Known reference construction year required')
        for c in ATTRIBUTE_COLUMNS+['age']: quality[c]=rf[c]
    timed=quality.copy();timed['quarter_index']=physical.quarter_index
    aged=timed.copy();aged['age']=quality.age+(int(target_quarter[:4])-int(record['quarter'][:4]))
    return [start,quality,timed,aged]

def decompose(pipeline,record,target_quarter,actual_unit_price,reference=None,train_period=None):
    """Phase-3 boundary: unavailable adjusted price plus explicitly separate fitted diagnostics.

    Effects follow attributes -> time at fixed age -> aging. For HGB these are
    path-dependent. Period/cohort/age confounding prevents causal interpretation.
    No publication-as-of evidence or stable temporal calibration exists yet.
    """
    if not np.isfinite(actual_unit_price) or actual_unit_price<=0: raise ValueError('Positive finite unit price required')
    try: states=feature_states(record,target_quarter,reference)
    except ValueError as exc:return dict(status='unavailable',adjusted_unit_price=None,reasons=[str(exc)],diagnostic=None)
    values=[float(pipeline['model'].predict(pipeline['preprocess'].transform(s))[0]) for s in states]
    effects=np.diff(values)
    total=float(sum(effects))
    if not np.isfinite(values).all() or abs(total)>50:raise ValueError('Nonfinite or extreme model response')
    reasons=['Temporal adjustment not independently validated; current-vintage data is not a publication-as-of backtest.',
             'Age, period and construction cohort are confounded; these are model-dependent associations.']
    if train_period is None or not train_period[0]<=record['quarter']<=target_quarter<=train_period[1]:
        reasons.append('At least one comparison period lies outside the fitted period support.')
    return dict(status='unavailable',adjusted_unit_price=None,reasons=reasons,
                diagnostic=dict(attribute_log_effect=float(effects[0]),time_log_effect=float(effects[1]),
                    aging_log_effect=float(effects[2]),total_log_effect=total,
                    fitted_adjusted_unit_price=float(actual_unit_price*np.exp(total)),
                    starting_age=float(states[0].age.iloc[0]),ending_age=float(states[-1].age.iloc[0]),
                    original_construction_year=record.get('建築年'),
                    comparison_construction_year=(reference or record).get('建築年'),
                    construction_year_preserved_on_aging_path=True,order='attributes -> time holding age -> aging',
                    evidence='fitted diagnostic only; not a price index, causal effect, or purchase recommendation'))

def formal_adjustment_status(quarter):
    """Consumer-facing gate: research decompositions are not approved adjustments."""
    if quarter<'2023Q1':
        reason='拡張データ：既存モデルの適用期間外。'
    else:
        reason='時間・老化補正の独立検証が不足。Phase 2の研究診断は正式結果に使いません。'
    return dict(status='unavailable',reason=reason,attribute=None,time=None,aging=None)
