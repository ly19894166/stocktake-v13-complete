# V13操作流程重构验收

在既有PR #1和同一优化分支继续完成，main未合并，未合并其他实验分支。全部公开测试从零构造模拟数据；截图、XLS、PDF、SQLite和经营记录不提交公开仓库。已先备份正式程序和完整SQLite，部署前再取得停机一致性备份。

## 当前01紧凑布局验收

母版只读取01版式和列顺序，37条参考样本未导入、未覆盖正式数据。计算、原始单位调整、02三列、03打印、保存及审核规则保持原实现。

|验收项|实际验证|
|---|---|
|A—M列|按母版13列横向排列；1920/2560全部显示，1366只折叠编码与供货商，详情仍可查|
|默认排序|旧flowVersion3的串码/金额偏好均迁移为原始序号，1到450连续升序；已选新版本偏好可正常保留|
|三种窗口密度|1366×768首屏10条；1920×1080首屏18条；2560×1440首屏28条。普通行38px，输入30px，条码/编码完整，无横向溢出|
|连续操作|450条实际鼠标滚轮到底，无分页或表内滚动；固定表头位于顶部工具条下方，不被覆盖；深处保存不回顶、不失焦|
|横向数量|虚构2889/1/5：初盘差异-2888、最新-2884、找回4、成本-1816.92；系统、初盘、实数、当前总数直接可见|
|特殊单位|原始调整0.4保留：系统10，实数0时差异-9.6；清空实数恢复未复盘，与0严格区分|
|备注|单行普通输入，展开可编辑并保存多行长备注，不撑高行；系统提示始终不覆盖人工备注|
|核查标签|最优对应名称单行显示，可定位；归零撤销、恢复重现。更多候选完整可查，只有主动联排才重排|
|排序隔离|原始、金额、联排、品类可切换，联排相邻后可恢复1至450；后台记录ID和导出顺序不变|
|200条连续输入|原主流程再次实际录入200条实数和10条穿插备注，约28秒全部保存|
|02/03完整回归|450行真XLS逐行等于最新总数，文本/文本/数值、前导零和0保留；245条31页A4、245个大空框、重印字节一致，填写完成后退出默认清单|
|汇报与重启|最新数量/成本/鲜食生成/重置/复制、失败、版本冲突和取消回归通过；真实停止重启后全部模拟表内容一致，历史PDF浏览器可显示|
|自动测试|83项pytest通过，包含“原始顺序显示引擎最优候选、联排独立选择相邻配对”的界面载荷回归；其余原有回归全部保留|

新旧界面均使用同一套450条虚构商品，旧界面在修改前的e7d8b32版本拍摄。截图/XLS/PDF/数据库只留本机忽略目录；公开摘要见`tests/workflow_acceptance.json`，不包含母版或真实业务记录。

## 重复执行

紧凑专项：先生成450条模拟文件，使用独立`STOCKTAKE_DATA_DIR=tests/runtime/compact_data`在18543端口启动，运行`node tests/browser_compact.mjs`。可用`--before`对更新前的独立测试实例拍摄旧布局。禁止指向正式8513。

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
