from ApiEngine.infra.exceptions import PreconditionChainError
from ApiEngine.http.client import HttpClient
from ApiEngine.engine.script_runner import ScriptRunner
from ApiEngine.engine.extractor import Extractor
from ApiEngine.engine.assertion import AssertionEngine


class PreconditionExecutor:
    """前置条件递归执行器（深度优先 DFS）"""

    def __init__(self, shared_env, db, http_client=None):
        self._shared_env = shared_env
        self._db = db
        self._extractor = Extractor()
        self._precondition_results = []
        self._shared_http_client = http_client  # 共享 HTTP session

    def execute(self, steps, depth=1, failure_mode="continue", log_handler=None):
        """
        递归执行多级前置接口
        :param steps: 前置步骤列表
        :param depth: 当前递归深度
        :param failure_mode: 失败模式 continue/stop
        :param log_handler: 日志处理实例（CaseLogHandler）
        :return: 错误列表, 前置结果列表
        """
        if not steps:
            return [], self._precondition_results

        prefix = "  " * depth
        precondition_errors = []

        for step in steps:
            title = step.get('title', '未命名前置')
            log_handler.info_log(f"{prefix}▶ [L{depth}] 执行前置步骤: {title}")

            # 递归子前置
            if step.get("preconditions"):
                log_handler.info_log(f"{prefix}  [L{depth}] '{title}' 有下级前置，先递归执行")
                child_errors, _ = self.execute(
                    step.get("preconditions"), depth + 1,
                    failure_mode=failure_mode, log_handler=log_handler
                )
                if child_errors:
                    precondition_errors.extend(child_errors)
                    log_handler.warning_log(f"{prefix}  [L{depth}] 子前置存在 {len(child_errors)} 个错误")
                log_handler.info_log(f"{prefix}  [L{depth}] '{title}' 的下级前置完成，开始执行自身")

            # 单步执行
            step_error = None
            has_assertion_error = False
            response = None
            step_assert_results = []
            step_extract_results = []
            http_client = None
            script_hook = None

            try:
                # 重置响应属性
                log_handler.status_code = ''
                log_handler.response_body = ''
                log_handler.response_headers = {}

                # 前置脚本
                script_hook = ScriptRunner.create_hook(
                    step, log_handler, self._shared_env, self._db
                )
                next(script_hook)

                # 发送请求：使用共享 session，无共享则创建临时实例
                from ApiEngine.engine.replacer import Replacer
                if self._shared_http_client:
                    http_client = self._shared_http_client
                else:
                    http_client = HttpClient()
                temp_env = {}
                replacer = Replacer(self._shared_env, temp_env, log_handler.info_log)
                request_data = http_client.build_request(step, self._shared_env, replacer)
                log_handler.info_log(request_data)
                response, req_info = http_client.send(request_data, log_handler.info_log)

                # 记录请求/响应信息到 log_handler
                log_handler.url = req_info["url"]
                log_handler.method = req_info["method"]
                log_handler.request_headers = req_info["request_headers"]
                log_handler.request_body = req_info["request_body"]
                log_handler.status_code = req_info["status_code"]
                log_handler.response_headers = req_info["response_headers"]
                log_handler.response_body = req_info["response_body"]

                log_handler.info_log("请求地址:", req_info["url"])
                log_handler.info_log("请求方法:", req_info["method"])
                log_handler.info_log("请求头:", req_info["request_headers"])
                log_handler.info_log("响应头:", req_info["response_headers"])
                log_handler.info_log("请求体:", req_info["request_body"])
                log_handler.info_log("响应体:", req_info["response_body"])

                # 数据提取
                if step.get("extract"):
                    for extract in step.get("extract"):
                        var_name = extract.get("var_name")
                        extract_expr = extract.get("extract_expr")
                        try:
                            resp_json = response.json()
                        except Exception:
                            resp_json = {}
                            log_handler.error_log("响应体非JSON格式，无法提取数据")
                        extracted_value = self._extractor.json_extract(resp_json, extract_expr)
                        # 保存到环境变量
                        temp_env[var_name] = extracted_value
                        envs = self._shared_env.get("envs")
                        if isinstance(envs, dict):
                            envs[var_name] = extracted_value
                        log_handler.info_log(f"数据提取成功：{var_name} = {extracted_value}")
                        step_extract_results.append({
                            "var_name": var_name,
                            "extract_expr": extract_expr,
                            "value": extracted_value,
                        })

                # 断言
                if step.get("assertions"):
                    total = len(step["assertions"])
                    log_handler.info_log(f"{prefix}  ========== 开始执行断言（共 {total} 个） ==========")
                    assertion_errors = []
                    for idx, assertion in enumerate(step["assertions"], start=1):
                        field = assertion.get("field", "未知")
                        expected = assertion.get("expected", "未知")
                        assert_type = assertion.get("type", "eq")
                        passed = True
                        actual_value = None
                        try:
                            log_handler.info_log(f"{prefix}  [{idx}/{total}] 执行断言: field={field}, expected={expected}")
                            # 对 expected 进行变量替换
                            assertion_content = expected
                            if isinstance(assertion_content, str) and "${" in assertion_content:
                                from ApiEngine.engine.replacer import Replacer as R2
                                r2 = R2(self._shared_env, temp_env, log_handler.info_log)
                                assertion_content = r2.replace_data(assertion_content)
                                log_handler.info_log(f"变量替换后期望值：{assertion_content}")
                            # 提取实际值
                            if field == "status_code":
                                actual_value = response.status_code
                            else:
                                try:
                                    resp_json = response.json()
                                except Exception:
                                    resp_json = {}
                                actual_value = self._extractor.json_extract(resp_json, field)
                            AssertionEngine.assert_value(
                                assert_type, assertion_content, actual_value,
                                debug_log=log_handler.debug_log,
                                info_log=log_handler.info_log,
                                error_log=log_handler.error_log
                            )
                            log_handler.info_log(f"{prefix}  [{idx}/{total}] ✅ 断言通过: {field}")
                        except AssertionError as e:
                            passed = False
                            log_handler.error_log(f"{prefix}  [{idx}/{total}] ❌ 断言失败: {field} — {e}")
                            assertion_errors.append({
                                "index": idx, "field": field,
                                "expected": expected,
                                "error_type": "ASSERTION_FAILED",
                                "message": str(e)
                            })
                        step_assert_results.append({
                            "field": field, "type": assert_type,
                            "expected": expected, "actual": actual_value,
                            "passed": passed,
                        })
                    passed_count = total - len(assertion_errors)
                    if assertion_errors:
                        log_handler.warning_log(
                            f"{prefix}  断言汇总：共 {total} 个，"
                            f"通过 {passed_count} 个，失败 {len(assertion_errors)} 个"
                        )
                        fail_details = "; ".join(
                            f"[{err['field']}] {err['message']}" for err in assertion_errors
                        )
                        raise AssertionError(
                            f"前置 [{title}] 断言失败：通过 {passed_count}/{total}，"
                            f"失败详情 → {fail_details}"
                        )
                    else:
                        log_handler.info_log(f"{prefix}  断言汇总：{total} 个全部通过 ✅")

            except AssertionError as e:
                has_assertion_error = True
                step_error = {
                    "level": depth,
                    "step_title": title,
                    "error_type": "ASSERTION_FAILED",
                    "message": str(e)
                }
                log_handler.warning_log(f"{prefix}❌ [L{depth}] 存在断言失败: {title} — {e}")

            except Exception as e:
                step_error = {
                    "level": depth,
                    "step_title": title,
                    "error_type": "EXECUTION_ERROR",
                    "message": str(e)
                }
                log_handler.error_log(f"{prefix}❌ [L{depth}] 前置执行异常: {title} — {e}")

            finally:
                # teardown
                if script_hook:
                    try:
                        script_hook.send(response)
                    except StopIteration:
                        pass

                # 仅关闭非共享的 http client
                if http_client and not self._shared_http_client:
                    http_client.close()

                # 构建步骤结果
                _req_body = getattr(log_handler, 'request_body', '')
                if isinstance(_req_body, bytes):
                    _req_body = _req_body.decode('utf-8', errors='replace')
                _elapsed = ""
                if response is not None:
                    try:
                        _elapsed = "{} ms".format(int(response.elapsed.total_seconds() * 1000))
                    except Exception:
                        pass
                # 推断步骤状态
                if step_error:
                    step_status = "fail"
                elif has_assertion_error:
                    step_status = "fail"
                else:
                    step_status = "success"
                step_result = {
                    "title": title,
                    "status": step_status,
                    "status_code": getattr(log_handler, 'status_code', ''),
                    "response_headers": dict(getattr(log_handler, 'response_headers', {}) or {}),
                    "response_body": getattr(log_handler, 'response_body', ''),
                    "request_body": _req_body,
                    "request_headers": dict(getattr(log_handler, 'request_headers', {}) or {}),
                    "url": getattr(log_handler, 'url', ''),
                    "method": getattr(log_handler, 'method', ''),
                    "run_time": _elapsed,
                    "assert_info": list(step_assert_results),
                    "extract_info": list(step_extract_results),
                }
                self._precondition_results.append(step_result)
                if step_error or has_assertion_error:
                    log_handler.warning_log(f"{prefix}❌ [L{depth}] 前置失败: {title}")
                else:
                    log_handler.info_log(f"{prefix}✅ [L{depth}] 前置完成: {title}")

            # 根据 failure_mode 决定是否继续
            if step_error:
                precondition_errors.append(step_error)
                if failure_mode == "stop":
                    log_handler.error_log(f"{prefix}🛑 [L{depth}] 配置 on_failure=stop，中止执行")
                    raise PreconditionChainError(precondition_errors)

        return precondition_errors, self._precondition_results
