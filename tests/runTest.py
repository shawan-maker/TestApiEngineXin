from ApiEngine import global_func
from ApiEngine.BaseCase import BaseCase, ENV, db

if __name__ == '__main__':
    case = {
        "interface": {
            "url": "/member/public/login",
            "method": "post"
        },
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "Token": "${token}"
        },
        "request_data": {
            "params": {},
            "data": {"keywords":"13012349900","password":"test123","user2":"${username}","pwd2":"${password}","mobile":"${mobile}"},
            "json": {"keywords":"13012349900","password":"test123","user2":"${username}","pwd2":"${password}","mobile":"${mobile}"}
        },
        "setup_scripts": open("setup_scripts.txt", "r", encoding="utf-8").read(),
        "teardown_scripts": open("teardown_scripts.txt", "r", encoding="utf-8").read()
    }
    # 全局环境数据
    test_env_data = {
        # "base_url": "http://121.43.169.97:8081",
        "base_url": "http://127.0.0.1",
        "headers": {
            "Content-Type": "application/json"
        },
        # 环境变量
        "envs": {
            "username": "rand_13012349900",
            "password": "rand_test123",
            "token": "12345678"
        },
        "tools": open("Tools.py", "r", encoding="utf-8").read(),
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
    # 根据数据库的配置初始化数据库的连接
    db.init_connent(test_env_data.pop("db"))
    # 将全局环境测试加载到ENV中
    ENV.update(test_env_data)
    # 将tools中的函数（用户自定义），通过exec执行（字符串中的python函数），加载到TestTools模块的命名空间中
    exec(ENV.get("tools"), global_func.__dict__)
    # 运行测试用例
    BaseCase().perform(case)
    # 断开数据库连接
    db.close_db_connent()