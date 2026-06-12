import re,time
import requests
from jsonpath import jsonpath
from . import global_func,log
from .caseLog import CaseLogHandler, PreconditionChainError
from .dbClient import DBClient
# 定义脚本中的全局变量
ENV = {}
# db = DBClient()

class BaseCase(CaseLogHandler):
    """用例执行基本父类"""
    def __init__(self):
        self.session = requests.Session()
        self._db = None
        self._extract_results = []
        self._assert_results = []

    def __run_script(self, data):
        # 执行前后置脚本，可以在前后置脚本中共享数据
        test = self
        global_var = ENV.get("envs")
        print = self.print_log
        # 定义脚本中的临时变量
        self.env = {}
        db = self._db
        # 1、读取前置脚本数据
        setup_scripts = data.get("setup_script")
        # 2、执行字符串中有效的python代码
        exec(setup_scripts)

        response = yield

        # 1、读取后置脚本数据
        teardown_scripts = data.get("teardown_script")
        # 2、执行字符串中有效的python代码
        exec(teardown_scripts)

        yield

    def __setup_script(self, data):
        """前置脚本处理"""
        self.script_hook = self.__run_script(data)
        next(self.script_hook)

    def __teardown_script(self, data, response):
        """后置脚本处理"""
        self.script_hook.send(response)
        """删除生成器对象"""
        delattr(self, "script_hook")


    def execute_function_if_exists(self, value):
        """
        支持带参数函数调用，增加异常兜底（避免返回None）
        """
        if not isinstance(value, str):
            # 非字符串类型直接返回
            return value

        # 匹配函数调用格式：如 gen_random_num(2)、random_mobile()
        func_pattern = r"^(\w+)\((.*)\)$"
        func_match = re.match(func_pattern, value.strip())
        if not func_match:
            return value

        # 提取函数名和参数
        func_name = func_match.group(1)
        func_args_str = func_match.group(2).strip()

        # 从 global_func 模块获取函数
        try:
            func = getattr(global_func, func_name)
            if not callable(func):
                log.warning_log(f"{func_name} 不是可调用函数，返回原格式")
                return value  # 兜底：不返回None
        except AttributeError:
            log.warning_log(f"全局函数 {func_name} 不存在，返回原格式")
            return value  # 兜底：不返回None

        # 解析参数
        func_args = []
        if func_args_str:
            try:
                func_args = eval(f"[{func_args_str}]")
            except Exception as e:
                log.error_log(f"解析函数 {func_name} 参数失败：{str(e)}，返回原格式")
                return value  # 兜底：不返回None

        # 执行函数
        log.info_log(f"执行函数 {func_name}，参数：{func_args}，参数类型：{[type(x) for x in func_args]}")
        try:
            func_result = func(*func_args)
            log.info_log(f"函数 {func_name} 执行结果：{func_result}，类型：{type(func_result)}")
            return func_result
        except Exception as e:
            log.error_log(f"执行 {func_name} 抛出异常：{str(e)}", exc_info=True)
            return value  # 兜底：不返回None

    def replace_data(self, data):
        """替换测试用例中的变量数据"""
        # 1、定义替换数据的规则
        pattern = r"\${(.+?)}"
        # 2、将测试数据转为字符串（统一处理）
        data_str = str(data)
        log.info_log("替换数据原始内容：", data_str)

        # 3、循环替换变量（直到无未解析的${}，或达到最大循环次数）
        max_loop = 100  # 避免死循环
        loop_count = 0
        has_unresolved = True  # 标记是否还有未解析的变量

        while has_unresolved and loop_count < max_loop:
            loop_count += 1
            # 记录替换前的内容，用于判断是否有变化
            original_str = data_str

            # 遍历所有匹配的变量，逐个替换
            for match_data in list(re.finditer(pattern, data_str)):  # list避免迭代时字符串变化
                full_match = match_data.group()  # 完整匹配：如 ${e_Cloud_vendors_name}
                key = match_data.group(1)  # 提取内容：如 e_Cloud_vendors_name

                log.info_log(f"第{loop_count}次匹配：{full_match} → 提取内容：{key}")

                # 步骤1：先从临时变量 self.env 取值
                value = self.env.get(key)
                # 步骤2：临时变量无值 → 从全局变量 ENV["envs"] 取值
                if value is None:
                    value = ENV.get("envs", {}).get(key)
                # 步骤3：仍无值 → 直接使用 key 作为值（如 key 是函数调用：gen_random_num(2)）
                if value is None:
                    log.info_log(f"变量 {key} 无临时/全局值，尝试作为函数调用处理")
                    value = key

                # 核心：执行函数（支持带参数），得到最终替换值
                value_after_exec = self.execute_function_if_exists(value)

                # 替换当前匹配的变量
                data_str = data_str.replace(full_match, str(value_after_exec))
                log.info_log(f"替换结果：{full_match} → {value_after_exec}")

            # 判断是否还有未解析的变量（替换后是否变化）
            has_unresolved = re.search(pattern, data_str) is not None
            if original_str == data_str:
                # 内容无变化，说明无法继续替换，退出循环
                has_unresolved = False

        if loop_count >= max_loop:
            log.warning_log(f"变量替换达到最大循环次数 {max_loop}，强制退出（可能存在循环引用）")

        # 4、还原数据类型（避免所有数据都是字符串）
        try:
            return eval(data_str)
        except (SyntaxError, NameError, TypeError):
            log.error_log(f"数据 {data_str} 无法还原类型，返回字符串格式")
            return data_str

    def __handle_request_data(self, data):
        """处理请求数据"""
        self.name = data.get("title")
        request_data = {}
        # 1、处理请求url
        if data.get("interface").get("url").startswith("http"):
            request_data["url"] = data.get("interface").get("url")
        else:
            request_data["url"] = ENV.get("base_url") + data.get("interface").get("url")
        request_data["method"] = data.get("interface").get("method")
        # 2、处理请求头
        request_data["headers"] = ENV.get("headers")
        request_data["headers"].update(data.get("headers"))
        # 3、处理请求参数
        request_data["params"] = data.get("request").get("params")
        content_type = request_data["headers"].get("Content-Type", "")
        if "application/json" in content_type:
            request_data["json"] = data.get("request").get("json")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            request_data["data"] = data.get("request").get("data")
        if "multipart/form-data" in content_type:
            # 注意：这里不直接把 files 放进需要做变量替换的数据里，避免 open 文件对象被 eval 破坏
            request_data["files"] = data.get("request").get("files")
        # 4、替换请求中的变量名 为 具体的变量数据（files 保持原值）
        files_raw = request_data.get("files")
        request_data_for_replace = dict(request_data)
        if "files" in request_data_for_replace:
            request_data_for_replace.pop("files")
        request_data = self.replace_data(request_data_for_replace)
        if files_raw is not None:
            request_data["files"] = files_raw
        self.url = request_data.get("url","")
        self.method = request_data.get("method","")
        self.request_headers = request_data.get("headers", {})
        return request_data

    def __send_request(self, data):
        """发送请求"""
        request_data = self.__handle_request_data(data)
        self.info_log(request_data)
        files_param = request_data.get("files")
        # ★ 新增：用于跟踪已打开的文件句柄（便于后续统一关闭）
        opened_files = []
        # 执行文件转换
        if isinstance(files_param, dict):
            files_param, new_opened = self.convert_files(files_param)
            opened_files.extend(new_opened)
        try:
            response = self.session.request(method=request_data.get("method"),
                                        url=request_data.get("url"),
                                        headers=request_data.get("headers"),
                                        params=request_data.get("params"),
                                        data=request_data.get("data"),
                                        json=request_data.get("json"),
                                        files=files_param,
                                        allow_redirects=False)
            #  获取用例执行的请求和响应信息
            self.request_body = response.request.body
            self.status_code = response.status_code
            self.response_headers = response.headers
            self.response_body = response.text
            # 拼接完整URL（包含params参数）
            full_url = self.url
            params = request_data.get("params")
            if params:
                from urllib.parse import urlencode
                query_string = urlencode(params)
                full_url = f"{self.url}?{query_string}"
            self.info_log("请求地址:", full_url)
            self.info_log("请求方法:", self.method)
            self.info_log("请求头:", self.request_headers)
            self.info_log("响应头:", self.response_headers)
            self.info_log("请求体:", self.request_body)
            self.info_log("响应体:", self.response_body)
            return response
        finally:
            # ★ 统一关闭所有打开的文件句柄（防止资源泄漏）
            for f in opened_files:
                try:
                    f.close()
                except Exception:
                    pass
            if opened_files:
                self.info_log(f"已关闭 {len(opened_files)} 个文件句柄")

    def convert_files(self,param):
        """递归转换文件参数，返回 (converted_dict, opened_files_list)"""
        local_opened = []

        if not isinstance(param, dict):
            return param

        converted = {}
        for field, val in param.items():
            if isinstance(val, dict) and "path" in val:
                # 格式 A: {"path": "...", "name": "..."}
                try:
                    import os
                    file_path = val["path"]
                    filename = val.get("name") or os.path.basename(file_path)
                    # ★ 修复：不用 with，手动管理文件句柄
                    f = open(file_path, "rb")
                    local_opened.append(f)
                    self.info_log(f"成功加载文件: {field} = {filename}")
                    converted[field] = (filename, f)
                except Exception as e:
                    self.error_log(f"文件加载失败 [{val.get('path')}]: {e}")

            elif isinstance(val, list):
                # 格式 C: 列表格式（单字段多文件）
                file_list = []
                for item in val:
                    if isinstance(item, tuple) and len(item) == 2:
                        # 已经是 (filename, fileobj) 元组
                        file_list.append(item)
                    elif isinstance(item, dict) and "path" in item:
                        try:
                            import os
                            fp = item["path"]
                            fn = item.get("name") or os.path.basename(fp)
                            # ★ 修复：不用 with
                            f = open(fp, "rb")
                            local_opened.append(f)
                            file_list.append((fn, f))
                        except Exception as e:
                            self.error_log(f"列表项文件加载失败 [{item.get('path')}]: {e}")
                    else:
                        # 其他格式直接使用
                        file_list.append(item)
                if file_list:
                    converted[field] = file_list
            else:
                # 格式 B: 直接传值/元组
                converted[field] = val

        return converted if converted else None, local_opened

    def __extract_data(self, extract, response):
        """
        从响应中提取数据并保存到环境变量
        :param extract: 提取规则，格式 ("变量名", "JSONPath表达式")
                        例如 {"var_name":"user_id","extract_expr":"$.result.user_id"},
        :param response: requests.Response 对象
        """
        # 1、解构元组：(变量名, 提取表达式)
        var_name = extract.get("var_name")
        extract_expr = extract.get("extract_expr")
        # 2、将响应体解析为 JSON/dict
        try:
            resp_json = response.json()
        except Exception:
            resp_json = {}
            self.error_log("响应体非JSON格式，无法提取数据")
        # 3、通过 JSONPath 提取值
        extracted_value = self.json_extract(resp_json, extract_expr)
        # 4、保存到环境变量（后续用 ${user_id} 引用）
        self.save_env_variable(var_name, extracted_value)
        self.info_log(f"数据提取成功：{var_name} = {extracted_value}")
        # 5、记录提取结果
        self._extract_results.append({
            "var_name": var_name,
            "extract_expr": extract_expr,
            "value": extracted_value,
        })

    def __assert_data(self, assertion, response):
        """
        断言响应数据
        :param assertion: 断言规则，格式                        {
                "type": "相等",
                "field": "$.msg",
                "expected": "登陆成功"
            }
        :param response: requests.Response 对象
        """
        # 1、解构元组
        assertion_type = assertion.get("type")
        extract_expr = assertion.get("field")
        assertion_content = assertion.get("expected")
        # ★ 核心修复：对 expected 字段进行变量替换
        # 支持格式：${var_name} → 替换为实际值
        if isinstance(assertion_content, str) and "${" in assertion_content:
            self.info_log(f"检测到断言期望值包含变量引用：{assertion_content}")
            assertion_content = self.replace_data(assertion_content)
            self.info_log(f"变量替换后期望值：{assertion_content}")
        # 2、将响应体解析为 JSON/dict
        # ★ 新增：特殊字段处理 —— status_code 直接取 HTTP 状态码
        if extract_expr == "status_code":
            extracted_value = response.status_code
            self.info_log(f"检测到断言字段为 status_code，直接获取 HTTP 状态码：{extracted_value}")
        else:
            try:
                resp_json = response.json()
            except Exception:
                resp_json = {}
                self.error_log("响应体非JSON格式，无法提取数据")
            # 3、通过 JSONPath 提取值
            extracted_value = self.json_extract(resp_json, extract_expr)
            # 4、断言
        self.assertion(assertion_type, assertion_content, extracted_value)

    # 遍历所有assertions项，依次执行断言
    def __execute_assertions(self, data, response):
        # ★ 新增：收集断言错误列表
        assertion_errors = []
        if data.get("assertions"):
            total = len(data.get("assertions"))
            self.info_log(f"========== 开始执行断言（共 {total} 个） ==========")
            for idx, assertion in enumerate(data.get("assertions"), start=1):
                field = assertion.get("field", "未知")
                expected = assertion.get("expected", "未知")
                assert_type = assertion.get("type", "eq")
                passed = True
                try:
                    self.info_log(f"  [{idx}/{total}] 执行断言: field={field}, expected={expected}")
                    self.__assert_data(assertion, response)
                    self.info_log(f"  [{idx}/{total}] ✅ 断言通过: {field}")
                except AssertionError as e:
                    passed = False
                    self.error_log(f"  [{idx}/{total}] ❌ 断言失败: {field} — {e}")
                    assertion_errors.append({
                        "index": idx,
                        "field": field,
                        "expected": expected,
                        "error_type": "ASSERTION_FAILED",
                        "message": str(e)
                    })
                # 记录断言结果
                self._assert_results.append({
                    "field": field,
                    "type": assert_type,
                    "expected": expected,
                    "passed": passed,
                })
            # 所有断言执行完毕后输出汇总
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

            # ★ 如果有失败的断言，最终抛出一个聚合的 AssertionError
            if assertion_errors:
                fail_details = "; ".join(
                    f"[{err['field']}] {err['message']}" for err in assertion_errors
                )
                raise AssertionError(
                    f"用例 [{data.get('title')}] 断言失败："
                    f"通过 {passed_count}/{total}，"
                    f"失败详情 → {fail_details}"
                )

    def __execute_preconditions(self, steps, depth=1,failure_mode="continue"):
        """
        递归执行多级前置接口（深度优先 DFS）
        容错模式：单步失败记录错误，不影响后续步骤执行
        """
        if not steps:
            return

        prefix = "  " * depth
        # 前置步骤整体状态记录
        precondition_errors = []  # 收集所有前置步骤的错误

        for step in steps:
            title = step.get('title', '未命名前置')
            # failure_mode = step.get('on_failure', 'continue')  # 默认容错继续

            self.info_log(f"{prefix}▶ [L{depth}] 执行前置步骤: {title}")

            # ★ 递归子前置（也带容错）
            if step.get("preconditions"):
                self.info_log(f"{prefix}  [L{depth}] '{title}' 有下级前置，先递归执行")
                child_errors = self.__execute_preconditions(
                    step.get("preconditions"), depth + 1
                )
                if child_errors:
                    precondition_errors.extend(child_errors)
                    self.warning_log(f"{prefix}  [L{depth}] 子前置存在 {len(child_errors)} 个错误")
                self.info_log(f"{prefix}  [L{depth}] '{title}' 的下级前置完成，开始执行自身")

            # ★ 单步 try-except 容错包裹
            step_error = None
            response= None
            try:
                self.__setup_script(step)
                response = self.__send_request(step)

                # 数据提取
                if step.get("extract"):
                    for extract in step.get("extract"):
                        self.__extract_data(extract, response)

                # 断言(批量执行所有的断言)
                self.__execute_assertions(step, response)

            except AssertionError as e:
                self.warning_log(f"{prefix}❌ [L{depth}] 存在断言失败: {title} — {e}")

            except Exception as e:
                step_error = {
                    "level": depth,
                    "step_title": title,
                    "error_type": "EXECUTION_ERROR",
                    "message": str(e)
                }
                self.error_log(f"{prefix}❌ [L{depth}] 前置执行异常: {title} — {e}")

            finally:
            # 确保 teardown 在任何情况下都执行（如果 setup 已执行成功）
            # 注意：如果 __setup_script 都失败了，teardown 不应再执行
                self.__teardown_script(step, response)
                self.info_log(f"{prefix}✅ [L{depth}] 前置完成: {title}")

            # ★ 根据 on_failure 决定是否继续
            if step_error:
                precondition_errors.append(step_error)
                if failure_mode == "stop":
                    self.error_log(f"{prefix}🛑 [L{depth}] 配置 on_failure=stop，中止执行")
                    # 将收集到的所有错误抛出给上层或 perform 处理
                    raise PreconditionChainError(precondition_errors)
            # 如果是 continue 模式，即使出错也继续下一个步骤
            # 但注意：extract 失败意味着某些变量可能未设置，
            # 后续步骤引用这些变量时会得到空值

        return precondition_errors  # 返回本层所有错误供上级参考


    def perform(self, data):
        """执行用例"""
        start_time = time.time()
        self._precondition_errors = []  # 记录前置错误（供结果查询）
        self._extract_results = []      # 重置提取结果
        self._assert_results = []       # 重置断言结果
        case_name = data.get('title')
        has_failure = False  # ★ 新增：失败标志位
        try:
            # 1、判断是否有前置步骤 preconditions（支持多级嵌套递归）
            if data.get("preconditions"):
                self.info_log("========== 开始执行前置步骤链 ==========")
                self._precondition_errors = self.__execute_preconditions(
                    data.get("preconditions"), depth=1
                )
                if self._precondition_errors:
                    has_failure = True  # ★ 前置有失败
                    self.warning_log(
                        f"前置步骤链完成，但有 {len(self._precondition_errors)} 个步骤失败，"
                        f"继续执行主用例"
                    )
                else:
                    self.info_log("========== 前置步骤链全部通过 ==========")
            # 2、执行测试用例（前置 - 测试用例）
            self.info_log(f"开始执行用例步骤:{case_name}")
            self.__setup_script(data)
            response = self.__send_request(data)
            # 3、判断是否有数据提取
            if data.get("extract"):
                for extract in data.get("extract"):
                    self.__extract_data(extract, response)
            # ★ 4、断言部分 —— 容错模式：全部执行完再汇总结果
            self.__execute_assertions(data,response)
            # 5、执行后置步骤
            self.__teardown_script(data, response)
            self.info_log(f"结束执行用例步骤:{case_name}")
            # ★ 新增：try块结束时检查前置是否有失败
            if has_failure:
                # 前置有断言/执行失败，但主用例可能通过了
                # 需要通知上层这个用例整体不算成功
                raise AssertionError(
                    f"[{case_name}] 用例执行完成但存在 {len(self._precondition_errors)} 个前置失败"
                )

        except AssertionError as e:
            # ★ 断言失败 —— 不吞掉
            has_failure = True
            self.warning_log(f"⚠️ 用例 [{case_name}] 存在失败断言")
            # 让异常继续传播给上层
            raise  # ← 关键：重新抛出！

        except Exception as e:
            step_error = {
                "level": 0,
                "step_title": case_name,
                "error_type": "EXECUTION_ERROR",
                "message": str(e)
            }
            self.error_log(f" ❌用例执行异常: {case_name} — {e}")
            raise  # 其他异常也要继续传播
        finally:
            end_time = time.time()
            elapsed_time = end_time - start_time
            self.elapsed_ms = "{} ms".format(int(elapsed_time * 1000))
            self.info_log(f"✅ 用例执行完成:{case_name}")

    def save_env_variable(self, key, value):
        """保存测试运行环境变量"""
        self.info_log(f"保存（临时）环境变量：{key} = {value}")
        self.env[key] = value
        # 运行期间：局部变量也写入 ENV["envs"]，使其在同一批用例中可跨脚本传递
        try:
            envs = ENV.get("envs")
            if isinstance(envs, dict):
                envs[key] = value
        except Exception:
            # 防御性兜底：不影响当前用例执行
            pass

    def del_evn_variable(self, key):
        """删除测试运行环境变量"""
        self.info_log(f"删除（临时）环境变量：{key}")
        del self.env[key]

    def save_global_variable(self, key, value):
       """保存测试运行环境的全局变量"""
       self.info_log(f"保存全局变量：{key} = {value}")
       envs = ENV.get("envs")
       if isinstance(envs, dict):
           envs[key] = value
       # 记录本次运行中修改/新增的全局变量，便于上层平台同步到“调试运行变量”
       try:
           debug_updates = ENV.get("debug_updates")
           if isinstance(debug_updates, dict):
               debug_updates[key] = value
       except Exception:
           # 防御性兜底：不影响当前用例执行
           pass

    def del_global_variable(self, key):
        """删除测试运行环境的全局变量"""
        self.info_log(f"删除全局变量：{key}")
        envs = ENV.get("envs")
        if isinstance(envs, dict) and key in envs:
            del envs[key]
        try:
            debug_deletes = ENV.get("debug_deletes")
            if isinstance(debug_deletes, list) and key not in debug_deletes:
                debug_deletes.append(key)
        except Exception:
            pass

    def get_env_variable(self, key, default=None):
        """
        获取临时变量（局部变量）
        优先从当前用例的 self.env 中读取，可选提供默认值
        """
        self.info_log(f"获取（临时）环境变量：{key}")
        return self.env.get(key, default)

    def get_global_variable(self, key, default=None):
        """
        获取环境变量（全局变量/环境变量）
        从 ENV['envs'] 中读取，可选提供默认值
        """
        self.info_log(f"获取环境变量：{key}")
        envs = ENV.get("envs")
        if isinstance(envs, dict):
            return envs.get(key, default)
        return default

    def json_extract(self,obj,ext):
        """通过jsonpath提取一个json数据"""
        self.info_log("----通过jsonpath提取单个数据---")
        res = jsonpath(obj, ext)
        value = res[0] if res else ""
        return value

    def json_extract_list(self,obj,ext):
        """通过jsonpath提取一组json数据"""
        self.info_log("----通过jsonpath提取一组数据---")
        res = jsonpath(obj, ext)
        value = res if res else []
        return value

    def re_extract(self,obj,ext):
        """
        通过正则提取一个数据
        obj: 响应的json数据
        ext: 匹配的正则表达式
        """
        self.info_log("----通过正则提取数据---")
        # 1、判断响应是否为字符串
        if not isinstance(obj,str):
            obj = str(obj)
        # 2、提取匹配正则表达式的第一个数据
        res = re.search(ext,obj)
        value = res.group(1) if res else ""
        return value

    def re_extract_list(self,obj,ext):
        """
        通过正则提取一组数据
        obj: 响应的json数据
        ext: 匹配的正则表达式
        """
        self.info_log("----通过正则提取一组数据---")
        # 1、判断响应是否为字符串
        if not isinstance(obj,str):
            obj = str(obj)
        # 2、提取匹配正则表达式的所有数据
        res = re.findall(ext,obj)
        value = res if res else []
        return value

    def assertion(self,method,expect,actual):
        """
        :param method: 断言比较的方式
        :param expect: 断言的期望结果
        :param actual: 断言的实际结果
        :return:
        """
        # 1、断言的方法（支持中英文关键字）
        method_map = {
            # 相等
            "相等": lambda a,b: a == b,
            "equals": lambda a,b: a == b,
            "eq": lambda a,b: a == b,
            "==": lambda a,b: a == b,
            # 相等忽略大小写
            "相等忽略大小写": lambda a, b: a.lower() == b.lower(),
            "equals_ignore_case": lambda a, b: a.lower() == b.lower(),
            "eq_ignore_case": lambda a, b: a.lower() == b.lower(),
            # 不相等
            "不相等":  lambda a,b: a != b,
            "not_equals": lambda a,b: a != b,
            "ne": lambda a,b: a != b,
            "!=": lambda a,b: a != b,
            # 包含
            "包含": lambda a,b: a in b,
            "contains": lambda a,b: a in b,
            "in": lambda a,b: a in b,
            # 不包含
            "不包含": lambda a,b: a not in b,
            "not_contains": lambda a,b: a not in b,
            "not_in": lambda a,b: a not in b,
            # 大于
            "大于": lambda a,b: a > b,
            "greater_than": lambda a,b: a > b,
            "gt": lambda a,b: a > b,
            ">": lambda a,b: a > b,
            # 小于
            "小于": lambda a,b: a < b,
            "less_than": lambda a,b: a < b,
            "lt": lambda a,b: a < b,
            "<": lambda a,b: a < b,
            # 大于等于
            "大于等于": lambda a,b: a >= b,
            "greater_than_or_equals": lambda a,b: a >= b,
            "ge": lambda a,b: a >= b,
            ">=": lambda a,b: a >= b,
            # 小于等于
            "小于等于": lambda a,b: a <= b,
            "less_than_or_equals": lambda a,b: a <= b,
            "le": lambda a,b: a <= b,
            "<=": lambda a,b: a <= b,
            # 正则匹配
            "正则匹配": lambda a,b: re.search(a,b),
            "regex_match": lambda a,b: re.search(a,b),
            "regex": lambda a,b: re.search(a,b),
            "match": lambda a,b: re.search(a,b)
        }
        # ★ 新增：智能类型兼容处理
        # 场景：expect="200"(str), actual=200(int) → 自动转一致后再比较
        expect, actual = self._normalize_for_compare(expect, actual)
        # 2、断言操作
        assert_fun = method_map.get(method)
        if assert_fun is None:
            raise Exception("不支持的断言方法")
        else:
            self.debug_log(f"断言比较方法是：{method}")
            self.debug_log(f"预期结果是：{expect}")
            self.debug_log(f"实际结果是：{actual}")
        try:
            assert assert_fun(expect,actual)
        except AssertionError:
            self.error_log(f"断言失败，实际结果({actual}) 不满足({method}) 期望结果({expect})")
            raise AssertionError(f"断言失败，实际结果({actual}) 不满足({method}) 期望结果({expect})")
        else:
            self.info_log(f"断言成功，实际结果({actual}) 满足({method}) 期望结果({expect})")

    def _normalize_for_compare(self, expect, actual):
        """
        智能类型归一化，解决 str/int/float 类型不一致导致的断言失败
        """
        # 如果两者类型已经相同，直接返回
        if type(expect) == type(actual):
            return expect, actual

        # 尝试将 expect 转为 actual 的类型
        try:
            if isinstance(actual, (int, float)) and isinstance(expect, str):
                # actual 是数字, expect 是字符串 → 尝试将 expect 转为数字
                if '.' in str(expect):
                    return float(expect), actual
                else:
                    return int(expect), actual
            elif isinstance(expect, (int, float)) and isinstance(actual, str):
                # expect 是数字, actual 是字符串 → 尝试将 actual 转为数字
                if '.' in str(actual):
                    return expect, float(actual)
                else:
                    return expect, int(actual)
        except (ValueError, TypeError):
            pass  # 转换失败，保持原值

        return expect, actual