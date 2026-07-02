# api_engine_xin

轻量级 API 自动化测试执行引擎。支持 `${var}` 变量替换、JSONPath 提取与断言、前后置 Python 脚本、多级前置接口递归、自定义函数注入、数据库访问、文件上传，以及套件级跨用例变量共享。

## 安装

```bash
pip install api_engine_xin
```

安装可选数据库驱动：

```bash
pip install api_engine_xin[all]    # SQL Server + Oracle + PostgreSQL
pip install api_engine_xin[sqlserver]
```

当前版本：`0.0.28`

---

## 使用场景

### 场景一：调试单条接口

最基本的用法——发送一个请求，提取响应数据，验证结果。

```python
from ApiEngine.core import TestRunner

env = {
    "base_url": "http://api.example.com",
    "headers": {"Content-Type": "application/json"},
    "envs": {"token": "my-token-123"},
}

case = {
    "title": "查询用户信息",
    "interface": {"url": "/api/user/info", "method": "get"},
    "headers": {"Authorization": "Bearer ${token}"},
    "request": {"params": {"user_id": "1001"}},
    "setup_script": "",
    "teardown_script": "",
    "extract": [
        {"var_name": "username", "extract_expr": "$.data.username"},
    ],
    "assertions": [
        {"type": "相等", "field": "$.code", "expected": 200},
        {"type": "相等", "field": "status_code", "expected": 200},
    ],
}

runner = TestRunner(env)
result = runner.execute_cases(case)

print(result["status"])            # "success" | "fail" | "error"
print(result["response_body"])     # 响应体文本
print(result["log_data"])          # 执行日志列表
```

---

### 场景二：批量执行套件

多条用例打包为一个套件执行，返回汇总统计。

```python
suite = {
    "name": "登录模块",
    "cases": [
        {
            "title": "登录",
            "interface": {"url": "/login", "method": "post"},
            "request": {"data": {"user": "admin", "pwd": "123"}},
            "setup_script": "", "teardown_script": "",
            "extract": [{"var_name": "token", "extract_expr": "$.token"}],
            "assertions": [{"type": "相等", "field": "$.code", "expected": 0}],
        },
        {
            "title": "查询个人信息",
            "interface": {"url": "/user/profile", "method": "get"},
            "headers": {"Token": "${token}"},
            "request": {},
            "setup_script": "", "teardown_script": "",
            "extract": [],
            "assertions": [{"type": "相等", "field": "$.code", "expected": 0}],
        },
    ],
}

result = runner.execute_cases(suite)
# result 是 list，每个元素是一个套件的汇总 dict：
# [{"name": "登录模块", "all": 2, "success": 2, "fail": 0, "error": 0, "cases": [...], "state": "success"}]
```

> **注意**：不传 `run_id` 时，套件内各用例的变量**不共享**。如需跨用例传值，请用场景三。

---

### 场景三：跨用例变量共享（套件级执行）

用例 A 提取的 token，用例 B 要能直接用。通过 `run_id` 启用共享。

```python
import time
from ApiEngine.core import TestRunner

env = {
    "base_url": "http://api.example.com",
    "envs": {"base_token": "initial"},
}

# 1. 注册一次运行
run_id = f"suite-1-{time.time()}"
TestRunner.register_run(run_id, initial_envs=env.get("envs", {}))

cases = [
    {
        "title": "登录获取 token",
        "interface": {"url": "/login", "method": "post"},
        "request": {"data": {"user": "admin", "pwd": "123"}},
        "setup_script": "", "teardown_script": "",
        "extract": [{"var_name": "token", "extract_expr": "$.data.token"}],
        "assertions": [],
    },
    {
        "title": "用 token 查询数据",
        "interface": {"url": "/data/list", "method": "get"},
        "headers": {"Authorization": "Bearer ${token}"},   # ← 用到上一条用例提取的 token
        "request": {},
        "setup_script": "", "teardown_script": "",
        "extract": [],
        "assertions": [{"type": "相等", "field": "$.code", "expected": 0}],
    },
]

try:
    for case in cases:
        runner = TestRunner(env, run_id=run_id)
        result = runner.execute_cases(case)
        print(f"{case['title']}: {result['status']}")
finally:
    # 2. 务必清理
    TestRunner.unregister_run(run_id)
```

**配套类方法**：

| 方法 | 用途 |
|------|------|
| `register_run(run_id, initial_envs)` | 注册共享存储（套件开始前） |
| `unregister_run(run_id)` | 清理共享存储（套件结束后，务必在 finally 中调用） |
| `get_debug_updates(run_id)` | 获取 `save_global_variable` 产生的变更队列 |
| `clear_debug_updates(run_id)` | 重置变更队列（持久化到 DB 后调用） |
| `get_run_globals(run_id)` | 获取当前累积的全部环境变量 |
| `cleanup_stale_runs(seconds)` | 兜底清理超时残留（默认 1 小时，按心跳判断不会误杀活跃套件） |

---

### 场景四：前置接口（登录依赖链）

用 `preconditions` 定义前置步骤，引擎自动按深度优先执行。前置提取的变量主用例可直接用 `${var}` 引用。

```python
case = {
    "title": "创建订单",
    "interface": {"url": "/order/create", "method": "post"},
    "headers": {"Token": "${login_token}"},
    "request": {"json": {"product_id": "${product_id}", "qty": 1}},
    "setup_script": "",
    "teardown_script": "",
    "preconditions": [
        {
            "title": "登录",
            "interface": {"url": "/login", "method": "post"},
            "request": {"data": {"user": "admin", "pwd": "123"}},
            "setup_script": "", "teardown_script": "",
            "extract": [{"var_name": "login_token", "extract_expr": "$.data.token"}],
            "assertions": [{"type": "相等", "field": "$.code", "expected": 0}],
            "preconditions": [],
        },
        {
            "title": "查询商品",
            "interface": {"url": "/product/first", "method": "get"},
            "headers": {"Token": "${login_token}"},
            "request": {},
            "setup_script": "", "teardown_script": "",
            "extract": [{"var_name": "product_id", "extract_expr": "$.data.id"}],
            "assertions": [],
            "preconditions": [],
        },
    ],
    "extract": [],
    "assertions": [{"type": "相等", "field": "$.code", "expected": 0}],
}

runner = TestRunner(env)
result = runner.execute_cases(case)
# result["precondition_results"] 包含每个前置步骤的独立结果
```

前置支持无限嵌套（子前置的 `preconditions` 字段）。前置步骤与主用例**共享 HTTP Session**（Cookie 自动传递）。

---

### 场景五：自定义函数

通过 `global_func` 注入 Python 函数，在变量替换和脚本中调用。

```python
tools_code = """
import random

def random_phone():
    return "138" + str(random.randint(10000000, 99999999))

def timestamp():
    import time
    return str(int(time.time()))
"""

env = {
    "base_url": "http://api.example.com",
    "envs": {
        "phone": "random_phone()",      # ← 字符串形式的函数调用
    },
    "global_func": tools_code,
}

case = {
    "title": "注册用户",
    "interface": {"url": "/register", "method": "post"},
    "request": {
        "json": {
            "mobile": "${phone}",              # → 调用 random_phone()
            "ts": "${timestamp()}",             # → 调用 timestamp()
        }
    },
    "setup_script": "", "teardown_script": "",
    "extract": [],
    "assertions": [],
}
```

**替换优先级**：临时变量（extract 提取的）→ 环境变量（envs）→ 函数调用。

---

### 场景六：前后置脚本

`setup_script` 在请求前执行，`teardown_script` 在请求后执行（可访问 `response`）。

```python
case = {
    "title": "下单并验证",
    "interface": {"url": "/order/create", "method": "post"},
    "request": {"json": {"product": "A001"}},
    "setup_script": """
# 前置：生成随机备注
import random
note = "order_" + str(random.randint(1000, 9999))
test.save_env_variable("order_note", note)
""",
    "teardown_script": """
# 后置：从响应提取并做额外校验
body = response.json()
order_id = test.json_extract(body, "$.data.order_id")
test.save_global_variable("last_order_id", order_id)
test.assertion("相等", True, order_id is not None)
""",
    "extract": [],
    "assertions": [{"type": "相等", "field": "$.code", "expected": 0}],
}
```

**脚本中可用对象**：

| 名称 | 说明 |
|------|------|
| `test` | BaseCase 实例，可调用 `save_env_variable`、`save_global_variable`、`json_extract`、`assertion` 等 |
| `response` | HTTP 响应对象（仅 teardown） |
| `ENV` | 环境 dict（含 `base_url`、`envs` 等） |
| `global_var` | `envs` 的直接引用 |
| `db` | 数据库客户端（见场景七） |
| `print` | 输出到执行日志 |

---

### 场景七：数据库操作

配置 DB 连接后，在脚本中通过别名直接查询。

```python
env = {
    "base_url": "http://api.example.com",
    "envs": {},
    "db": [
        {
            "name": "main_db",
            "type": "mysql",           # mysql | sqlserver | oracle | postgresql
            "config": {
                "host": "127.0.0.1",
                "port": 3306,
                "user": "root",
                "password": "123456",
                "database": "test_db",
            },
        }
    ],
}

case = {
    "title": "验证数据库记录",
    "interface": {"url": "/user/create", "method": "post"},
    "request": {"json": {"name": "test_user"}},
    "setup_script": "",
    "teardown_script": """
# 后置脚本查 DB 验证
row = db.main_db.execute_sql("SELECT * FROM users WHERE name=%s", ("test_user",))
print(f"DB 查询结果: {row}")
test.assertion("相等", "test_user", row["name"])
""",
    "extract": [],
    "assertions": [],
}
```

**API**：
- `db.{name}.execute_sql(sql, params)` → 返回单行（dict）
- `db.{name}.execute_all(sql, params)` → 返回所有行（list[dict]）

---

### 场景八：文件上传

```python
case = {
    "title": "上传头像",
    "interface": {"url": "/upload/avatar", "method": "post"},
    "headers": {},
    "request": {
        "data": {"user_id": "1001"},
        "files": {
            "avatar": {"path": "/tmp/photo.png", "name": "photo.png"}
        },
    },
    "setup_script": "", "teardown_script": "",
    "extract": [],
    "assertions": [{"type": "相等", "field": "$.code", "expected": 0}],
}
```

支持三种格式：

```python
# 单文件（路径 dict）
"files": {"field": {"path": "/abs/path.png", "name": "photo.png"}}

# 单文件（requests 原生元组）
"files": {"field": ("photo.png", open("/abs/path.png", "rb"))}

# 多文件
"files": {"field": [{"path": "/a.pdf"}, {"path": "/b.pdf"}]}
```

---

## 环境配置 test_env_data

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `base_url` | `str` | 推荐 | 相对 URL 的前缀 |
| `headers` | `dict` | 否 | 全局默认请求头（用例 headers 会覆盖同名字段） |
| `envs` | `dict` | 否 | 环境变量，支持 `${key}` 替换 |
| `global_func` | `str` | 否 | Python 源码，注入自定义函数 |
| `db` | `dict` \| `list` | 否 | 数据库连接配置 |

---

## 用例结构 case_payload

```python
{
    "title": "用例名称",
    "interface": {
        "url": "/api/path",     # 相对路径自动拼接 base_url；绝对 URL 原样使用
        "method": "post",       # get | post | put | delete | patch
    },
    "headers": {},              # 与全局 headers 合并
    "request": {
        "params": {},           # query string
        "data": {},             # form body
        "json": {},             # json body
        "files": {},            # 文件上传
    },
    "preconditions": [],        # 前置接口列表
    "setup_script": "",         # 前置脚本
    "teardown_script": "",      # 后置脚本
    "extract": [],              # 数据提取
    "assertions": [],           # 断言
}
```

**请求体选择**：由 Content-Type 决定——`application/json` 用 `json`，`form-urlencoded` / `multipart` 用 `data`。

---

## 变量替换

在 URL、headers、request body、assertions expected 中均可使用 `${var}`：

```python
"headers": {"Authorization": "Bearer ${token}"}
"request": {"json": {"user_id": "${user_id}", "phone": "${random_phone()}"}}
"assertions": [{"type": "相等", "field": "$.name", "expected": "${expected_name}"}]
```

**查找顺序**：extract 提取的临时变量 → envs 环境变量 → 函数调用。

---

## 数据提取

```python
"extract": [
    {"var_name": "token", "extract_expr": "$.data.token"},
    {"var_name": "first_id", "extract_expr": "$.data.list[0].id"},
]
```

提取后自动存入变量，后续用例（共享模式下）或当前用例的断言/脚本中可通过 `${token}` 引用。

---

## 断言

```python
"assertions": [
    {"type": "相等", "field": "$.code", "expected": 200},
    {"type": "相等", "field": "status_code", "expected": 200},
    {"type": "包含", "field": "$.message", "expected": "success"},
    {"type": "大于", "field": "$.data.total", "expected": 0},
]
```

`field` 支持 JSONPath 或特殊值 `status_code`（HTTP 状态码）。`expected` 支持 `${var}`。

| 类型 | 别名 |
|------|------|
| 相等 | equals, eq, == |
| 相等忽略大小写 | equals_ignore_case |
| 不相等 | not_equals, ne, != |
| 包含 / 不包含 | contains / not_contains |
| 大于 / 小于 / 大于等于 / 小于等于 | gt / lt / ge / le |
| 正则匹配 | regex_match, regex |

str 与 int/float 会自动尝试类型归一化（`"200"` == `200`）。

---

## 执行结果

### 单条用例

```python
{
    "status": "success",        # success | fail | error
    "name": "用例标题",
    "url": "http://...",
    "method": "post",
    "status_code": 200,         # HTTP 状态码
    "response_body": "...",
    "response_headers": {...},
    "request_body": "...",
    "request_headers": {...},
    "run_time": "123 ms",
    "log_data": [...],          # 执行日志
    "extract_info": [...],      # 提取结果
    "assert_info": [...],       # 断言结果（含 passed 字段）
    "precondition_results": [...],  # 前置步骤结果
}
```

### 套件

```python
{
    "name": "套件名称",
    "all": 10,
    "success": 8,
    "fail": 1,
    "error": 1,
    "cases": [...],
    "state": "fail",            # 全成功→success；有 fail→fail；否则→error
}
```

---

## 依赖

| 项 | 值 |
|----|-----|
| Python | `>=3.6` |
| 核心 | `requests>=2.26.0`, `pymysql>=1.0.0`, `jsonpath>=0.82` |
| 可选 | `pymssql`（SQL Server）, `oracledb`（Oracle）, `psycopg2-binary`（PostgreSQL） |

---

## License

MIT — Author: Shawn
