"""CCv2持续DOM工作台：保留输入、滚动、筛选；后台逐次确认保存。"""
from pathlib import Path
import streamlit as st
from core import json_bytes
ROOT=Path(__file__).parent
GRID=st.components.v2.component('stocktake_workbench_complete',
    html='<section id="stocktake-workbench" aria-label="01复盘与智能找差异"></section>',
    css=(ROOT/'ui'/'workbench.css').read_text('utf8'),
    js=(ROOT/'ui'/'workbench.js').read_text('utf8'))

def workbench(data,callback,key):
    return GRID(data=json_bytes(data).decode('utf8'),key=key,on_action_change=callback,height='content',width='stretch')
