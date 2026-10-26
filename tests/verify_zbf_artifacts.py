"""用独立Decimal及本机纯模拟SQLite核对专项金额、关系和拖选证据。"""
import os,sys,json,copy
from pathlib import Path
from decimal import Decimal as D
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from storage import Store
from core import current_amount,current_total,decimal_value
from supplier_policy import SupplierDirectory,effective_vendors
from reporting import financial_panel
OUT=ROOT/'tests/runtime/zbf_results'

def verify():
    folder=Path(os.environ.get('STOCKTAKE_ZBF_DATA_DIR',ROOT/'tests/runtime/zbf_data')).resolve();assert folder.is_relative_to((ROOT/'tests/runtime').resolve())
    snapshots=json.loads((OUT/'zbf_snapshots.json').read_text('utf8'));db=Store(folder);checked=0
    try:
        for snap in snapshots:
            original,_,state,_=db.load(snap['batch']);items=copy.deepcopy(original);view={r['id']:r for r in snap['rows']};assert len(items)==len(view)==(2407 if snap['name']=='large' else 500)
            for item in items:
                r=view[item['记录ID']];item['复盘实数']=decimal_value(r['stats_raw']['recount']);assert current_amount(item)==decimal_value(r['stats_raw']['amount']);checked+=1
            classes=SupplierDirectory(effective_vendors(state),state['meta']).classify_all(items);chosen=[x for x in items if classes[x['记录ID']]['status']=='zbf'];d=snap['dashboard'];amounts=[current_amount(x) for x in chosen]
            assert d['total']==len(chosen)==(2407 if snap['name']=='large' else 60) and d['reviewed']==sum(x.get('复盘实数') is not None for x in chosen)
            assert snap['panel']==financial_panel(items,state['meta'])
            if None in amounts:assert all(d[k] is None for k in ['net','distance','gain','loss']) and d['status']=='incomplete'
            else:
                gain=sum((v for v in amounts if v>0),D(0));loss=sum((v for v in amounts if v<0),D(0))
                assert D(d['gain'])==gain and D(d['loss'])==loss and D(d['net'])==gain+loss and D(d['distance'])==abs(gain+loss)
            plan=snap['balance']['plan'];pending=sum(r['stage']=='pending' for r in plan['rows'].values());verified=0;byid={x['记录ID']:x for x in chosen}
            for rel in plan['relations']:
                if rel['status']!='verified':continue
                legs=[plan['rows'][k] for k in (rel['a'],rel['b'])]
                assert all(leg['stage']=='confirmed' and decimal_value(leg['confirmed'])==byid[leg['id']]['复盘实数'] and str(leg['note']).strip() for leg in legs)
                assert sum((current_total(byid[leg['id']]) for leg in legs),D(0))==sum((D(leg['base_total']) for leg in legs),D(0));verified+=1
            assert d['pending_suggestions']==pending and d['verified_relations']==verified and not d['final_approved'] and not d['formal_balance_complete']
    finally:db.close()
    evidence=json.loads((OUT/'drag_evidence.json').read_text('utf8'));normal=snapshots[0];rows={r['id']:r for r in normal['rows']}
    for e in evidence:
        whole=e['all'];assert len(whole['keys'])==60 and whole['keys']==e['reverse']['keys']==e['forward']['keys']
        keys={tuple(json.loads(k)) for k in whole['keys']};assert (whole['ids'][0],'amount') in keys and (whole['ids'][-1],'amount') in keys
        values=[D(rows[k]['stats_raw']['amount']) for k in whole['ids']];assert [D(v) for v in e['clipboard'].splitlines()]==values
        assert D(e['reverse']['text'].split('求和：')[1])==sum(values,D(0))
        assert e['reverse']['first_top']>=e['reverse']['header_bottom']-2 and e['reverse']['first_top']<e['reverse']['header_bottom']+8
        assert e['reverse']['scroll']>0 and e['first_and_last_included'] and e['release_stopped']
    result={'pass':True,'simulated_only':True,'snapshots':len(snapshots),'rows_checked_against_core':checked,'three_resolutions':[e['width'] for e in evidence],'reverse_forward_column_equal':True,'first_row_visible_and_selected':True,'decimal_money_and_distance':True,'pending_vs_confirmed_independently_checked':True,'whole_scope_not_filtered':True}
    (OUT/'独立金额与反向选区验算.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8');return result

if __name__=='__main__':print(json.dumps(verify(),ensure_ascii=False))
