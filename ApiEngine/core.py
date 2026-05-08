from ApiEngine import global_func,log
from ApiEngine.BaseCase import BaseCase, db, ENV
from ApiEngine.testResult import TestResult


class TestRunner:
    def __init__(self, cases, env_data):
        """
        :param cases: 要执行的测试数据
        :param env_data: 执行测试时的环境数据
        """
        self.cases = cases
        self.env_data = env_data
        self.result = []
        self.c=BaseCase()

    def execute_cases(self):
        """执行测试用例的方法"""
        # 根据数据库的配置初始化数据库的连接
        db.init_connent(self.env_data.pop("db"))
        # 判断测试数据参数的类型
        if isinstance(self.cases, dict):
            cases = self.cases.get("cases")
            if cases:
                log.info_log("执行测试套件：",self.cases["name"])
                # 将全局环境测试加载到ENV中
                ENV.clear()
                ENV.update(self.env_data)
                # 将tools中的函数（用户自定义），通过exec执行（字符串中的python函数），加载到TestTools模块的命名空间中
                exec(ENV.get("global_func"), global_func.__dict__)
                # 创建测试结果的记录器
                test_result = TestResult(all=len(self.cases["cases"]),name=self.cases["name"])
                # 运行测试用例
                for case in self.cases["cases"]:
                    log.info_log(case)
                    self.perform_case(case,test_result)
                # 获取测试结果执行记录器中的结果
                res = test_result.get_result_info()
                self.result.append(res)
            else:
                log.info_log("调试单条接口用例：",self.cases["title"])
                # 将全局环境测试加载到ENV中
                ENV.clear()
                ENV.update(self.env_data)
                # 将tools中的函数（用户自定义），通过exec执行（字符串中的python函数），加载到TestTools模块的命名空间中
                exec(ENV.get("global_func"), global_func.__dict__)
                # 创建测试结果的记录器
                test_result = TestResult(all=1)
                # log.info_log("执行测试用例：",self.cases)
                self.perform_case(self.cases, test_result)
                # 获取测试结果执行记录器中的结果
                res = test_result.get_result_info()
                self.result = res["cases"][0]
        elif isinstance(self.cases, list):
            # 遍历所有测试用例
            results = []
            for items in self.cases:
                log.info_log("执行测试套件：",items["name"])
                # 将全局环境测试加载到ENV中
                ENV.clear()
                ENV.update(self.env_data)
                # 将tools中的函数（用户自定义），通过exec执行（字符串中的python函数），加载到TestTools模块的命名空间中
                exec(ENV.get("global_func"), global_func.__dict__)
                # 新增检测日志
                log.info_log(f"gen_random_num 是否存在：{hasattr(global_func, 'gen_random_num')}")
                log.info_log(f"gen_random_num 是否可调用：{callable(getattr(global_func, 'gen_random_num', None))}")
                log.info_log(f"random_mobile 是否存在：{hasattr(global_func, 'random_mobile')}")
                log.info_log(f"random_mobile 是否可调用：{callable(getattr(global_func, 'random_mobile', None))}")
                # 创建测试结果的记录器
                test_result = TestResult(all=len(items["cases"]),name=items["name"])
                # 运行测试用例
                for case in items["cases"]:
                    self.perform_case(case,test_result)
                # 获取测试结果执行记录器中的结果
                res = test_result.get_result_info()
                results.append(res)
            all = 0
            success = 0
            fail = 0
            error = 0
            for scence_result in results:
                all += scence_result["all"]
                success += scence_result["success"]
                fail += scence_result["fail"]
                error += scence_result["error"]
            self.result = {
                "results": results,
                "all": all,
                "success": success,
                "fail": fail,
                "error": error
            }
        else:
            log.error_log("测试数据格式错误")
        # 断开数据库连接
        db.close_db_connent()
        # 返回用例执行结果
        return self.result

    def perform_case(self, case,test_result):
        # 运行测试用例
        try:
            self.c.perform(case)
        except AssertionError:
            test_result.add_fail(self.c)
        except Exception as e:
            test_result.add_error(self.c,e)
        else:
            test_result.add_success(self.c)


if __name__ == '__main__':
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
           "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
           "teardown_script": "",
        # 数据提取
        "extract": [
            {"var_name":"status","extract_expr":"$.status"},
            {"var_name": "description", "extract_expr": "$.description"}
        ],
    "assertions": [
            {
                "type": "相等",
                "field": "$.status",
                "expected": 200
            },
            {
                "type": "相等",
                "field": "$.description",
                "expected": "登录成功"
            }
        ]
     }
    test_case2 = {
        "title": "验证是否登录成功",
       "interface": {
            "url": "/member/public/islogin",
             "method": "post"
            },
           "headers": {
             # "Content-Type": "application/x-www-form-urlencoded"
         },
         "request": {
             "params": {
                   "m": "Home",
                   "c": "User",
                 "a":"do_login",
                    "t":"${status}"
               },
             # "data": {
             #     "username": "13800000001",
             #     "password": "123456",
             #     "verify_code": "8888"
             # }
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
                    "description":"${description3}"
                }
            },
            "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
            "teardown_script": "",
            "preconditions": [
                {
                    "title": "验证当前用户没有登录",
                    "interface": {
                        "url": "/member/public/islogin",
                        "method": "post"
                    },
                    "headers": {
                        # "Content-Type": "application/x-www-form-urlencoded"
                    },
                    "request": {
                        # "data": {
                        #     "keywords": "13012341231",
                        #     "password": "test123"
                        # }
                    },
                    "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
                    "teardown_script": "",

                    # 数据提取
                    "extract": [
                        {"var_name": "status3", "extract_expr": "$.status"},
                        {"var_name": "description3", "extract_expr": "$.description"}
                    ],
                    "assertions": [
                        {
                            "type": "相等",
                            "field": "$.status",
                            "expected": 200
                        },
                        {
                            "type": "相等",
                            "field": "$.description",
                            "expected": "您未登陆！"
                        }
                    ]
                }
            ],
            # 数据提取
            "extract": [
                {"var_name": "status", "extract_expr": "$.status"},
                {"var_name": "description", "extract_expr": "$.description"}
            ],
            "assertions": [
                {
                    "type": "相等",
                    "field": "$.status",
                    "expected": 200
                },
                {
                    "type": "相等",
                    "field": "$.description",
                    "expected": "登录成功"
                }
            ]
        }
    ],
           "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
           "teardown_script": "",
        # 数据提取
        "extract": [
            {"var_name":"status2","extract_expr":"$.status"},
            {"var_name": "description2", "extract_expr": "$.description"}
        ],
    "assertions": [
            {
                "type": "相等",
                "field": "$.status",
                "expected": 200
            },
            {
                "type": "相等",
                "field": "$.description",
                "expected": "OK"
            }
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
                    "data": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                             "pwd2": "${password}", "mobile": "${mobile}"},
                    "json": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                             "pwd2": "${password}", "mobile": "${mobile}"}
                },
                "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
                "teardown_script": open("..\\tests\\teardown_scripts.txt", "r", encoding="utf-8").read()
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
                    "data": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                             "pwd2": "${password}", "mobile": "${mobile}"},
                    "json": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                             "pwd2": "${password}", "mobile": "${mobile}"}
                },
                "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
                "teardown_script": ""
            }
        ]
    }
    test_suites = [
        {
            "name":"测试套件1",
            "cases":[
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
                        "data": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mob"
                                                        ""
                                                        "ile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mobile": "${mobile}"}
                    },
                    "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
                    "teardown_script": open("..\\tests\\teardown_scripts.txt", "r", encoding="utf-8").read()
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
                        "data": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mobile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mobile": "${mobile}"}
                    },
                    "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
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
                        "data": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mobile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mobile": "${mobile}"}
                    },
                    "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
                    "teardown_script": open("..\\tests\\teardown_scripts.txt", "r", encoding="utf-8").read()
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
                        "data": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mobile": "${mobile}"},
                        "json": {"keywords": "13012349900", "password": "test123", "user2": "${username}",
                                 "pwd2": "${password}", "mobile": "${mobile}"}
                    },
                    "setup_script": open("..\\tests\\setup_scripts.txt", "r", encoding="utf-8").read(),
                    "teardown_script": ""
                }
            ]
        }
    ]
    # 全局环境数据
    test_env_data = {
        "base_url": "http://121.43.169.97:8081",
        # "base_url": "http://127.0.0.1",
        # "base_url": "http://hmshop-test.itheima.net",
        "headers": {
            "Content-Type": "application/json"
        },
        # 环境变量
        "envs": {
            "username": "rand_13012349900",
            "password": "rand_test123",
            "token": "12345678"
        },
        "global_func": open("..\\tests\\Tools.py", "r", encoding="utf-8").read(),
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
    runner = TestRunner(test_case2, test_env_data)
    # runner = TestRunner(test_suite,test_env_data)
    # runner = TestRunner(test_suites,test_env_data)
    result = runner.execute_cases()
    log.info_log("测试结果：", result)