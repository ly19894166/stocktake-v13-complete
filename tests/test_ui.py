from pathlib import Path
from streamlit.testing.v1 import AppTest
APP=Path(__file__).resolve().parents[1]/'app.py'

def test_new_import_has_no_store_time_form(tmp_path,monkeypatch):
    monkeypatch.setenv('STOCKTAKE_DATA_DIR',str(tmp_path/'empty'))
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    assert not at.exception
    assert len(at.get('file_uploader'))==2 # 单控件多文件+高级母版
    assert at.get('file_uploader')[0].proto.max_upload_size_mb>0
    assert not any('门店' in x.label or '时间' in x.label or '期间' in x.label for x in at.text_input)

def test_all_native_entries_and_optional_evidence(store,batch,monkeypatch):
    monkeypatch.setenv('STOCKTAKE_DATA_DIR',str(store.root))
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    at.selectbox(key='selected_batch').select(batch).run()
    assert not at.exception
    from client_app import PAGES
    assert PAGES==['01 现场复盘与找差异','02 领导审批报表','03 现场复核单打印','更多工具']
    for page in PAGES:
        at.session_state['navigation']=page;at.run()
        assert not at.exception,page
        assert not any(x.label=='下载公司盘点表.xls' for x in at.get('download_button')) # 迁入CCv2弹窗，由浏览器验证
    at.session_state['navigation']=PAGES[3]
    for tool in ['供货商数据库','变化清单/七表母版','来源与本地备份','商品档案与异常分析']:
        at.session_state['tools_mode']=tool;at.run();assert not at.exception,tool
    at.session_state['tools_mode']='商品档案与异常分析'
    for view in ['跨店与交易证据','商品档案','参数与批次设置','复盘变化轨迹','成对候选']:
        at.session_state['advanced_mode']=view;at.run()
        assert not at.exception,view

def test_print_callbacks_persist_before_following_rerender(store,batch,monkeypatch):
    monkeypatch.setenv('STOCKTAKE_DATA_DIR',str(store.root))
    at=AppTest.from_file(str(APP),default_timeout=30).run()
    from client_app import PAGES
    at.session_state['navigation']=PAGES[2];at.run()
    next(b for b in at.button if b.label=='生成并保存PDF').click().run()
    assert not at.exception and len(store.prints(batch))==1
    first=store.prints(batch)[0];blob=store.print_pdf(batch,first['id'])
    next(b for b in at.button if b.label=='原单重印并登记').click().run()
    assert not at.exception and len(store.prints(batch))==2
    repeated=store.prints(batch)[0]
    assert repeated['parent']==first['id'] and store.print_pdf(batch,repeated['id'])==blob
