from pathlib import Path
from streamlit.testing.v1 import AppTest
APP=Path(__file__).resolve().parents[1]/'app.py'

def test_new_import_has_no_store_time_form(tmp_path,monkeypatch):
    monkeypatch.setenv('STOCKTAKE_DATA_DIR',str(tmp_path/'empty'))
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    assert not at.exception
    assert len(at.get('file_uploader'))==3 # 2公司表+可选完整母版
    assert not any('门店' in x.label or '时间' in x.label or '期间' in x.label for x in at.text_input)

def test_all_native_entries_and_optional_evidence(store,batch,monkeypatch):
    monkeypatch.setenv('STOCKTAKE_DATA_DIR',str(store.root))
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    at.selectbox(key='selected_batch').select(batch).run()
    assert not at.exception
    from client_app import PAGES
    assert '03审核' not in PAGES and len(PAGES)==5
    for page in ['02变化/导出','供货商数据库','打印历史','高级异常明细','01复盘与智能找差异']:
        at.session_state['navigation']=page;at.run()
        assert not at.exception,page
        if page=='02变化/导出':
            assert any('正式导出检查' in x.label for x in at.expander)
    at.session_state['navigation']='高级异常明细'
    for view in ['跨店与交易证据','商品档案','参数与批次设置','复盘变化轨迹','成对候选']:
        at.session_state['advanced_mode']=view;at.run()
        assert not at.exception,view
