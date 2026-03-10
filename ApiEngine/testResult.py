from ApiEngine import log
from ApiEngine.BaseCase import BaseCase


class TestResult:
    """测试结果类"""
    def __init__(self, all, name="调试运行"):
        """
        :param all: 测试套件中的用例个数
        :param name: 测试套件的名称
        """
        self.all = all
        self.name = name
        self.success = 0
        self.fail = 0
        self.error = 0
        self.results = []

    def add_success(self, test: BaseCase):
        """
        :param test: 用例对象
        :return:
        """
        self.success += 1
        info = {
            "name": getattr(test, "name",""),
            "url": getattr(test, "url",""),
            "method": getattr(test, "method",""),
            "request_headers": getattr(test, "request_headers",""),
            "request_body": getattr(test, "request_body",""),
            "response_code": getattr(test, "status_code",""),
            "response_headers": getattr(test, "response_headers",""),
            "response_body": getattr(test, "response_body",""),
            "status": "success",
            "log_data": getattr(test, "log_data", ""),
            "run_time": getattr(test,"elapsed_ms","")
        }
        self.results.append(info)

    def add_fail(self, test: BaseCase):
        """
        :param test: 用例对象
        :return:
        """
        self.fail += 1
        info = {
            "name": getattr(test, "name",""),
            "url": getattr(test, "url",""),
            "method": getattr(test, "method",""),
            "request_headers": getattr(test, "request_headers",""),
            "request_body": getattr(test, "request_body",""),
            "response_code": getattr(test, "status_code",""),
            "response_headers": getattr(test, "response_headers",""),
            "response_body": getattr(test, "response_body",""),
            "status": "fail",
            "log_data": getattr(test, "log_data", ""),
            "run_time": getattr(test,"elapsed_ms","")
        }
        self.results.append(info)

    def add_error(self, test: BaseCase, error):
        """
        :param test: 用例对象
        :return:
        """
        self.error += 1
        # 同时记录到全局日志和当前用例日志，确保返回结果中也能看到 ERROR 记录
        log.error_log("用例执行错误，错误信息：", error)
        try:
            # BaseCase 继承了 CaseLogHandler，直接复用其 error_log 记录到用例的 log_data
            test.error_log("用例执行错误，错误信息：", error)
        except Exception:
            # 如果 test 上不存在 error_log（理论上不会发生），则忽略，不影响后续结果生成
            pass
        info = {
            "name": getattr(test, "name",""),
            "url": getattr(test, "url",""),
            "method": getattr(test, "method",""),
            "request_headers": getattr(test, "request_headers",""),
            "request_body": getattr(test, "request_body",""),
            "response_code": getattr(test, "status_code",""),
            "response_headers": getattr(test, "response_headers",""),
            "response_body": getattr(test, "response_body",""),
            "status": "error",
            "log_data": getattr(test, "log_data", ""),
            "run_time": getattr(test,"elapsed_ms","")
        }
        self.results.append(info)

    def get_result_info(self):
        """
        :return: 测试结果信息
        """
        if self.success == self.all:
            state = "success"
        elif self.fail > 0:
            state = "fail"
        else:
            state = "error"
        info = {
            "name": self.name,
            "all": self.all,
            "success": self.success,
            "fail": self.fail,
            "error": self.error,
            "cases": self.results,
            "state": state
        }
        return info