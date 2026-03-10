### **API AutoTest Runner**

A lightweight and flexible execution engine for API automated testing, supporting multiple test case organization forms, environment variable injection, and custom script extension.

### Core Features

Support three test case organization forms: single case / single scenario (multiple cases) / multiple scenarios (multiple cases)

Dynamic environment variable injection (support custom functions)

Pre/post script extension

Built-in database connection configuration (MySQL)

Clear execution results (success/failure count + logs)

### Installation

```bash
pip install api-engine-xin
```

1、Basic Usage

~~~python
from api-engine-xin import TestRunner

# 执行测试用例
result = TestRunner(test_suites, test_env_data).execute_cases()
print(f"result: success: {result['success']}, fail: {result['failed']}")
print(f"log: {result['logs']}")
~~~

2、Test Case definition：

format  1:  single test case

~~~
test_suites = {
    "title": "Login Success",
    "interface": {
        "url": "/member/public/login",
        "method": "post"
    },
    "headers": {
        "content-Type": "application/json"
    },
    "request": {
        "json": {
            "keywords": "13012349900",
            "password": "test123"
        }
    },
    "setup_script": "",  # setup script（option）
    "teardown_script": ""  # teardown_script（option）
}
~~~

format 2: single test scene（multiple test cases）

~~~
test_suites = {
    "name": "Test Suite 1",
    "cases": [
        {
            "title": "Login Interface",
            "interface": {"url": "/member/public/login", "method": "post"},
            "headers": {
                "Content-Type": "application/x-www-form-urlencoded",
                "Token": "${token}"  # quato envs
            },
            "request": {
                "params": {},
                "data": {"keywords": "13012349900", "password": "test123", "user2": "${username}"},
                "json": {"keywords": "13012349900", "password": "test123", "user2": "${username}"}
            },
            "setup_script": "",
            "teardown_script": ""
        },
        # more cases....
    ]
}
~~~

format  3: multiple test scenes

~~~
test_suites = [
    {
        "name": "Test Suite 1",
        "cases": [
            # case1
        ]
    },
    {
        "name": "Test Suite 2",
        "cases": [
            # case2
        ]
    }
]
~~~



### License

MIT

### Author

Shawn