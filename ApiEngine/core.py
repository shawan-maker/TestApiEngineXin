import copy
from typing import Optional

from ApiEngine import log
from ApiEngine.infra import global_func
from ApiEngine.infra.exceptions import PreconditionChainError
from ApiEngine.infra.test_result import TestResult
from ApiEngine.infra.db_client import DBClient
from ApiEngine.infra.suite_store import RunRegistry, RunStore
from ApiEngine.engine.base_case import BaseCase


class TestRunner:
    def __init__(self, env_data, run_id=None):
        """
        :param env_data: 执行测试时的环境数据
        :param run_id: 套件运行ID（传入时启用套件级变量共享）
        """
        # 深拷贝环境数据，避免修改调用方原始数据
        self.env_data = copy.deepcopy(env_data)
        # debug_updates 保持原引用，变更对上层可见（仅无 run_id 的退化路径使用）
        if "debug_updates" in env_data:
            self.env_data["debug_updates"] = env_data["debug_updates"]
        self.result = []
        self._db = DBClient()
        self._shared_env = {}  # 实例级共享环境
        self._run_id = run_id
        self._suite_store: Optional[RunStore] = RunRegistry.get(run_id) if run_id else None

    def execute_cases(self, testcases):
        """执行测试用例的方法"""
        # 根据数据库的配置初始化数据库的连接
        db_config = self.env_data.pop("db", None)
        if db_config:
            self._db.init_connect(db_config)

        # 统一初始化共享环境
        self._shared_env.clear()
        self._shared_env.update(self.env_data)

        # 如果有 run_id，将 _shared_env["envs"] 和 debug_updates 指向套件级存储
        # 这样所有变量读写（包括 Replacer、用户脚本、前置用例提取）自动走 _suite_stores
        if self._suite_store:
            self._shared_env["envs"] = self._suite_store.envs
            self._shared_env["debug_updates"] = self._suite_store.debug_updates

        self._load_global_func()

        # 判断测试数据参数的类型
        if isinstance(testcases, dict):
            cases = testcases.get("cases")
            if cases:
                log.info_log("执行测试套件：", testcases["name"])
                test_result = TestResult(all=len(testcases["cases"]), name=testcases["name"])
                for case in testcases["cases"]:
                    log.info_log(case)
                    self.perform_case(case, test_result)
                res = test_result.get_result_info()
                self.result.append(res)
            else:
                log.info_log("调试单条接口用例：", testcases["title"])
                test_result = TestResult(all=1)
                self.perform_case(testcases, test_result)
                res = test_result.get_result_info()
                self.result = res["cases"][0]
        elif isinstance(testcases, list):
            results = []
            for items in testcases:
                log.info_log("执行测试套件：", items["name"])
                test_result = TestResult(all=len(items["cases"]), name=items["name"])
                for case in items["cases"]:
                    self.perform_case(case, test_result)
                res = test_result.get_result_info()
                results.append(res)
            total_all = 0
            total_success = 0
            total_fail = 0
            total_error = 0
            for scence_result in results:
                total_all += scence_result["all"]
                total_success += scence_result["success"]
                total_fail += scence_result["fail"]
                total_error += scence_result["error"]
            self.result = {
                "results": results,
                "all": total_all,
                "success": total_success,
                "fail": total_fail,
                "error": total_error
            }
        else:
            log.error_log("测试数据格式错误")

        # 断开数据库连接
        if db_config:
            self._db.close_db_connect()
        return self.result

    def perform_case(self, case, test_result):
        """执行单条用例"""
        # 每次创建新的 BaseCase 实例，传入共享环境引用
        c = BaseCase(shared_env=self._shared_env)
        c._db = self._db
        try:
            c.perform(case)
        except PreconditionChainError:
            test_result.add_fail(c)
        except AssertionError:
            test_result.add_fail(c)
        except Exception as e:
            test_result.add_error(c, e)
        else:
            test_result.add_success(c)

    def _load_global_func(self):
        """安全加载用户自定义函数，避免跨执行污染"""
        _gf = self.env_data.get("global_func")
        if not (_gf and isinstance(_gf, str)):
            return
        # 只保留 __name__ 等双下划线内置属性
        builtins = {k: v for k, v in global_func.__dict__.items() if k.startswith('__')}
        global_func.__dict__.clear()
        global_func.__dict__.update(builtins)
        exec(_gf, global_func.__dict__)

    def get_env_snapshot(self) -> dict:
        """获取执行后的环境变量快照（供上层平台读取）

        返回包含 envs、debug_updates 的字典，
        用于上层平台同步临时变量和持久化全局变量变更。

        debug_updates 中的约定：
        - value 非 None → 新增/更新全局变量
        - value 为 None → 删除全局变量
        """
        return {
            "envs": copy.deepcopy(dict(self._shared_env.get("envs") or {})),
            "debug_updates": copy.deepcopy(self._shared_env.get("debug_updates") or {}),
        }

    # ==================== 套件级共享变量：生命周期管理 ====================

    @classmethod
    def register_run(cls, run_id: str, initial_envs: dict) -> None:
        """套件开始前注册共享存储。

        :param run_id: 唯一运行标识（建议格式: suite-{id}-{run_id}-{timestamp}）
        :param initial_envs: 初始环境变量（用户配置的基线值，含 DB 全局变量）
        """
        RunRegistry.register(run_id, initial_envs)

    @classmethod
    def unregister_run(cls, run_id: str) -> None:
        """套件结束后清理共享存储。务必在 finally 中调用。"""
        RunRegistry.unregister(run_id)

    @classmethod
    def get_debug_updates(cls, run_id: str) -> dict:
        """获取需要持久化到 DB 的全局变量变更队列。

        返回 dict 副本：
        - value 非 None → upsert
        - value 为 None → delete
        """
        store = RunRegistry.get(run_id)
        if not store:
            return {}
        with store.lock:
            return dict(store.debug_updates)

    @classmethod
    def clear_debug_updates(cls, run_id: str) -> None:
        """重置变更队列（平台写 DB 后调用，避免重复写入）。"""
        store = RunRegistry.get(run_id)
        if store:
            with store.lock:
                store.debug_updates.clear()

    @classmethod
    def get_run_globals(cls, run_id: str) -> dict:
        """获取当前套件累积的全部环境变量（含初始基线 + 运行时设置）。"""
        store = RunRegistry.get(run_id)
        if not store:
            return {}
        with store.lock:
            return dict(store.envs)

    @classmethod
    def cleanup_stale_runs(cls, max_age_seconds: float = 3600) -> None:
        """清理超时的残留 store（防止异常中断导致内存泄漏）。"""
        RunRegistry.cleanup_stale(max_age_seconds)


if __name__ == '__main__':
    import os

    # 获取测试辅助文件的绝对路径
    _test_dir = os.path.join(os.path.dirname(__file__), '..', 'tests')
    _setup = open(os.path.join(_test_dir, 'setup_scripts.txt'), 'r', encoding='utf-8').read()
    _teardown = open(os.path.join(_test_dir, 'teardown_scripts.txt'), 'r', encoding='utf-8').read()
    _tools = open(os.path.join(_test_dir, 'Tools.py'), 'r', encoding='utf-8').read()

    test_case = {
        "title": "登录成功",
        "interface": {
            "url": "/member/public/login",
            "method": "post"
        },
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded"
        },
        "request": {
            "data": {
                "keywords": "13012341231",
                "password": "test123"
            }
        },
        "setup_script": _setup,
        "teardown_script": "",
        "extract": [
            {"var_name": "status", "extract_expr": "$.status"},
            {"var_name": "description", "extract_expr": "$.description"}
        ],
        "assertions": [
            {"type": "相等", "field": "$.status", "expected": 200},
            {"type": "相等", "field": "$.description", "expected": "登录成功"}
        ]
    }

    test_case2 = {
        "title": "验证是否登录成功",
        "interface": {
            "url": "/member/public/islogin",
            "method": "post"
        },
        "headers": {},
        "request": {
            "params": {
                "m": "Home",
                "c": "User",
                "a": "do_login",
                "t": "${status}"
            },
        },
        "preconditions": [
            {
                "title": "P2P登录成功",
                "interface": {
                    "url": "/member/public/login",
                    "method": "post"
                },
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                "request": {
                    "data": {
                        "keywords": "13012341231",
                        "password": "test123",
                        "description": "${description3}"
                    }
                },
                "setup_script": _setup,
                "teardown_script": "",
                "preconditions": [
                    {
                        "title": "验证当前用户没有登录",
                        "interface": {
                            "url": "/member/public/islogin",
                            "method": "post"
                        },
                        "headers": {},
                        "request": {},
                        "setup_script": _setup,
                        "teardown_script": "",
                        "extract": [
                            {"var_name": "status3", "extract_expr": "$.status"},
                            {"var_name": "description3", "extract_expr": "$.description"}
                        ],
                        "assertions": [
                            {"type": "相等", "field": "$.status", "expected": 200},
                            {"type": "相等", "field": "$.description", "expected": "您未登陆！"}
                        ]
                    }
                ],
                "extract": [
                    {"var_name": "status", "extract_expr": "$.status"},
                    {"var_name": "description", "extract_expr": "$.description"}
                ],
                "assertions": [
                    {"type": "相等", "field": "$.status", "expected": 200},
                    {"type": "相等", "field": "$.description", "expected": "登录成功"}
                ]
            }
        ],
        "setup_script": _setup,
        "teardown_script": "",
        "extract": [
            {"var_name": "status2", "extract_expr": "$.status"},
            {"var_name": "description2", "extract_expr": "$.description"}
        ],
        "assertions": [
            {"type": "相等", "field": "$.status", "expected": "${status3}"},
            {"type": "相等", "field": "$.description", "expected": "OK"}
        ]
    }

    test_suite = {
        "name": "测试套件1",
        "cases": [
            {
                "title": "登录接口",
                "interface": {
                    "url": "/member/public/login",
                    "method": "post"
                },
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Token": "${token}"
                },
                "request": {
                    "params": {},
                    "data": {"keywords": "13012349900", "password": "test123",
                             "user2": "${username}", "pwd2": "${password}",
                             "mobile": "${mobile}"},
                    "json": {"keywords": "13012349900", "password": "test123",
                             "user2": "${username}", "pwd2": "${password}",
                             "mobile": "${mobile}"}
                },
                "setup_script": _setup,
                "teardown_script": _teardown
            },
            {
                "title": "登录接口2",
                "interface": {
                    "url": "/member/public/login",
                    "method": "post"
                },
                "headers": {
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Token": "${token}"
                },
                "request": {
                    "params": {},
                    "data": {"keywords": "13012349900", "password": "test123",
                             "user2": "${username}", "pwd2": "${password}",
                             "mobile": "${mobile}"},
                    "json": {"keywords": "13012349900", "password": "test123",
                             "user2": "${username}", "pwd2": "${password}",
                             "mobile": "${mobile}"}
                },
                "setup_script": _setup,
                "teardown_script": ""
            }
        ]
    }

    test_suites = [
        {
            "name": "测试套件1",
            "cases": [
                {
                    "title": "登录接口",
                    "interface": {
                        "url": "/member/public/login",
                        "method": "post"
                    },
                    "headers": {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Token": "${token}"
                    },
                    "request": {
                        "params": {},
                        "data": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"}
                    },
                    "setup_script": _setup,
                    "teardown_script": _teardown
                },
                {
                    "title": "登录接口2",
                    "interface": {
                        "url": "/member/public/login",
                        "method": "post"
                    },
                    "headers": {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Token": "${token}"
                    },
                    "request": {
                        "params": {},
                        "data": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"}
                    },
                    "setup_script": _setup,
                    "teardown_script": ""
                }
            ]
        },
        {
            "name": "测试套件2",
            "cases": [
                {
                    "title": "登录接口3",
                    "interface": {
                        "url": "/member/public/login",
                        "method": "post"
                    },
                    "headers": {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Token": "${token}"
                    },
                    "request": {
                        "params": {},
                        "data": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"}
                    },
                    "setup_script": _setup,
                    "teardown_script": _teardown
                },
                {
                    "title": "登录接口4",
                    "interface": {
                        "url": "/member/public/login",
                        "method": "post"
                    },
                    "headers": {
                        "Content-Type": "application/x-www-form-urlencoded",
                        "Token": "${token}"
                    },
                    "request": {
                        "params": {},
                        "data": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123",
                                 "user2": "${username}", "pwd2": "${password}",
                                 "mobile": "${mobile}"}
                    },
                    "setup_script": _setup,
                    "teardown_script": ""
                }
            ]
        }
    ]

    # 全局环境数据
    test_env_data = {
        "base_url": "http://121.43.169.97:8081",
        "headers": {
            "Content-Type": "application/json"
        },
        "envs": {
            "username": "rand_13012349900",
            "password": "rand_test123",
            "token": "12345678"
        },
        "global_func": _tools,
        "db": [
            {
                "name": "P2P",
                "type": "mysql",
                "config": {
                    "host": "121.43.169.97",
                    "port": 3306,
                    "user": "student",
                    "password": "P2P_student_2023"
                }
            }
        ]
    }

    runner = TestRunner(test_env_data)
    result = runner.execute_cases(test_case2)
    log.info_log("测试结果：", result)
