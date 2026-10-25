# 第六次集中优化验收

范围：同一PR开发分支，导航仅01、03、更多工具。V13数量、原始调整、逐商品金额、2‰与季度汇报规则不改；真实资料不参与测试或进入公开源码。

## 自动与实际界面验证

- 138项Python/Node回归通过：覆盖原计算、0与空白、导入恢复、三列真XLS、打印原单、普通串码、供应商冲突/有效期与批次基准、人工档案历史、卓不凡资格、建议分离、10/-8示例、成本独立、单位/箱规不足、多候选、不同供应商、原始调整、四位精度、单方确认及重算、撤销、目录变更、幂等、事务失败回滚和重启。
- 独立500条虚构商品浏览器：一个控件导入两报表；60条确认卓不凡；20条旧人工授权档案仅留历史。默认仅排除卓不凡，普通串码存在，非卓不凡A换B为0。
- 建议先显示12/20，草稿不变正式数据。A确认后实数12、差异+2、金额+4，B仍空白；重新生成保留单方事实，B独立确认后数量32守恒。已确认值和原件不被重算覆盖。
- 实际鼠标拖拽、Shift矩形及Ctrl追加；精确求和单元用259格=9094，0.1+0.2=0.3及大整数验证。负数、0、空白、草稿及不同单位分别计数求和。
- 01弹窗读取全店500条，未复盘/核查未完成按旧规则阻断。先保存未失焦0和经营输入；仅卓不凡视图仍导出500行。独立xlrd验证真XLS签名、3列、文本/文本/数值与全量快照逐行相等。
- 双窗口在弹窗打开后修改正式数量，点击下载必须重新读取新revision；保存失败不得下载文件，输入草稿保留。
- 1366×768、1920×1080、2560×1440：第一/200/400/500条位置七项统计可见、表头不被遮挡、普通行≤42px（目标38px）、金额/完整条码可见且无横向溢出；选区固定底栏，导出对话框不越屏。
- 03默认排除确认卓不凡、品类/中类/序号排序；历史PDF与原单重印字节相等。414条A4为25页，前24页17条、末页6条；414个手写框，至少22pt高，中文字体嵌入，完整条码全量出现，无A换B/串码打印文字。首末页实际渲染检查。
- 实际停止并重启模拟服务，比较全部12表指纹，再打开浏览器验证实数、建议确认历史与历史PDF。

## 复现

安装`requirements-dev.txt`及Node Playwright1.62.1；Windows使用Edge，CI使用Chromium。中文字体参考README。

```powershell
$env:PYTHONPATH='.'
$env:STOCKTAKE_DATA_DIR='tests/runtime/sixth_ci_data'
$env:STOCKTAKE_SIXTH_DATA_DIR=$env:STOCKTAKE_DATA_DIR
$env:STOCKTAKE_TEST_URL='http://127.0.0.1:18546'
python -m pytest tests -q
python tests/prepare_sixth_demo.py
python -m streamlit run app.py --server.port 18546 --server.address 127.0.0.1 --server.headless true
# 另一个窗口在相同模拟环境变量下运行：
node tests/browser_sixth.mjs
python tests/verify_sixth_artifacts.py verify
python tests/verify_sixth_artifacts.py pdf
python tests/verify_sixth_artifacts.py before
# 停止并使用相同目录重新启动模拟服务后：
python tests/verify_sixth_artifacts.py after
node tests/browser_sixth.mjs --reopen
```

输出在忽略目录`tests/runtime/sixth_results`，含建议前/单方/双方确认截图、三分辨率第400条及弹窗、选区、全店XLS、专项Excel、历史PDF与A4页数报告。CI保存纯模拟验收附件14天，不上传SQLite或真实资料。旧第四/第五次脚本只是历史复现入口。

## 正式部署与数据保护

只有本地验证与当前提交GitHub CI全部通过后才部署。部署前再做一致性备份，逐表比较原10表全部记录并校验原件/PDF/供应商文件哈希，保留所有正式复盘。仅增加两张建议表；不得用500条模拟数据或37条母版覆盖真实记录。原件、供应商、打印、虚拟环境均不替换。具体备份路径、最终提交和部署后核对结果写入本机交付目录，避免将业务资料带入公开仓库。回滚详见[安全迁移](EXCHANGE_DATABASE.md)。
