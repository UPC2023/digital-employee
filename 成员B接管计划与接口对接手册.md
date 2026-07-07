# 成员B 接管计划与接口对接手册

> **项目名称：** 企业 HR 数字员工  
> **编写角色：** 成员B — 智能体与知识检索（Agent & RAG Core）  
> **交接来源：** 成员C — 后端数据与文档处理  
> **最后更新：** 2026-07-06（动态 provider 切换 & RAG 持久化已落地）  
> **文档定位：** 本文档是成员B接收成员C后端交接、并继续完成 Agent 核心开发的唯一权威手册。全文围绕四大主题：**成员C已完成清单、接口边界（不可混用/易串用）、API Key 配置规范、代码与文档交接步骤**。

---

## 〇、一句话总纲

> ⚠️ **所有对成员C能力的调用，必须从 `src.api` 导入，严禁直接 import `database.py` / `business_logic.py` / `resume_parser.py` / `doc_generator.py` 的内部函数。** `src.api.__all__` 即为白名单。任何绕过 `src.api` 的调用都是接口冲突的源头。

---

## 一、背景与接管范围

| 角色 | 职责 | 现状 |
|------|------|------|
| 成员A | 前端与系统集成（Gradio） | 并行开发中，依赖成员B的 `run_agent` 与成员C的看板接口 |
| **成员B（你）** | 智能体与知识检索（Agent & RAG） | **本文档接收方**，负责封装 Tools、意图路由、RAG 与 `run_agent` |
| 成员C | 后端数据与文档处理 | **已开发完成，准备交接** |

**成员B 后续工作范围（已与团队确认）：**
1. 产出本手册（交接文档）；
2. 将成员C的 `src.api` 函数封装为 LangChain Tools（枚举写死、写操作防护）；
3. 实现 7 类意图路由 + 制度问答 RAG；
4. 实现 `run_agent(user_query, session_id) -> dict` 供成员A接入；
5. 补充**火山方舟（Volcano Engine Ark）API Key 适配改造**（详见第四章，属成员B接管后开发项）。

---

## 二、成员C已完成模块与功能清单

### 2.1 数据库与数据（SQLite）
- 文件：`data/hr_agent.db`（**已含 183 条逻辑自洽模拟数据，可直接使用**）
- 建表脚本：`data/init_db.sql`；种子数据：`data/seed_data.py`
- 五张核心表（外键统一为 `employee_code`）：

| 表名 | 说明 | 模拟数据量 |
|------|------|:--:|
| `employees` | 员工信息（主键 `id`，唯一键工号 `employee_code` = EMP001~EMP030） | 30 |
| `attendance` | 考勤记录（外键 `employee_code`） | 35 |
| `leave_requests` | 请假申请（外键 `employee_code`） | 20 |
| `payroll` | 薪酬明细（外键 `employee_code`，在职各3个月） | 78 |
| `recruitment` | 招聘记录（自增 `id`，**无 employee_code 外键**） | 20 |

### 2.2 统一对外接口 `src/api.py`（24 个函数，白名单见 `__all__`）
> 调用方式：`from src.api import query_employee, submit_leave, ...`

**员工 / 考勤 / 请假 / 招聘（数据库类）**
- `query_employee(employee_code=None, name=None, department=None) -> list[dict]`
- `get_employee_by_code(employee_code) -> dict | None`
- `update_employee(employee_code, **kwargs) -> bool` ⚠️*写操作*
- `get_department_members(department) -> list[dict]`
- `query_attendance(employee_code, start_date=None, end_date=None) -> list[dict]`
- `submit_leave(employee_code, leave_type, start_date, end_date, reason) -> dict` ⚠️*写操作，自动计算天数+扣余额*
- `query_leave_balance(employee_code) -> dict`
- `query_leave_history(employee_code, status=None) -> list[dict]`
- `query_payroll(employee_code, year=None, month=None) -> list[dict]`
- `query_recruitment(position=None, status=None, candidate_name=None) -> list[dict]`
- `insert_recruitment(data: dict) -> int` ⚠️*写操作，入参为 dict，返回自增 id*
- `update_recruitment_status(recruitment_id: int, status, **kwargs) -> bool` ⚠️*写操作，注意用 recruitment 的 `id` 而非 employee_code*

**业务逻辑（计算类）**
- `calculate_tax(gross_income, social_insurance=0, housing_fund=0, special_deduction=0, cumulative_income=None, cumulative_tax_paid=None, month_number=1) -> dict`（累计预扣法）
- `calculate_monthly_tax(gross_income, social_insurance=0, housing_fund=0, special_deduction=0) -> dict`（单月估算）
- `calculate_social_insurance(base_salary, city_rate=None) -> dict`
- `calculate_annual_leave_days(hire_date_str, today_str=None) -> float`
- `calculate_workdays(start_date, end_date) -> int`
- `calculate_salary_summary(payroll_records: list[dict]) -> dict` ⚠️*入参是 `query_payroll` 的返回列表，不是 employee_code*

**简历解析 / 文档生成**
- `parse_resume(file_path) -> dict` ⭐对外唯一入口，返回 `{success, data, error}`
- `batch_parse_resumes(file_paths: list[str]) -> list[dict]`
- `generate_onboarding_doc(employee_code) -> dict`
- `generate_offboarding_doc(employee_code) -> dict`
- `generate_offer_letter(candidate_name, position, department, salary, start_date, contact_person="人事部", contact_phone="010-12345678") -> dict`

**便捷 / 概览**
- `setup_project(sql_file=None) -> dict` ⚠️*会初始化/重建数据库*
- `get_dashboard_summary() -> dict`（供成员A看板）

### 2.3 简历解析 `src/resume_parser.py`
- 文本提取：PDF（pdfplumber 优先，回退 PyPDF2）、Word（python-docx，含表格）
- 结构化抽取：DeepSeek / 火山方舟 LLM + Pydantic `ResumeInfo`（`src/resume_schema.py`）
- 对外入口 `parse_resume(file_path)`；内部 `parse_resume_text(resume_text)` **禁止外部调用**
- **动态 provider 切换**：`get_llm_client(provider=None)` 支持不传参（读 `.env`）或传入 `"deepseek"` / `"ark"` 覆盖；按 provider 分键缓存，避免重复创建连接

### 2.4 文档生成 `src/doc_generator.py`
- 入职材料清单 / 离职交接清单 / 录用通知书（python-docx，支持 `templates/` 占位符 `{{key}}` 渲染，缺模板自动代码生成）
- 输出目录：`output/`

### 2.5 已确认的"已完成"判定
成员C模块已具备：可导入性、查询/写接口齐全、简历解析与文档生成可运行、数据库 183 条数据就绪。**成员B接管无需重写后端，只需在其之上做 Agent 封装。**

---

## 三、需交接接口及边界（⚠️ 严格区分不可混用 / 易串用）

本章是**防接口冲突的核心**，每条均给出"正确用法 / 错误用法 / 风险"。

### 🔴 边界0：唯一入口 — 只能从 `src.api` 调用
- **正确**：`from src.api import query_employee`
- **错误**：`from src.database import query_employee` 或 `from src.resume_parser import parse_resume`
- **风险**：成员C若调整内部实现（如换 ORM、改函数签名），绕过 `src.api` 的代码会直接崩；且 `src.api` 内的 `get_dashboard_summary` 等聚合逻辑不会被执行。
- **规则**：`src.api.__all__` 之外的任何函数都不属于对外契约。

### 🔴 边界1：`calculate_tax` vs `calculate_monthly_tax`（不可混用）
| 函数 | 语义 | 关键参数 | 适用场景 |
|------|------|---------|---------|
| `calculate_tax` | 累计预扣法（精确） | 需 `cumulative_income` / `cumulative_tax_paid` / `month_number` | 算某员工某月**真实**个税（需喂入历史累计） |
| `calculate_monthly_tax` | 单月估算（不累计） | 等价 `month_number=1, 累计=0` | 快速估算、对话中随口问"这个工资要交多少税" |

- **两者返回字段名完全一致**，极易串用导致"看起来对、实际税算错"。
- **Agent 约定**：用户问"某员工X月个税"→ 用 `calculate_tax` 并补全累计参数；用户泛指"月薪1万交多少税"→ 用 `calculate_monthly_tax`。

### 🔴 边界2：`parse_resume` vs `parse_resume_text`（不可混用）
- `parse_resume(file_path)`：**对外唯一入口**，处理文件存在性、文本提取、LLM 抽取，返回标准 `{success, data, error}`。
- `parse_resume_text(resume_text)`：**内部函数**，接收已提取文本；**失败时返回 `{_raw_response, _error}` 非标准结构**，且无文件校验。
- **规则**：成员B / 成员A 只调 `parse_resume`。误用 `parse_resume_text` 会导致返回结构不符合手册约定，下游解析崩溃。

### 🔴 边界3：`calculate_salary_summary` 的入参不是 employee_code
- **正确**：先 `recs = query_payroll(employee_code, ...)`，再 `calculate_salary_summary(recs)`。
- **错误**：`calculate_salary_summary("EMP001")`。
- **风险**：类型不符，函数内 `r.get("gross_pay", 0)` 全部走默认值 0，统计结果恒为 0。

### 🔴 边界4：枚举字符串必须一字不差（易串用高发区）
以下字符串是 `==` 精确匹配，**多一个空格、错一个字都会匹配失败或落空**。在 LangChain Tool 的 docstring 中必须**写死原文**：

| 枚举字段 | 合法取值（原文） |
|---------|----------------|
| `leave_type`（请假类型） | `年假` / `事假` / `病假` / `婚假` / `产假` / `调休` |
| `recruitment.status` | `简历筛选` / `初试` / `复试` / `终试` / `已发Offer` / `已入职` / `已拒绝` |
| `employees.status` | `在职` / `离职` / `试用期` |
| `attendance.status` | `正常` / `迟到` / `早退` / `缺勤` / `请假` |

- **注意"已发Offer"含英文大写的"O"**，不是"已发offer"；"EMP001"工号大小写敏感。

### 🔴 边界5：关联键 `employee_code`（字符串）vs 主键 `id`（int）
- 绝大多数 api 以 `employee_code`（如 `"EMP001"`）为键。
- **唯一例外**：`update_recruitment_status(recruitment_id: int, ...)` 用的是 `recruitment` 表的**自增 `id`（整数）**，不是 employee_code，且 recruitment 表本身**无 employee_code 字段**。
- **风险**：把 `EMP001` 传给 `update_recruitment_status` 会被当成 `id=0` 或报错；把 recruitment 的 `id` 当 employee_code 传给其他函数同样会落空。
- **规则**：操作招聘流程时，先用 `query_recruitment(...)` 取到目标记录的 `id`，再传 `update_recruitment_status(id, ...)`。

### 🔴 边界6：写操作有副作用，Agent 须防误触发
以下函数会**真实改动数据库或生成文件**，Agent 工具描述必须显式标注"有副作用、需用户明确确认后再执行"：
- `submit_leave`（写入请假记录 + 扣减假期余额）
- `update_employee`、`insert_recruitment`、`update_recruitment_status`
- `generate_onboarding_doc` / `generate_offboarding_doc` / `generate_offer_letter`（写 `output/`）

- **建议**：在 Tool 的 `description` 中加入"⚠️ 此操作会写入数据库，请先向用户确认参数无误后再调用"。

### 🔴 边界7：破坏性操作 — 执行前必须备份
- `python data/seed_data.py`：**删除旧库并重新生成** 183 条数据。
- `setup_project()`：会初始化/重建数据库。
- **规则**：本地调试如需重置数据，先 `cp data/hr_agent.db data/hr_agent.db.bak`；**绝不在成员A演示环境随意跑 seed**。

### ✅ 接口边界速查表（成员B 内置校验清单）
| 检查项 | 是否满足 |
|-------|---------|
| 只从 `src.api` 导入 | ☐ |
| 个税按需选用 `calculate_tax` / `calculate_monthly_tax` | ☐ |
| 简历只调 `parse_resume` | ☐ |
| `calculate_salary_summary` 入参为 `query_payroll` 列表 | ☐ |
| 枚举字符串与手册一致 | ☐ |
| 招聘状态更新用 `id` 而非 `employee_code` | ☐ |
| 写操作 Tool 已标注副作用 | ☐ |
| 不随意运行 `seed_data.py` | ☐ |

---

## 四、API Key 配置规范

### 4.1 DeepSeek（已实现，默认通道）
当前 `src/resume_parser.py` 中 `get_llm_client()` 按 provider 分键缓存，默认使用 DeepSeek；`src/agent/agent.py` 中 `_build_llm()` 同样支持双通道（独立实例，可调 temperature）。
- 缓存策略：`_llm_clients[provider]` dict，同一 provider 只创建一次 ChatOpenAI 实例。
- Agent 层 `_build_llm()` 与 `resume_parser` 同源逻辑但独立调用，各自缓存互不干扰。

`.env` 配置项（复制 `.env.example` 后填写）：
```env
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-chat
```
- `DEEPSEEK_BASE_URL` 默认 `https://api.deepseek.com`，一般无需改；
- `DEEPSEEK_MODEL` 默认 `deepseek-chat`，可换 `deepseek-reasoner` 等。

**适用场景**：项目默认 LLM 后端，覆盖简历解析与 Agent 问答。

### 4.2 火山方舟 / Volcano Engine Ark（✅ 已实现，支持动态切换）
`resume_parser.py` 的 `get_llm_client(provider="ark")` 与 `agent.py` 的 `_build_llm(provider="ark")` 均已支持火山方舟。

**.env 配置项：**
```env
LLM_PROVIDER=deepseek            # 默认 deepseek，静态切换改为 ark

# 火山方舟（Volcano Engine Ark）
ARK_API_KEY=your_volcano_ark_key
ARK_BASE_URL=https://ark.cn-beijing.volces.com/api/v3   # OpenAI 兼容 endpoint
ARK_MODEL=ep-xxxxxxxx            # 方舟模型 endpoint id（如豆包 doubao 系列）
```

**三种使用方式（由粗到细）：**
1. **静态切换**：`.env` 中 `LLM_PROVIDER=ark` → 全局走火山方舟（需重启）
2. **代码动态指定**：`run_agent("你好", session_id="s1", provider="ark")` → 单次调用走火山方舟
3. **前端下拉框**：成员A 在 Gradio 加一个 Dropdown（选项 `deepseek` / `ark`），用户选择后传给 `run_agent(..., provider=selected)` — 无需重启、无需改 `.env`

**适用场景（明确区分）：**
- `LLM_PROVIDER=deepseek` 或不传 `provider` → 默认 DeepSeek，正常开发/演示
- `provider="ark"` → ① DeepSeek 配额耗尽或并发受限时降级；② 对比豆包等模型效果时切换
- 注意：火山方舟走 OpenAI 兼容协议（`langchain_openai.ChatOpenAI`），切换零侵入、可一键回退

### 4.3 配置步骤（通用）
```bash
cp .env.example .env          # 然后填入真实 Key
# 切勿把 .env 提交到仓库或发给组员（已配 .gitignore）
```

### 4.4 安全规范
- `.env` 含敏感 Key，**不入库、不私发**（成员C应口头/私信单独交付 Key）。
- 切换 provider 后建议先跑一次 `parse_resume` 冒烟测试，确认客户端初始化无误。

---

## 五、成员B后续开发计划（Agent 层，与C模块解耦）

> 详细代码实现见 `env-volcano` / `parser-provider` / `build-tools` / `build-rag` / `build-agent` 任务。此处仅给出对接契约与设计要点，供成员A与评审理解。

### 5.1 目录结构（新增，不改动C模块）
```
src/agent/
├── __init__.py     # 导出 run_agent
├── tools.py        # 将 src.api 封装为 LangChain Tool（枚举写死、写操作防护）
├── rag.py          # 加载制度文档切块 + 构建 Chroma/FAISS 向量库与检索器
├── router.py       # 7类意图定义与路由
└── agent.py        # 主流程，提供 run_agent 入口
```

### 5.2 Tools 封装规范
- 每个 `src.api` 函数对应一个 `@tool`，docstring 中**写死第四章枚举**与参数说明。
- 写操作 Tool（边界6）描述中标注"⚠️ 有副作用、需用户确认"。
- 入参严格遵循边界3/边界5（如 `calculate_salary_summary` 先查后算、招聘用 `id`）。

### 5.3 意图路由与 RAG
- **7 类意图**：招聘咨询 / 考勤 / 薪酬 / 请假 / 入职 / 离职 / 制度问答。
- 优先用 LLM **Function Calling** 一次性分发到具体 Tool；制度问答走 RAG Retriever（加载《员工手册》《考勤管理制度》《个税计算规则》等，切块后存入 Chroma/FAISS），避免多轮 RouterChain 额外延迟。

### 5.4 与成员A的对接契约（来自《三人分工.md》）
```python
def run_agent(user_query: str, session_id: str, provider: str = None) -> dict:
    # 参数：
    #   user_query: 用户自然语言问题
    #   session_id: 会话标识，用于维护多轮上下文
    #   provider:   "deepseek" | "ark"，可覆盖 .env 配置（供前端 Gradio 下拉框动态切换）
    #               不传则读取 .env 的 LLM_PROVIDER
    # 返回格式固定，便于成员A流式接入 Gradio：
    # {
    #   "response": "大模型回复文本",
    #   "tool_used": "调用了哪个工具（或 'rag' / 'none'）",
    #   "data": 结构化数据(dict|None)
    # }
    ...
```

### 5.5 快速验证（成员B 自测）
```bash
pip install -r requirements.txt     # 安装 B 侧依赖（langchain / chromadb / sentence-transformers 等）
cp .env.example .env                # 填入 DEEPSEEK_API_KEY（必填）和 ARK_API_KEY（可选）
```
```python
from src.agent import run_agent

# 基础测试（走 .env 默认 DeepSeek）
out = run_agent("技术部有哪些员工？", session_id="test-1")
print(out["response"], "| tool:", out["tool_used"])

# 个税估算
out = run_agent("月薪15000大概交多少税？", session_id="test-1")
print(out["response"])

# 制度问答（自动走 RAG 快捷路径，不调工具）
out = run_agent("年假有几天？", session_id="test-1")
print(out["response"], "| tool:", out["tool_used"])  # tool_used = "rag"

# 动态切换火山方舟（需先填 .env 中 ARK_API_KEY）
out = run_agent("帮我查一下技术部有哪些员工", session_id="test-1", provider="ark")
print(out["response"])
```

> 注：
> - `src/agent/` 已落地实现（tools.py / rag.py / router.py / agent.py），均仅通过 `src.api` 调用成员C能力，未直连其内部模块。
> - RAG 向量库在首次使用（制度问答）时自动加载知识文档并持久化到 `data/chroma_db/`，后续重启无需重建。
> - 制度问答意图自动识别 → 走 RAG 检索 + LLM 总结捷径，不经过工具调用链，减少幻觉。
> - 文件处理契约：成员A Gradio 收集到简历路径后，直接调 `from src.api import parse_resume`。

---

## 六、代码与文档交接步骤

> 目标：平滑过渡、接口零冲突。按顺序执行，任一步失败则回退并联系成员C。

**步骤1 — 接收交付物（成员C → 成员B）**
- [ ] 源码全量（含 `src/`、`data/init_db.sql`、`data/seed_data.py`）
- [ ] `data/hr_agent.db`（183 条数据，确认文件存在且非空）
- [ ] 本手册 + 成员C《交接书.md》
- [ ] API Key：**私信单独交付 `.env` 或 Key 明文**，不通过仓库传输

**步骤2 — 环境就绪（成员B 本地）**
```bash
pip install -r requirements.txt
cp .env.example .env          # 填入 Key（见第四章）
```
- [ ] 验证可导入：`python -c "from src.api import *; print('OK')"`

**步骤3 — 冒烟测试（核对接口边界）**
- [ ] 查询类：依次调用 `query_employee` / `query_attendance` / `query_payroll` / `query_recruitment`，核对返回结构与手册一致；
- [ ] 枚举一致性：用边界4的合法枚举值各测一次，确认不落空；
- [ ] 计算类：分别用 `calculate_tax` 与 `calculate_monthly_tax` 验证边界1差异；
- [ ] 解析类：跑一次 `parse_resume(某简历路径)`，确认返回 `{success:true, data:ResumeInfo}`；
- [ ] 确认 `data/hr_agent.db` 可正常读取（无需重新 seed）。

**步骤4 — 签署与冻结**
- [ ] 成员B确认步骤1–3全部通过，与成员C**签署交接确认**；
- [ ] **冻结 `src.api` 接口签名**：后续成员B如需新增导出，只能在 `src/agent/` 内做二次封装，不得改动 `src.api` 白名单与函数签名；如需变更走契约评审。
- [ ] 将 `.env` / `data/hr_agent.db` 确认已在 `.gitignore`（Key 与数据不入库）。

---

## 七、接口冲突规避总清单（交付前自查）

- [ ] 全项目搜索 `from src.database` / `from src.business_logic` / `from src.resume_parser import parse_resume_text` / `from src.doc_generator`，**除 `src/api.py` 内部外应为 0 处**（成员B代码仅 `from src.api import ...`）
- [ ] 所有枚举字符串与第四章表格逐字一致
- [ ] 招聘状态更新统一用 `recruitment.id`，其余用 `employee_code`
- [ ] 写操作 Tool 均标注副作用与确认提示
- [ ] `seed_data.py` / `setup_project` 仅在备份后、明确需要重置时执行
- [ ] 火山方舟改造**仅限** `resume_parser.py` 与 `.env.example`，`DEEPSEEK_*` 默认路径不变（向后兼容）
- [ ] `run_agent` 返回结构严格遵循第五章契约，便于成员A接入

---

## 八、附录 A：最小可用调用示例（成员B 视角）

```python
# 1) 员工查询（边界0：只从 src.api 导入）
from src.api import query_employee, get_employee_by_code
emps = query_employee(department="技术部")          # 按部门查
emp  = get_employee_by_code("EMP001")              # 按工号精确查

# 2) 个税（边界1：区分累计 vs 单月）
from src.api import calculate_tax, calculate_monthly_tax
monthly = calculate_monthly_tax(gross_income=15000)            # 单月估算
precise = calculate_tax(gross_income=15000, cumulative_income=45000,
                        cumulative_tax_paid=198.75, month_number=4)  # 累计精确

# 3) 薪酬汇总（边界3：先查后算）
from src.api import query_payroll, calculate_salary_summary
recs = query_payroll("EMP001", year=2026, month=6)
summary = calculate_salary_summary(recs)

# 4) 简历解析（边界2：只调 parse_resume）
from src.api import parse_resume
res = parse_resume("./data/resumes/张三.pdf")
if res["success"]:
    print(res["data"]["name"], res["data"]["phone"])

# 5) 招聘状态更新（边界5：用 recruitment.id 而非 employee_code）
from src.api import query_recruitment, update_recruitment_status
rec = query_recruitment(candidate_name="李四")[0]
update_recruitment_status(rec["id"], "已发Offer")   # 注意是 id（int）
```

## 附录 B：Key 配置速查

| Provider | 环境变量 | 用途 | 状态 |
|----------|---------|------|------|
| DeepSeek | `DEEPSEEK_API_KEY` / `DEEPSEEK_BASE_URL` / `DEEPSEEK_MODEL` | 默认 LLM（解析+Agent） | ✅ 已实现 |
| 火山方舟 | `LLM_PROVIDER=ark` + `ARK_API_KEY` / `ARK_BASE_URL` / `ARK_MODEL` | 降级 / 模型对比；支持动态 `provider` 参数 | ✅ 已实现 |

---

> 📞 接口疑问请联系成员C（后端原作者）；Agent 封装与路由问题由成员B负责。本文档随 `src/agent/` 开发进度同步更新。
