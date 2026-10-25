# 第四次集中优化验收

继续PR #1及feature/complete-workbench-quarterly-report分支，不合并main。开发前先备份正式程序、真实供应商与SQLite完整8表。所有测试均从零构造模拟资料，不上传母版、真实报表、供应商、截图、SQLite或打印历史。

|验收项|实际结果|
|---|---|
|一键导入|一个控件同时选择两份、顺序不限；450条实际导入；重复上传恢复原批次和已保存0，不覆盖记录|
|严格识别|两类结构/数量方向/名称交叉确认；缺份、重复、同方向、混合方向、标识矛盾或空文件拒绝；中性文件名可由实际方向确认|
|统一归属|模拟60条已确认卓不凡、25条待确认；同编码别名可归一、不同供应商/未确认编码/有效期异常保留待确认；01供应商筛选也是60条|
|02专项审计|16列、60条、25待确认、900对A换B；金额与后台一致；下载Excel逐格读回匹配；人工说明和凭证刷新后、进程重启后仍保留|
|公司全口径|实际下载真旧XLS，Sheet1严格三列，450行含全部60条卓不凡；文本/文本/数值、前导零和0、原导出顺序及最新实物总数一致|
|03筛选|默认390；包含450；仅卓不凡60；不打印待确认365。待确认默认保留且数量明示；预览/留档/新单共用规则|
|找货排序|档案大类、中类、原始序号稳定排列；仅使用实际已有品类设置确认路线，无虚构货架/类别；也可切换原序号/金额|
|414条A4|25页，前24页每页17条、最后6条；414个至少22点高手写框，完整条码各一次，中文TrueType嵌入；实际渲染检查首页、中间及尾页、长名称|
|去除纸单分析|PDF无串码/A换B/疑似说明，不分配对背景或联排；01/02分析保留|
|打印历史|实际留档、原单重印、新数据新ID；重印PDF字节与原文件完全一致，新筛选不改旧PDF|
|七项悬浮|1366×768、1920×1080、2560×1440，分别滚到第1/200/400条；七项完整可读，表头在悬浮条下方；深处填0金额实时更新，不失焦不回顶|
|口径隔离|03供应商选项变化前后完整financial_panel逐项相同；整店2‰包含卓不凡，非卓不凡口径明确仅内部分析|
|持久化回调|供应商导入、专项凭证、生成/重印/新打印采用写入回调及保存反馈；浏览器刷新和独立文件检查确认真实落库；原有版本冲突保护保留|
|原功能|98项pytest通过，包括旧V13、原始单位调整、0/空白、2‰精确边界、供应商冲突、报告、存储、导出、恢复/撤销和新增回归；季度汇报实际生成并复制最新金额|
|真实进程重启|停止并重启18544，450条实数/备注/目录/说明/凭证恢复，历史PDF实际浏览器渲染；全部8表完整哈希一致|

可公开结果摘要在tests/workflow_acceptance.json。截图和文件只在本机tests/runtime/fourth_results，不能当真实公司报表使用。PDF视觉查看不等同于实体打印机试打。

## 重复执行

1. 安装requirements-dev.txt、Playwright与Edge，Windows使用黑体或STOCKTAKE_CJK_FONT指定嵌入字体；Linux CI使用文泉驿字体。
2. 运行python -m pytest tests -q和python tests/prepare_fourth_demo.py。
3. 使用全新独立STOCKTAKE_DATA_DIR=tests/runtime/fourth_verified_data启动python -m streamlit run app.py --server.address 127.0.0.1 --server.port 18544 --server.headless true。禁止使用正式库或8513。
4. 运行node tests/browser_fourth.mjs。可设PLAYWRIGHT_MODULE和STOCKTAKE_BROWSER_CHANNEL。
5. 设STOCKTAKE_FOURTH_DATA_DIR与应用模拟目录相同，运行python tests/verify_fourth_artifacts.py audit及pdf；用pdftoppm渲染PDF检查首页、长名称及尾页。
6. 运行node tests/browser_fourth.mjs --final-export，再运行python tests/verify_fourth_artifacts.py company。
7. 运行python tests/verify_fourth_artifacts.py before，真正停止重启模拟进程后运行node tests/browser_fourth_reopen.mjs及python tests/verify_fourth_artifacts.py after。
8. 暂存后python scripts/check_public_tree.py扫描暂存区及所有可达历史；提交并推送到同一PR，GitHub CI通过后再按授权备份和更新正式软件。

既有browser_workflow/browser_compact等回归入口保留，并已适配主入口变化；其各自模拟目录、端口和前置样本不同，不能混用已完成的批次。Git历史保留之前版式与对应验收。

## 安全更新与回滚

正式更新前停止已核实的8513进程，用SQLite备份API取得包含已提交WAL的一致性副本，逐行核对8表和完整性；保存原程序及供应商哈希。只替换当前提交涉及的运行源文件，保留data、vendors.json、虚拟环境和锁定依赖。启动原Windows脚本后只读验收，再比较全部表内容及原文件哈希。

回滚优先只恢复更新前程序，不回退数据库，保留升级后新增复盘。若必须恢复旧库，应先保全新记录，停止程序后用SQLite备份API恢复完整副本并核对残留WAL/SHM；不要运行时覆盖主库或丢弃新记录。具体备份位置及本机核对结果见本地交付说明。
