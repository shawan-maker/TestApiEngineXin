from ApiEngine.infra import global_func


class ScriptRunner:
    """前后置脚本执行器（生成器模式）"""

    @staticmethod
    def create_hook(data, test_instance, shared_env, db):
        """
        创建前后置脚本钩子（生成器）
        :param data: 用例数据（包含 setup_script / teardown_script）
        :param test_instance: BaseCase 实例（供脚本中的 test 引用）
        :param shared_env: 共享环境数据（供脚本中的 ENV 引用）
        :param db: 数据库客户端实例（供脚本中的 db 引用）
        """
        test = test_instance
        ENV = shared_env
        global_var = shared_env.get("envs")
        print = test_instance.print_log
        test_instance.env = {}

        # 执行前置脚本
        setup_scripts = data.get("setup_script")
        if setup_scripts and isinstance(setup_scripts, str):
            exec(setup_scripts)

        response = yield

        # 执行后置脚本
        teardown_scripts = data.get("teardown_script")
        if teardown_scripts and isinstance(teardown_scripts, str):
            exec(teardown_scripts)

        yield
