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

    def _build_info(self, test: BaseCase, status: str) -> dict:
        """构建用例结果信息（包含提取和断言结果）"""
        return {
            "name": getattr(test, "name", ""),
            "url": getattr(test, "url", ""),
            "method": getattr(test, "method", ""),
            "request_headers": getattr(test, "request_headers", ""),
            "request_body": getattr(test, "request_body", ""),
            "response_code": getattr(test, "status_code", ""),
            "response_headers": getattr(test, "response_headers", ""),
            "response_body": getattr(test, "response_body", ""),
            "status": status,
            "log_data": getattr(test, "log_data", ""),
            "run_time": getattr(test, "elapsed_ms", ""),
            "extract_info": getattr(test, "_extract_results", []),
            "assert_info": getattr(test, "_assert_results", []),
            "precondition_results": getattr(test, "_precondition_results", []),
        }

    def add_success(self, test: BaseCase):
        """
        :param test: 用例对象
        :return:
        """
        self.success += 1
        self.results.append(self._build_info(test, "success"))

    def add_fail(self, test: BaseCase):
        """
        :param test: 用例对象
        :return:
        """
        self.fail += 1
        self.results.append(self._build_info(test, "fail"))

    def add_error(self, test: BaseCase, error):
        """
        :param test: 用例对象
        :return:
        """
        self.error += 1
        # 同时记录到全局日志和当前用例日志，确保返回结果中也能看到 ERROR 记录
        log.error_log("用例执行错误，错误信息：", error)
        try:
            test.error_log("用例执行错误，错误信息：", error)
        except Exception:
            pass
        self.results.append(self._build_info(test, "error"))

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
