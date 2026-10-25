"""检查Git暂存区及所有可达历史，拒绝业务文件、凭证和大文件。"""
from pathlib import Path, PurePosixPath
import json
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
MAX_SIZE=512*1024
ROOT_FILES=set('app.py bootstrap.py client_app.py core.py source_core.py intelligence.py imports_exports.py storage.py reporting.py workflow.py field_printing.py legacy_views.py pdf_renderer.py print_manager.py workbench_component.py requirements.txt requirements-lock.txt requirements-dev.txt start_windows.bat run_tests.bat vendors.json README.md CONTRIBUTING.md SECURITY.md AGENTS.md SOURCE_MANIFEST.json ACCEPTANCE.md .gitignore .gitattributes 启动完整盘点客户端.cmd 启动盘点软件V1.3.cmd'.split())
ROOT_FILES.update({'report_intake.py','supplier_policy.py','vendor_audit.py'})
PATTERNS=[
    ('GitHub credential',re.compile(r'gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}')),
    ('AWS credential',re.compile(r'(?:AKIA|ASIA)[A-Z0-9]{16}')),
    ('private key',re.compile(r'-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----')),
    ('OpenAI credential',re.compile(r'\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{32,}')),
    ('credential literal',re.compile(r'''(?im)^\s*(?:password|passwd|api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*["'][^"'\n]{8,}["']''')),
    ('credential URL',re.compile(r'https?://[^\s/:]+:[^\s/@]+@')),
    ('personal Windows path',re.compile(r'(?i)[A-Z]:[\\/]+Users[\\/]+(?!Public\b|Default\b)[^\s"\']+')),
]

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT)

def allowed(path):
    p=PurePosixPath(path)
    if path in ROOT_FILES:return True
    if path=='.streamlit/config.toml':return True
    if path=='tests/workflow_acceptance.json':return True
    if len(p.parts)==2 and p.parts[0] in ('tests','scripts'):
        return p.suffix in ('.py','.mjs') and not p.name.startswith('.')
    if path in ('ui/workbench.js','ui/workbench.css'):return True
    if path in ('.github/workflows/ci.yml','.github/pull_request_template.md'):return True
    return False

def check(path,blob):
    errors=[]
    if not allowed(path):errors.append('path outside public-source allowlist')
    if len(blob)>MAX_SIZE:errors.append('file exceeds 512 KiB')
    try:text=blob.decode('utf8')
    except UnicodeDecodeError:return errors+['binary/non-UTF8 file']
    if '\x00' in text:errors.append('binary content')
    for label,pattern in PATTERNS:
        if pattern.search(text):errors.append(label)
    if path=='vendors.json' and json.loads(text)!=[]:errors.append('default supplier catalog must be empty')
    return errors

def main():
    errors=[];files=[];seen=set()
    for entry in git('ls-files','--stage','-z').decode('utf8').split('\0'):
        if not entry:continue
        meta,path=entry.split('\t',1);mode,sha,stage=meta.split()
        if mode not in ('100644','100755') or stage!='0':errors.append((path,['non-regular/unmerged entry']))
        blob=git('cat-file','blob',sha)
        found=check(path,blob)
        if found:errors.append((path,found))
        files.append(path);seen.add((sha,path))
    # 空仓库在首次提交前没有HEAD；rev-list --all仍可成功返回空结果。
    objects=git('rev-list','--objects','--all').decode('utf8').splitlines()
    history_blobs=0
    for line in objects:
        parts=line.split(' ',1)
        if len(parts)!=2:continue
        sha,path=parts
        if (sha,path) in seen:continue
        if git('cat-file','-t',sha).strip()!=b'blob':continue
        history_blobs+=1;found=check(path,git('cat-file','blob',sha))
        if found:errors.append((path,found))
    if not files:errors.append(('<index>',['no tracked source files']))
    result={'pass':not errors,'tracked_files':len(files),'additional_history_blobs':history_blobs,
            'all_reachable_history_scanned':True,'errors':errors}
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return 0 if not errors else 1

if __name__=='__main__':sys.exit(main())
