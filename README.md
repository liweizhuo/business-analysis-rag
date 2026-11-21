# 经营分析 RAG 与 Text-to-SQL

> **本仓库仅公开项目的部分实现代码，不包含真实经营数据、企业业务知识、数据库文件、模型权重或有效 API 密钥。** `知识库.md` 和配置内容均为占位或教学示例，不能直接查询真实经营结果。本版本尚未完成外部服务联调及端到端验收，不是开箱即用的生产系统。

本项目展示经营分析问答的一条实现路径：通过 RAG 查找统计口径，让大模型结合口径与表结构生成 SQL，再由程序校验并查询 MySQL，最后计算和展示实际结果。

仓库包含中文前端和 FastAPI 入口，便于阅读各模块如何交接。项目说明、配置方法及启动步骤统一放在本 README 中，仓库不提供独立的 `docs` 文档目录。

## 1. 项目流程

### 离线准备

```text
业务知识文档
  → 读取正文与来源行号
  → 父子分块
  → BGE-M3 生成 dense / sparse 向量
  → 写入 Milvus，记录知识版本

真实 MySQL 数据 + 经确认的业务口径
  → 维护字段说明、指标定义、授权范围和数据版本
  → 发布业务配置
```

经营明细保存在 MySQL 中，由 SQL 完整聚合；向量库保存的是口径文字及来源。代码没有将检索到的几段文本当成完整经营记录求和。

### 在线问答

```text
用户问题与服务端身份
  → BGE-M3 编码问题
  → Milvus dense / sparse 混合召回
  → WeightedRanker 融合
  → 恢复父文、去重、CrossEncoder 重排
  → 组合 schema、确认规则与证据
  → 大模型生成 SQL 或提出澄清
  → SQLGlot AST 门禁及可信参数绑定
  → MySQL 只读查询
  → Decimal 计算金额差额与环比
  → 前端展示回答、SQL 和知识来源
```

## 2. 本次公开的内容与边界

|模块|已提供代码|边界|
|---|---|---|
|知识处理|Markdown 读取、父子分块、来源行号|知识文件仅含占位文字|
|向量检索|BGE-M3 dense / learned sparse、Milvus、加权融合|需要自行提供模型和 Milvus 服务|
|精排|父文恢复、去重、CrossEncoder|需要兼容的重排模型|
|SQL 生成|兼容 Chat Completions 的模型调用、JSON 输出协议|需要真实 API 配置，不保证模型每次生成正确 SQL|
|SQL 门禁|单表聚合 AST 核验、规则引用、季度、权限及版本约束|保守限定查询结构，不支持任意 SQL|
|数据计算|单季度新签金额、相邻季度环比、缺数与非正基期处理|使用教学字段契约，须与真实数据适配|
|前端|中文问答、业务规则入口、来源与查询结果展示|周报入口仅作展示，尚未实现生成逻辑|

企业数据接入、Excel ETL、自动对账、动态版本发布、SSO、多轮确认、复杂多表查询、多指标分析及自动化评测不在此次公开实现中。代码中声明了某个能力，不代表它已经在真实环境通过验收。

## 3. 工程目录

```text
.
├── main.py                  # 网页与 API 启动入口
├── prepare.py               # 离线知识建库入口
├── requirements.txt         # Python 依赖
├── .env.example             # 外部资源配置占位
├── .gitignore
├── 知识库.md                # 占位知识文件，需自行替换
├── config/
│   └── business.json        # 教学 schema、规则、版本与用户范围
└── app/
    ├── api.py               # HTTP 接口、访问密钥检查与静态资源
    ├── settings.py          # 环境变量和业务配置读取
    ├── knowledge.py         # Embedding、混合召回、父文恢复与精排
    ├── llm.py               # 模型提示词及 SQL 候选生成
    ├── guard.py             # SQL AST 核验与服务端参数绑定
    ├── db.py                # MySQL 独立连接及只读事务
    ├── service.py           # 问答流程、结果校验和计算
    └── static/
        ├── index.html      # 中文前端页面
        ├── app.css         # 页面样式
        └── app.js          # 前端交互与 API 请求
```

## 4. 运行前需要自行准备

建议使用 Python 3.11 或 3.12，并准备：

- MySQL 8 服务、真实分析表或视图，以及只读账号。
- 支持 dense / sparse 混合检索的 Milvus 服务。
- BGE-M3 模型及 CrossEncoder 兼容的重排模型。
- 支持 Chat Completions 和 JSON 对象返回的大模型 API。
- 真实业务知识文档、经确认的指标口径、数据发布版本与用户授权范围。

安装 Python 客户端不会自动启动 MySQL 或 Milvus。模型权重也不随本仓库分发；填写远程模型 ID 时，相关库可能在首次使用时下载模型。

## 5. 配置外部资源

在工程根目录执行以下命令。命令以 Windows PowerShell 为例：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item -LiteralPath .env.example -Destination .env
```

已有 `.env` 时直接编辑，避免覆盖。将其中的占位内容替换为真实配置：

|配置项|含义|
|---|---|
|`MYSQL_HOST` / `MYSQL_PORT`|MySQL 主机及端口，主机不带 `http://`|
|`MYSQL_DATABASE`|真实 MySQL 库名；`sql.db` 只是别名，不是 SQLite 文件|
|`MYSQL_USER` / `MYSQL_PASSWORD`|MySQL 只读账号及密码|
|`LLM_BASE_URL`|供应商提供的兼容接口基础地址|
|`LLM_API_KEY` / `LLM_MODEL`|模型密钥及真实模型 ID|
|`EMBEDDING_MODEL`|BGE-M3 的实际模型 ID 或本地目录|
|`RERANKER_MODEL`|重排模型的实际 ID 或本地目录|
|`MILVUS_URI` / `MILVUS_TOKEN`|Milvus 服务地址及认证凭据；无认证时 Token 留空|
|`KNOWLEDGE_FILE`|真实口径文件路径，默认 `知识库.md`|
|`CONFIG_FILE`|业务配置路径，默认 `config/business.json`|

仓库中的“大模型API”“MySQL地址”“重排模型”等文字只是说明性占位值。实际密码与密钥放在本地 `.env`，不要提交到仓库。

## 6. 适配真实经营数据

当前示例查询使用 `business_new_signing` 表，并要求以下字段：

|字段|含义|
|---|---|
|`snapshot_id`|已对账且保持不可变的数据发布版本|
|`quarter`|根据已确认业务日期生成的季度，例如 `2023Q1`|
|`region`|业务归属地区，与服务端授权范围一致|
|`amount_yuan`|人民币元金额，建议使用 `DECIMAL`|
|`include_flag`|是否按已确认口径计入，示例中 `1` 表示计入|

**仅填写数据库连接信息，不会自动适配任意业务表。** 可以由数据维护者建立符合上述字段契约的分析表或视图；若字段、指标或过滤逻辑不同，需要同步调整业务配置、模型提示词、SQL 门禁及结果处理。

`config/business.json` 中的表名可以配置，但金额等关键字段仍被代码明确引用，单独修改字段说明不能改变执行逻辑。真实数据的业务粒度、去重、日期归属、NULL 金额与汇总对账由接入方核对。`SUM` 会忽略 NULL，聚合结果非空不能证明所有源数据完整。

## 7. 建库与发布配置

先用真实业务口径替换 `知识库.md`，再执行离线建库：

```powershell
.\.venv\Scripts\python.exe prepare.py
```

程序将知识写入 Milvus，并打印知识版本。核对后编辑 `config/business.json`：

1. 配置真实表名及字段业务含义。
2. 将建库输出版本填入 `knowledge_version` 和 `rule.source_version`。
3. 填写真实 `snapshot_id` 和 `data_as_of`。
4. 核对规则定义、金额单位、计入条件及适用起止季度。
5. 将 `users` 中的占位访问密钥替换为真实访问密钥，并登记用户授权地区。
6. 确认数据与规则后，将 `published` 改为 `true`。

系统访问密钥与大模型 API 密钥是两种不同凭据。前端填写前者，后者只保存在后端。当前用户授权限定为单地区，未提供全公司或多地区权限策略。

## 8. 已知限制与验证状态

- 本公开版本未完成真实 MySQL、Milvus、模型 API 的联合验证，不承诺照填配置即可成功运行。
- SQL 门禁严格限定单表新签聚合；JOIN、CTE、同比、趋势、排名及多任务尚未开放，不会因为修改提示词就自动获得支持。
- 缺少任一比较期时不补零，基期为零或负数时不输出普通增长率。
- 口径文字回答由模型生成，尚未实现逐句事实与引用支持验证。
- 数据覆盖、规则冲突及版本发布管理仍需接入方完善；检索相关性不能证明业务规则有效。
- 前端周报功能尚未实现，界面保留待接入提示。

接入后应使用独立人工基准核对金额，并验证权限、版本过滤、SQL 拒绝案例、缺数处理及模型与 SDK 兼容性后，再考虑实际使用。
