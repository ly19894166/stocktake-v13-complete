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
    assert '03审核' not in PAGES and len(PAGES)==4
    for page in PAGES:
        at.session_state['navigation']=page;at.run()
        assert not at.exception,page
        if page==PAGES[1]:
            assert any('导出检查' in x.label for x in at.expander)
            assert any(x.label=='下载公司盘点表.xls' and x.disabled for x in at.get('download_button'))
    at.session_state['navigation']=PAGES[3]
    for tool in ['供货商数据库','变化清单/七表母版','来源与本地备份','商品档案与异常分析']:
        at.session_state['tools_mode']=tool;at.run();assert not at.exception,tool
    at.session_state['tools_mode']='商品档案与异常分析'
    for view in ['跨店与交易证据','商品档案','参数与批次设置','复盘变化轨迹','成对候选']:
        at.session_state['advanced_mode']=view;at.run()
        assert not at.exception,view
