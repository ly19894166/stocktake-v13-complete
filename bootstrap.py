"""Create a recoverable local environment and launch on loopback only."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

def main():
    root=Path(__file__).resolve().parent;os.chdir(root)
    if not (3,11)<=sys.version_info[:2]<(3,14):
        print('Please use Python 3.11, 3.12 or 3.13 (64-bit).');return 1
    python=root/'.venv'/'Scripts'/'python.exe';lock=root/'requirements-lock.txt'
    marker=root/'.venv'/'.requirements_sha256'
    digest=hashlib.sha256(lock.read_bytes()).hexdigest()
    if not python.exists():
        print('[1/3] Creating local Python environment...',flush=True)
        venv.create(root/'.venv',with_pip=True)
    if not marker.exists() or marker.read_text()!=digest:
        print('[2/3] Installing dependencies. Internet is needed on first run.',flush=True)
        subprocess.run([str(python),'-m','pip','install','--disable-pip-version-check','-r',str(lock)],check=True)
        marker.write_text(digest)
    # PDF组件只能在Streamlit上下文中注册，环境自检只检查其模块可发现性。
    subprocess.run([str(python),'-c',
        "import streamlit,xlrd,xlwt,pandas,openpyxl,reportlab,importlib.util; "
        "assert importlib.util.find_spec('streamlit_pdf') is not None"],check=True)
    if '--check' in sys.argv:
        print('Environment check passed.');return 0
    port=os.environ.get('STOCKTAKE_PORT','8513')
    if not port.isdigit() or not 1024<=int(port)<=65535:raise ValueError('STOCKTAKE_PORT must be 1024..65535')
    print(f'[3/3] Open http://127.0.0.1:{port} . Keep this window open.',flush=True)
    return subprocess.call([str(python),'-m','streamlit','run',str(root/'app.py'),
        '--server.address','127.0.0.1','--server.port',port,'--browser.gatherUsageStats','false',
        '--server.headless','false'])

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as exc:
        print(f'Start failed: {exc}\nFix the error and run start_windows.bat again.');sys.exit(1)
