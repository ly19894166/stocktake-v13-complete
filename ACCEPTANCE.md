# V13操作流程重构验收

在既有PR #1和同一优化分支继续完成，main未合并，未合并其他实验分支。全部公开测试从零构造模拟数据；截图、XLS、PDF、SQLite和经营记录不提交公开仓库。已先备份正式程序和完整SQLite，部署前再取得停机一致性备份。

## 已完成的操作验收

|验收项|实际验证|
|---|---|
|上传即操作|450条两份模拟报表上传后直接进入01，无强制店名/时间输入|
|连续滚轮|450条唯一记录常驻，22次鼠标滚轮到底，约47842px，无分页、表内滚动、大片空白或回顶|
|保存连续性|列表深处输入和详情开关保留滚动/焦点；200条连续实数和10条穿插备注全部保存，约32秒|
|三种实际窗口|1366×768、1920×1080、2560×1440，表宽约1204/1758/2398，无关键列溢出；长名称换行|
|主行数量|虚构系统2889、初盘1、实数5：-2888→-2884，找回4件，成本-1816.92；原始调整另测|
|主行对应商品|具体名称、条码、对方差异可见，双向定位，联排双方都可编辑；多对多不重复计数|
|动态提示|归零撤销，恢复重现，不相关候选和人工备注保留；金额/联排视图均保留450条唯一记录|
|02最终模板|未核实阻断下载；全部填写、单位说明与确认后实际下载真XLS，Sheet1严格三列，450行与最新有效总数逐行一致；文本/文本/数值，前导零和0保留|
|03现场单|默认未填且非零，盘亏优先不漏盘盈，245条实际预览/下载/留档；填写完成后默认清单立即为空|
|打印文件|31页A4横向，中文字体嵌入、245个大空框、条码各一次、成对商品不跨页；原单重印字节相同，新数据生成新ID|
|汇报风险|延迟保存时立刻修改实数/成本/鲜食，再打开/重新生成/复制，等待期间隐藏旧稿，复制金额与最新保存一致|
|失败和冲突|无效成本保存失败、第二窗口真实版本冲突、等待时关闭窗口均不覆盖剪贴板；人工稿保存可用，源变化后重新生成使用最新金额|
|重启|真正停止并重启模拟进程，450条实数、备注、经营值和鲜食恢复；全部业务表完整哈希一致，历史PDF可预览|
|其他能力|供应商、商品档案、异常、跨店证据、参数、轨迹、变化、七表和备份均在更多工具，既有自动回归保留|
|自动回归|82项pytest通过；推送与PR的GitHub Actions运行相同测试与全部可达历史隐私扫描|

`tests/workflow_acceptance.json`保存可公开的模拟验收摘要；具体运行截图、下载文件和日志只在本机忽略目录。

## 重复执行

1. 安装`requirements-dev.txt`、Playwright、Edge。Windows使用黑体，Linux CI配置可嵌入中文字体。
2. 运行`python -m pytest tests -q`及`python tests/prepare_workflow_demo.py`。
3. 使用全新的独立目录`STOCKTAKE_DATA_DIR=tests/runtime/workflow_final_data`，启动`python -m streamlit run app.py --server.address 127.0.0.1 --server.port 18541 --server.headless true`。禁止指向正式数据或8513端口。
4. 运行`node tests/browser_workflow.mjs`（完整上传、450条、200次输入、三分辨率、02/03操作），再运行`node tests/browser_report_barrier.mjs`（PR审查风险回归）。可用`PLAYWRIGHT_MODULE`指定本机模块位置。
5. 安装开发依赖中的pypdf后，运行`python tests/verify_workflow_artifacts.py`重新读入下载XLS和留档PDF核验。
6. 运行`python tests/verify_workflow_artifacts.py before`，真正停止并重启18541进程，运行`node tests/browser_workflow_reopen.mjs`及`python tests/verify_workflow_artifacts.py after`。
7. 供应商/跨店补充界面测试：生成`tests/synthetic_data.py`和`tests/prepare_module_demo.py`，新建独立18542端口和数据目录，再运行`node tests/browser_existing_modules.mjs`。
8. 暂存后执行`python scripts/check_public_tree.py`，检查全部待提交文件及所有可达历史，再提交、推送到同一个PR。

旧`browser_optimization.mjs`、`browser_synthetic.mjs`、`browser_restart_check.mjs`及`verify_optimization_artifacts.py`保留为兼容入口，调用当前流程测试；历史脚本可在Git历史查看。

## 正式更新和安全回滚

正式更新仅替换本次提交的运行源码和界面文件，不复制模拟库、供应商空目录或虚拟环境。先停止已核实的正式进程，使用SQLite备份API取得含WAL提交的完整一致性副本，核对所有表逐行相同并保存旧程序压缩包；再替换代码、启动原8513端口，只读验收并再次逐表比对。保留全部原件、打印PDF、历史轨迹、目录和依赖环境。

回滚前先停止客户端并备份当前程序和当前完整数据库。如果只是界面/代码问题，优先只恢复更新前程序；本次未改变数据库结构。若确需恢复旧数据库，必须先单独保全更新后产生的记录，使用SQLite备份API恢复一致性副本并处理残留WAL/SHM；不要在运行时覆盖主库文件，不要直接删除业务数据。具体备份位置和本机验证结果随本地交付记录提供。
