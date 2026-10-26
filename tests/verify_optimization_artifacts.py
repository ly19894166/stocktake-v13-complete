"""兼容入口：独立核验当前450条模拟流程文件和真实进程重启。"""
from pathlib import Path
import runpy
if __name__ == "__main__":
    runpy.run_path(str(Path(__file__).with_name("verify_workflow_artifacts.py")),run_name="__main__")
