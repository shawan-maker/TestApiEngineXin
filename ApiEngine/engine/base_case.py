import time

from ApiEngine.infra.case_log import CaseLogHandler
from ApiEngine.http.client import HttpClient
from ApiEngine.engine.replacer import Replacer
from ApiEngine.engine.extractor import Extractor
from ApiEngine.engine.assertion import AssertionEngine
from ApiEngine.engine.script_runner import ScriptRunner
from ApiEngine.engine.precondition import PreconditionExecutor


class BaseCase(CaseLogHandler):
    """用例执行编排层：协调各模块完成一次用例执行"""

    def __init__(self, shared_env=None):
        super().__init__()
        self._shared_env = shared_env or {}
        self._db = None
        self.env = {}
        self._extract_results = []
        self._assert_results = []
        self._extractor = Extractor()

    # ==================== 脚本执行 ====================

    def _setup_script(self, data):
        """前置脚本处理"""
        self._script_hook = ScriptRunner.create_hook(
            data, self, self._shared_env, self._db
        )
        next(self._script_hook)

    def _teardown_script(self, data, response):
        """后置脚本处理"""
        if hasattr(self, '_script_hook'):
            try:
                self._script_hook.send(response)
            except StopIteration:
                pass
            delattr(self, "_script_hook")

    # ==================== HTTP 请求 ====================

    def _send_request(self, data, http_client=None):
        """构建并发送请求"""
        if http_client is None:
            http_client = HttpClient()
            self._owns_http_client = True
        else:
            self._owns_http_client = False
        self._http_client = http_client
        replacer = Replacer(self._shared_env, self.env, self.info_log)
        request_data = http_client.build_request(data, self._shared_env, replacer)
        self.info_log(request_data)
        response, req_info = http_client.send(request_data, self.info_log)

        # 记录请求/响应信息
        self.name = data.get("title")
        self.url = req_info["url"]
        self.method = req_info["method"]
        self.request_headers = req_info["request_headers"]
        self.request_body = req_info["request_body"]
        self.status_code = req_info["status_code"]
        self.response_headers = req_info["response_headers"]
        self.response_body = req_info["response_body"]

        self.info_log("请求地址:", req_info["url"])
        self.info_log("请求方法:", req_info["method"])
        self.info_log("请求头:", req_info["request_headers"])
        self.info_log("响应头:", req_info["response_headers"])
        self.info_log("请求体:", req_info["request_body"])
        self.info_log("响应体:", req_info["response_body"])
        return response

    # ==================== 数据提取 ====================

    def _extract_data(self, extract, response):
        """从响应中提取数据并保存到环境变量"""
        var_name = extract.get("var_name")
        extract_expr = extract.get("extract_expr")
        try:
            resp_json = response.json()
        except Exception:
            resp_json = {}
            self.error_log("响应体非JSON格式，无法提取数据")
        extracted_value = self._extractor.json_extract(resp_json, extract_expr)
        self._save_env_variable(var_name, extracted_value)
        self.info_log(f"数据提取成功：{var_name} = {extracted_value}")
        self._extract_results.append({
            "var_name": var_name,
            "extract_expr": extract_expr,
            "value": extracted_value,
        })

    # ==================== 断言 ====================

    def _execute_assertions(self, data, response):
        """批量执行断言"""
        assertion_errors = []
        if data.get("assertions"):
            total = len(data.get("assertions"))
            self.info_log(f"========== 开始执行断言（共 {total} 个） ==========")
            replacer = Replacer(self._shared_env, self.env, self.info_log)
            for idx, assertion in enumerate(data.get("assertions"), start=1):
                field = assertion.get("field", "未知")
                expected = assertion.get("expected", "未知")
                assert_type = assertion.get("type", "eq")
                passed = True
                actual_value = None
                try:
                    self.info_log(f"  [{idx}/{total}] 执行断言: field={field}, expected={expected}")

                    # 对 expected 进行变量替换
                    assertion_content = expected
                    if isinstance(assertion_content, str) and "${" in assertion_content:
                        self.info_log(f"检测到断言期望值包含变量引用：{assertion_content}")
                        assertion_content = replacer.replace_data(assertion_content)
                        self.info_log(f"变量替换后期望值：{assertion_content}")

                    # 提取实际值
                    if field == "status_code":
                        actual_value = response.status_code
                        self.info_log(f"检测到断言字段为 status_code，直接获取 HTTP 状态码：{actual_value}")
                    else:
                        try:
                            resp_json = response.json()
                        except Exception:
                            resp_json = {}
                            self.error_log("响应体非JSON格式，无法提取数据")
                        actual_value = self._extractor.json_extract(resp_json, field)

                    self._last_actual = actual_value
                    AssertionEngine.assert_value(
                        assert_type, assertion_content, actual_value,
                        debug_log=self.debug_log,
                        info_log=self.info_log,
                        error_log=self.error_log
                    )
                    self.info_log(f"  [{idx}/{total}] ✅ 断言通过: {field}")
                except AssertionError as e:
                    passed = False
                    actual_value = getattr(self, '_last_actual', None)
                    self.error_log(f"  [{idx}/{total}] ❌ 断言失败: {field} — {e}")
                    assertion_errors.append({
                        "index": idx, "field": field,
                        "expected": expected,
                        "error_type": "ASSERTION_FAILED",
                        "message": str(e)
                    })
                self._assert_results.append({
                    "field": field, "type": assert_type,
                    "expected": expected, "actual": actual_value,
                    "passed": passed,
                })
            passed_count = total - len(assertion_errors)
            if assertion_errors:
                self.warning_log(
                    f"========== 断言汇总：共 {total} 个，"
                    f"通过 {passed_count} 个，失败 {len(assertion_errors)} 个 =========="
                )
                for err in assertion_errors:
                    self.warning_log(
                        f"  ❌ [第{err['index']}个] field={err['field']}, "
                        f"expected={err['expected']}, 原因: {err['message']}"
                    )
            else:
                self.info_log(f"========== 断言汇总：{total} 个全部通过 ✅ ==========")
            if assertion_errors:
                fail_details = "; ".join(
                    f"[{err['field']}] {err['message']}" for err in assertion_errors
                )
                raise AssertionError(
                    f"用例 [{data.get('title')}] 断言失败："
                    f"通过 {passed_count}/{total}，"
                    f"失败详情 → {fail_details}"
                )

    # ==================== 主执行流程 ====================

    def perform(self, data):
        """执行用例"""
        start_time = time.time()
        self._precondition_errors = []
        self._precondition_results = []
        self._extract_results = []
        self._assert_results = []
        case_name = data.get('title')
        has_failure = False
        shared_http_client = None

        try:
            # 创建共享 HTTP session（前置步骤 + 主用例共用 Cookie）
            shared_http_client = HttpClient()

            # 1、前置条件链
            if data.get("preconditions"):
                self.info_log("========== 开始执行前置步骤链 ==========")
                precond_executor = PreconditionExecutor(
                    self._shared_env, self._db, http_client=shared_http_client
                )
                self._precondition_errors, self._precondition_results = precond_executor.execute(
                    data.get("preconditions"), depth=1, log_handler=self
                )
                if self._precondition_errors:
                    has_failure = True
                    self.warning_log(
                        f"前置步骤链完成，但有 {len(self._precondition_errors)} 个步骤失败，"
                        f"继续执行主用例"
                    )
                else:
                    self.info_log("========== 前置步骤链全部通过 ==========")

            # 2、前置脚本 + 发送请求
            self.info_log(f"开始执行用例步骤:{case_name}")
            self._setup_script(data)
            response = self._send_request(data, http_client=shared_http_client)

            # 3、数据提取
            if data.get("extract"):
                for extract in data.get("extract"):
                    self._extract_data(extract, response)

            # 4、断言
            self._execute_assertions(data, response)

            # 5、后置脚本
            self._teardown_script(data, response)
            self.info_log(f"结束执行用例步骤:{case_name}")

            if has_failure:
                raise AssertionError(
                    f"[{case_name}] 用例执行完成但存在 {len(self._precondition_errors)} 个前置失败"
                )

        except AssertionError as e:
            has_failure = True
            self.warning_log(f"⚠️ 用例 [{case_name}] 存在失败断言")
            raise

        except Exception as e:
            self.error_log(f" ❌用例执行异常: {case_name} — {e}")
            raise

        finally:
            # 关闭共享 http client
            if shared_http_client:
                shared_http_client.close()
            if hasattr(self, '_http_client'):
                delattr(self, '_http_client')

            end_time = time.time()
            elapsed_time = end_time - start_time
            self.elapsed_ms = "{} ms".format(int(elapsed_time * 1000))
            self.info_log(f"✅ 用例执行完成:{case_name}")

    # ==================== 环境变量操作 ====================

    def _save_env_variable(self, key, value):
        """保存临时环境变量"""
        self.info_log(f"保存（临时）环境变量：{key} = {value}")
        self.env[key] = value
        try:
            envs = self._shared_env.get("envs")
            if isinstance(envs, dict):
                envs[key] = value
        except Exception:
            pass

    def save_env_variable(self, key, value):
        """保存临时环境变量（供脚本调用）"""
        self._save_env_variable(key, value)

    def del_evn_variable(self, key):
        """删除测试运行环境变量"""
        self.info_log(f"删除（临时）环境变量：{key}")
        del self.env[key]

    def save_global_variable(self, key, value):
        """保存测试运行环境的全局变量"""
        self.info_log(f"保存全局变量：{key} = {value}")
        envs = self._shared_env.get("envs")
        if isinstance(envs, dict):
            envs[key] = value
        # 记录到 debug_updates，便于上层平台同步到数据库
        try:
            debug_updates = self._shared_env.get("debug_updates")
            if isinstance(debug_updates, dict):
                debug_updates[key] = value
        except Exception:
            pass

    def del_global_variable(self, key):
        """删除测试运行环境的全局变量"""
        self.info_log(f"删除全局变量：{key}")
        envs = self._shared_env.get("envs")
        if isinstance(envs, dict) and key in envs:
            del envs[key]
        # 在 debug_updates 中标记为 None，通知上层从数据库删除
        try:
            debug_updates = self._shared_env.get("debug_updates")
            if isinstance(debug_updates, dict):
                debug_updates[key] = None
        except Exception:
            pass

    def get_env_variable(self, key, default=None):
        """获取临时变量（局部变量）"""
        self.info_log(f"获取（临时）环境变量：{key}")
        return self.env.get(key, default)

    def get_global_variable(self, key, default=None):
        """获取环境变量（全局变量）"""
        self.info_log(f"获取环境变量：{key}")
        envs = self._shared_env.get("envs")
        if isinstance(envs, dict):
            return envs.get(key, default)
        return default

    # ==================== 数据提取（供脚本调用） ====================

    def json_extract(self, obj, ext):
        """通过jsonpath提取一个json数据"""
        self.info_log("----通过jsonpath提取单个数据---")
        return self._extractor.json_extract(obj, ext)

    def json_extract_list(self, obj, ext):
        """通过jsonpath提取一组json数据"""
        self.info_log("----通过jsonpath提取一组数据---")
        return self._extractor.json_extract_list(obj, ext)

    def re_extract(self, obj, ext):
        """通过正则提取一个数据"""
        self.info_log("----通过正则提取数据---")
        return self._extractor.re_extract(obj, ext)

    def re_extract_list(self, obj, ext):
        """通过正则提取一组数据"""
        self.info_log("----通过正则提取一组数据---")
        return self._extractor.re_extract_list(obj, ext)

    # ==================== 断言（供脚本调用） ====================

    def assertion(self, method, expect, actual):
        """执行断言（供脚本直接调用）"""
        AssertionEngine.assert_value(
            method, expect, actual,
            debug_log=self.debug_log,
            info_log=self.info_log,
            error_log=self.error_log
        )
