# 经营分析 RAG 与 Text-to-SQL 工程

本工程依据新的“离线准备—在线问答”主线编写，包含中文网页与统一API入口。源码未运行、未联调，不代表外部依赖已经验收。外部资源名称为占位符。

## 工程入口

接入真实资源的逐步操作见 [真实数据接入与运行](docs/真实数据接入与运行.md)。先完成该说明中的配置和对账，再启动网页。

- `main.py`：Web/API入口，网页位于 `/`，开发接口位于 `/docs`。
- `prepare.py`：离线知识解析、父子切块、BGE-M3编码和Milvus入库入口。
- `app/service.py`：在线问答主线。
- `config/business.json`：指标、schema、规则、发布版本和服务端身份范围。
- `docs/项目说明.md`：流程、边界与配置说明。

## 环境准备与启动命令

以下命令交给使用者操作，本次交付不执行。使用Python 3.11或3.12。

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

填写 `.env`，准备MySQL和Milvus服务、模型文件及大模型接口。`sql.db`只是MySQL数据库名别名，没有SQLite文件。模型配置填写实际模型仓库ID或本地目录。

```powershell
.venv\Scripts\python prepare.py
```

核对知识入库结果，将输出版本登记到业务配置的 `knowledge_version` 和规则的 `source_version`。根据真实业务核对schema、数据覆盖、规则适用期、授权地区及数据版本，完成后才将 `published` 设为true。

```powershell
.venv\Scripts\python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

浏览器打开 `http://127.0.0.1:8000/`，输入配置中的用户访问密钥后提问。密钥只保存在当前页面内存，不写入浏览器存储。

## 当前能力

支持新签口径问答、单季度金额、相邻季度环比。模型直接生成SQL，门禁按AST严格限定单表聚合、字段、业务过滤、授权地区、版本和参数。没有使用正则将自然语言编译成SQL。

新签表名、字段和规则是教学示例。其他指标、JOIN、CTE、同比、趋势、排名、多任务、周报不在本版执行能力内；必须扩展门禁和结果契约后才能开放，不能仅在提示词增加要求。

## 交付状态

只编写工程与说明，未运行依赖安装、模型下载、离线索引、数据库脚本、服务或测试。MySQL、Milvus、BGE模型和大模型API接口兼容需要实际环境验收。
