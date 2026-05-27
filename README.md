# api_engine_xin

轻量级 API 自动化测试执行引擎，支持单用例 / 单套件 / 多套件组织形式，环境变量与函数注入、前后置 Python 脚本、JSONPath 提取与断言、多级前置接口、MySQL/SQL Server 数据库访问。

## 目录

- [项目概述](#项目概述)
- [安装](#安装)
- [包结构](#包结构)
- [快速开始](#快速开始)
- [TestRunner API](#testrunner-api)
- [test_env_data 环境配置](#test_env_data-环境配置)
- [用例结构 case_payload](#用例结构-case_payload)
- [变量替换与全局函数](#变量替换与全局函数)
- [前后置脚本](#前后置脚本)
- [前置接口 preconditions](#前置接口-preconditions)
- [数据提取 extract](#数据提取-extract)
- [断言 assertions](#断言-assertions)
- [文件上传 files](#文件上传-files)
- [数据库客户端](#数据库客户端)
- [BaseCase 扩展点](#basecase-扩展点)
- [日志与执行结果](#日志与执行结果)
- [本地测试入口](#本地测试入口)
- [与 AITestPlatform 集成](#与-aitestplatform-集成)
- [依赖与版本](#依赖与版本)
- [已知限制](#已知限制)
- [License](#license)

---

## 项目概述

`api_engine_xin`（包目录名 `ApiEngine`）是接口测试用例的**执行引擎**，不负责用例管理或调度。核心流程：

1. 加载 `test_env_data`（基础 URL、请求头、环境变量、工具函数、DB 配置）
2. 按用例定义发送 HTTP 请求（`requests.Session`）
3. 执行 extract / assertions / 前后置脚本
4. 汇总 `TestResult` 并返回结构化结果

**正确导入方式**：

```python
from ApiEngine.core import TestRunner
```

> 旧版 README 中的 `from api-engine-xin import TestRunner` 与 `TestRunner(test_suites, test_env_data).execute_cases()` **已过时**，请勿使用。

---

## 安装

### 开发安装（推荐）

与 AITestPlatform 联调时，在平台 venv 中执行：

```bash
cd D:\PyProject\TestApiEngineXin
pip install -e .
```

或在 AITestPlatform 项目内：

```bash
D:\PyProject\AITestPlatform\venv\Scripts\python.exe -m pip install -e D:\PyProject\TestApiEngineXin
```

### PyPI 安装

```bash
pip install api_engine_xin
```

当前版本：`0.0.16`（见 `setup.py`）。

---

## 包结构

```
TestApiEngineXin/
├── ApiEngine/
│   ├── __init__.py      # 导出全局 log (CaseLogHandler)
│   ├── core.py          # TestRunner 入口
│   ├── BaseCase.py      # 用例执行、变量替换、断言、脚本钩子
│   ├── caseLog.py       # 日志与 PreconditionChainError
│   ├── dbClient.py      # MySQL / SQL Server 客户端
│   ├── testResult.py    # 结果汇总
│   └── global_func.py   # 空模块，运行时 exec 注入用户函数
├── tests/
│   ├── runTest.py       # 旧版 BaseCase 直连示例（字段名已过时）
│   ├── Tools.py         # 示例工具函数（faker/rsa 等）
│   ├── setup_scripts.txt
│   └── teardown_scripts.txt
├── setup.py
└── README.md
```

---

## 快速开始

```python
from ApiEngine.core import TestRunner

test_env_data = {
    "base_url": "http://121.43.169.97:8081",
    "headers": {"Content-Type": "application/json"},
    "envs": {
        "username": "13012349900",
        "password": "test123",
        "token": "12345678",
    },
    "global_func": "",  # 或读取 tests/Tools.py 源码字符串
}

test_case = {
    "title": "登录成功",
    "interface": {"url": "/member/public/login", "method": "post"},
    "headers": {"Content-Type": "application/x-www-form-urlencoded"},
    "request": {
        "data": {"keywords": "13012341231", "password": "test123"},
    },
    "setup_script": "",
    "teardown_script": "",
    "extract": [
        {"var_name": "status", "extract_expr": "$.status"},
        {"var_name": "description", "extract_expr": "$.description"},
    ],
    "assertions": [
        {"type": "相等", "field": "$.status", "expected": 200},
        {"type": "相等", "field": "$.description", "expected": "登录成功"},
    ],
}

runner = TestRunner(test_env_data)
result = runner.execute_cases(test_case)
print(result["status"])  # success | fail | error
```

> **注意**：`TestRunner.__init__` 仅接收 `env_data`；用例通过 `execute_cases(testcases)` 传入。
>
> **注意**：`execute_cases` 会 `pop("db")` 修改传入的 `env_data`，调用方应使用 `copy.deepcopy`（AITestPlatform 已如此处理）。

---

## TestRunner API

### 构造

```python
runner = TestRunner(env_data: dict)
```

### 执行

```python
result = runner.execute_cases(testcases)
```

`testcases` 支持三种形态：

| 形态 | 结构 | 返回值 |
|------|------|--------|
| **单条用例** | `dict`，含 `title`，**不含** `cases` | 单条用例结果 `dict`（`status`、`log_data` 等） |
| **单套件** | `dict`，含 `name` + `cases: [...]` | `list`，元素为套件汇总 `dict` |
| **多套件** | `list`，每项为 `{name, cases}` | `dict`：`{results, all, success, fail, error}` |

### 示例：单套件

```python
test_suite = {
    "name": "测试套件1",
    "cases": [
        {
            "title": "登录接口",
            "interface": {"url": "/member/public/login", "method": "post"},
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Token": "${token}",
            },
            "request": {
                "params": {},
                "data": {
                    "keywords": "13012349900",
                    "password": "test123",
                    "mobile": "${mobile}",
                },
            },
            "setup_script": "",
            "teardown_script": "",
        },
    ],
}
result = runner.execute_cases(test_suite)  # -> list[dict]
```

### 示例：多套件

```python
test_suites = [
    {"name": "测试套件1", "cases": [...]},
    {"name": "测试套件2", "cases": [...]},
]
result = runner.execute_cases(test_suites)
# result["all"], result["success"], result["fail"], result["error"]
```

### 内部行为

- 每个 `TestRunner` 实例持有独立 `DBClient`（`self._db`），支持多线程并发
- 执行前：`ENV.clear()` 并 `ENV.update(env_data)`，再 `exec(global_func)` 注入工具函数
- 异常映射：`AssertionError` / `PreconditionChainError` → fail；其他 `Exception` → error

---

## test_env_data 环境配置

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `base_url` | `str` | 推荐 | 相对路径 URL 的前缀 |
| `headers` | `dict` | 否 | 全局默认请求头，与用例 headers 合并（用例覆盖） |
| `envs` | `dict` | 否 | 环境变量，`${key}` 占位替换 |
| `global_func` | `str` | 否 | Python 源码字符串，`exec` 加载到 `ApiEngine.global_func` |
| `db` | `dict` \| `list` | 否 | 数据库配置，执行时会被 `pop` 出 env_data |
| `debug_updates` | `dict` | 否 | 脚本中 `save_global_variable` 写入的变更（平台调试用） |

### 完整示例（来自 `core.py` `__main__`）

```python
test_env_data = {
    "base_url": "http://121.43.169.97:8081",
    "headers": {"Content-Type": "application/json"},
    "envs": {
        "username": "rand_13012349900",
        "password": "rand_test123",
        "token": "12345678",
    },
    "global_func": open("tests/Tools.py", encoding="utf-8").read(),
    "db": [
        {
            "name": "P2P",
            "type": "mysql",
            "config": {
                "host": "121.43.169.97",
                "port": 3306,
                "user": "student",
                "password": "P2P_student_2023",
            },
        }
    ],
}
```

### db 配置 schema

```python
{
    "name": "P2P",           # 连接别名，脚本中 db.P2P 访问
    "type": "mysql",         # mysql | sqlserver
    "config": {              # 传给 pymysql / pymssql.connect
        "host": "...",
        "port": 3306,
        "user": "...",
        "password": "...",
    },
}
```

单条 DB 可传 `dict` 而非 `list`。

---

## 用例结构 case_payload

与 AITestPlatform `APIruncaseModel` / `api_test_case.case_payload` 对齐：

```python
{
    "title": "用例名称",                    # 必填
    "interface": {
        "url": "/member/public/login",      # 相对或绝对 URL
        "method": "post",                 # requests 方法名（小写）
    },
    "headers": {"Content-Type": "..."},   # 与全局 headers 合并
    "request": {
        "params": {},                     # query string
        "data": {},                       # form-urlencoded / multipart
        "json": {},                       # application/json body
        "files": {},                      # multipart 文件（见下文）
    },
    "preconditions": [],                  # 嵌套前置用例列表（结构同本对象）
    "setup_script": "",                   # 前置 Python 脚本字符串
    "teardown_script": "",                # 后置 Python 脚本字符串
    "extract": [                          # JSONPath 提取
        {"var_name": "status", "extract_expr": "$.status"},
    ],
    "assertions": [                       # 断言列表
        {"type": "相等", "field": "$.status", "expected": 200},
    ],
}
```

### 请求体选择规则

由合并后的 `Content-Type` 决定：

- 含 `application/json` → 发送 `request.json`
- 含 `application/x-www-form-urlencoded` 或 `multipart/form-data` → 发送 `request.data`
- 含 `multipart/form-data` → 额外处理 `request.files`

### URL 规则

- `interface.url` 以 `http` 开头 → 原样使用
- 否则 → `base_url + url`
- 默认 `allow_redirects=False`

---

## 变量替换与全局函数

### `${var}` 语法

- 替换顺序：`test.env`（用例临时变量）→ `ENV["envs"]`（全局环境变量）→ 将 key 当作函数调用表达式
- 支持 `${gen_random_num(2)}` 等形式；也支持 env 值为 `random_mobile()` 字符串
- 最多循环 100 次，防止循环引用
- 替换后尝试 `eval` 还原 Python 类型

### global_func

`test_env_data["global_func"]` 为 Python 源码，执行时：

```python
exec(ENV.get("global_func"), global_func.__dict__)
```

脚本与 `${}` 中可调用 `global_func.random_mobile()` 等（见 `tests/Tools.py`）。

---

## 前后置脚本

在 `setup_script` / `teardown_script` 中可使用的对象（`exec` 作用域）：

| 名称 | 说明 |
|------|------|
| `test` | 当前 `BaseCase` 实例 |
| `global_var` | `ENV["envs"]` 引用 |
| `print` | 重定向到 `test.print_log` |
| `response` | **仅 teardown**：HTTP 响应对象 |
| `ENV` | 模块级环境 dict（含 base_url、envs 等） |
| `global_func` | 已注入的工具函数模块 |
| `db` | `BaseCase` 模块级 `DBClient()`（见[已知限制](#已知限制)） |

### setup 示例（`tests/setup_scripts.txt`）

```python
print('前置脚本')
a = global_func.random_mobile()
test.save_global_variable("mobile", a)
test.save_env_variable("mobile", a * 2)
print(db.P2P.execute_sql("SELECT * FROM czbk_member.mb_member;"))
```

### teardown 示例（`tests/teardown_scripts.txt`）

```python
res = response.json()
value = test.json_extract(res, "$.description")
test.save_global_variable("result", value)
test.assertion("相等", "登录成功", value)
```

---

## 前置接口 preconditions

`preconditions` 为与主用例相同结构的列表，支持**无限嵌套**（深度优先）：

```python
"preconditions": [
    {
        "title": "P2P登录成功",
        "interface": {"url": "/member/public/login", "method": "post"},
        "headers": {"Content-Type": "application/x-www-form-urlencoded"},
        "request": {"data": {"keywords": "...", "password": "..."}},
        "preconditions": [ /* 子前置 */ ],
        "extract": [...],
        "assertions": [...],
        "setup_script": "",
        "teardown_script": "",
    }
]
```

行为要点：

- 默认 **continue** 模式：单步异常记录日志，继续后续前置
- 前置中的 **AssertionError** 仅打日志，**不**计入 `_precondition_errors`
- 主用例若 `_precondition_errors` 非空，最终仍判为 fail
- `failure_mode="stop"` 与 `on_failure` 在代码中**未完全接通**（相关读取行已注释）

---

## 数据提取 extract

```python
"extract": [
    {"var_name": "status", "extract_expr": "$.status"},
]
```

- 使用 `jsonpath-ng`（`from jsonpath import jsonpath`）
- 提取第一个匹配值；无匹配则为 `""`
- 写入 `test.env` 并同步到 `ENV["envs"]`，供后续 `${status}` 使用

脚本中也可手动提取：

```python
value = test.json_extract(resp_json, "$.status")
test.json_extract_list(resp_json, "$.items[*].id")
test.re_extract(text, r"'(\w+?)': '")
test.re_extract_list(text, r"'(\w+?)':")
```

---

## 断言 assertions

```python
"assertions": [
    {"type": "相等", "field": "$.status", "expected": 200},
    {"type": "相等", "field": "status_code", "expected": 200},
    {"type": "相等", "field": "$.description", "expected": "${status}"},
]
```

| 字段 | 说明 |
|------|------|
| `type` | 断言方式（见下表） |
| `field` | JSONPath 表达式，或特殊值 `status_code`（HTTP 状态码） |
| `expected` | 期望值，支持 `${var}` 替换 |

### 支持的 type

| 中文 | 英文别名 |
|------|----------|
| 相等 | equals, eq, == |
| 相等忽略大小写 | equals_ignore_case, eq_ignore_case |
| 不相等 | not_equals, ne, != |
| 包含 | contains, in |
| 不包含 | not_contains, not_in |
| 大于 / 小于 / 大于等于 / 小于等于 | gt, lt, ge, le, greater_than, less_than, ... |
| 正则匹配 | regex_match, regex, match |

- 全部断言执行完后汇总；任一失败抛出聚合 `AssertionError`
- `str` 与 `int`/`float` 期望/实际值会自动尝试类型归一化

---

## 文件上传 files

`request.files` 支持 dict，由 `BaseCase.convert_files` 转换：

```python
# 格式 A：单文件
"files": {
    "avatar": {"path": "/abs/path/to/file.png", "name": "avatar.png"}
}

# 格式 C：单字段多文件
"files": {
    "docs": [
        {"path": "/path/a.pdf", "name": "a.pdf"},
        {"path": "/path/b.pdf"},
    ]
}
```

AITestPlatform 执行前会将 `{"uploaded_file_id": 12}` 解析为 `{"path", "filename"}`（引擎 fallback 用 `basename(path)` 作文件名）。

---

## 数据库客户端

### 配置与生命周期

```python
runner = TestRunner({"db": [...], ...})
runner.execute_cases(case)  # 内部 init_connent / close_db_connent
```

### 脚本中使用

```python
# 模块级 db（见限制）
row = db.P2P.execute_sql("SELECT * FROM table WHERE id=%s", (1,))
rows = db.P2P.execute_all("SELECT * FROM table")
```

### 支持类型

- `mysql` → `pymysql`（DictCursor）
- `sqlserver` → `pymssql`
- Oracle 代码已注释，未启用

---

## BaseCase 扩展点

| 方法 | 作用 |
|------|------|
| `save_env_variable(key, value)` | 用例级临时变量 → `self.env` + `ENV["envs"]` |
| `get_env_variable(key, default=None)` | 读临时变量 |
| `del_evn_variable(key)` | 删除临时变量（注意拼写 env→evn） |
| `save_global_variable(key, value)` | 写全局 envs + `debug_updates` |
| `get_global_variable(key, default=None)` | 读全局变量 |
| `del_global_variable(key)` | 删除全局变量 |
| `json_extract` / `json_extract_list` | JSONPath |
| `re_extract` / `re_extract_list` | 正则提取 |
| `assertion(method, expect, actual)` | 手动断言 |
| `replace_data(data)` | 变量替换 |
| `perform(data)` | 直接执行单条用例（不经 TestRunner 统计） |

继承 `BaseCase` 可覆盖 `perform` 或请求发送逻辑（当前无官方 plugin 机制）。

---

## 日志与执行结果

### 日志

- 全局：`from ApiEngine import log` → `CaseLogHandler`
- 用例级：`test.log_data` → `[(level, msg), ...]`，level 含 `INFO`/`ERROR`/`DEBUG`/`PRINT` 等
- 同时 `print` 到控制台

### 单条用例结果字段（TestResult）

```python
{
    "name": "登录成功",
    "url": "http://...",
    "method": "post",
    "request_headers": {...},
    "request_body": "...",
    "response_code": 200,
    "response_headers": {...},
    "response_body": "...",
    "status": "success",   # success | fail | error
    "log_data": [(...), ...],
    "run_time": "123 ms",
}
```

### 套件汇总

```python
{
    "name": "测试套件1",
    "all": 2,
    "success": 1,
    "fail": 1,
    "error": 0,
    "cases": [ /* 上表结构 */ ],
    "state": "fail",       # 全成功→success；有 fail→fail；否则 error
}
```

---

## 本地测试入口

无 `setup.py` CLI entry point。可手动运行：

```bash
# 推荐：core.py 内置示例
python -m ApiEngine.core

# 旧示例（字段名过时，勿照搬）
python tests/runTest.py
```

`tests/runTest.py` 使用已废弃字段：`request_data`、`setup_scripts`、`tools`（应为 `request`、`setup_script`、`global_func`）。

---

## 与 AITestPlatform 集成

AITestPlatform 通过以下方式调用：

```python
from ApiEngine.core import TestRunner
import copy

env_copy = copy.deepcopy(test_env_data)
runner = TestRunner(env_copy)
result = runner.execute_cases(case_payload)
```

| 组件 | 路径 | 职责 |
|------|------|------|
| `RunnerGateway` | `service/api_test/shared/runner_gateway.py` | 封装 TestRunner + 写 `api_case_run_record` |
| `TestEnvDataAssembler` | `service/test_environment/` | 从 DB 组装 `test_env_data` |
| `SuiteCaseRunner` | `service/test_execution/` | 套件/依赖链执行 |
| `api_runcase_workflow` | `workflow/api_runcase_workflow.py` | AI 生成用例 + 预执行验证 |

平台 `test_env_data` 与引擎字段对齐：`base_url`、`headers`、`envs`、`global_func`、`db`。
用例存于 `api_test_case.case_payload`，结构与本文 [用例结构](#用例结构-case_payload) 一致。
文件引用由平台 `FileResolver` 在执行前解析为绝对路径。

---

## 依赖与版本

| 项 | 值 |
|----|-----|
| Python | `>=3.6`（`setup.py`） |
| 声明依赖 | `pymysql>=1.0.0`, `requests>=2.26.0` |
| 代码中实际使用但未声明 | `jsonpath-ng`（`jsonpath`）、`pymssql`、`faker`、`rsa`（示例 Tools.py） |

安装示例工具函数依赖：

```bash
pip install jsonpath-ng pymssql faker rsa
```

---

## 已知限制

1. **旧 README API 错误**：`TestRunner(test_suites, test_env_data)` 与 `from api-engine-xin import TestRunner` 均不正确。
2. **返回值形态不统一**：单用例返回 `dict`，单套件返回 `list`，多套件返回聚合 `dict`。
3. **`env_data` 会被 mutate**：`db` 键被 `pop`；需 `deepcopy`。
4. **双 DBClient 实例**：`TestRunner._db` 初始化连接，但脚本中的 `db` 是 `BaseCase` 模块级另一实例，**默认未初始化**——`tests/setup_scripts.txt` 中 `db.P2P` 在纯 TestRunner 路径下可能失败。
5. **`setup.py` 依赖不完整**：缺 `jsonpath-ng` 等，裸装后 import 可能失败。
6. **前置断言失败不阻断**：preconditions 内 AssertionError 仅日志，不进入错误链。
7. **`on_failure=stop`**：参数存在但未从用例 JSON 读取（代码已注释）。
8. **无 examples/ 目录**；示例分散在 `core.py` `__main__` 与 `tests/`。
9. **`tests/runTest.py` 字段过时**，与当前引擎不一致。
10. **文件字段名**：引擎读 `name`，平台 FileResolver 写 `filename`（有 basename 兜底）。

---

## License

MIT — Author: Shawn
