import re
import ast
import logging

from ApiEngine.infra import global_func

logger = logging.getLogger("ApiEngine")


class Replacer:
    """变量替换引擎：处理 ${var} 语法和函数调用"""

    def __init__(self, shared_env, local_env, log_func=None):
        """
        :param shared_env: TestRunner 级共享环境（包含 envs, base_url 等）
        :param local_env: 用例级临时变量 dict（需保持引用，运行时会动态写入）
        :param log_func: 日志函数
        """
        self._shared_env = shared_env
        self._local_env = local_env
        self._log = log_func or (lambda *a: None)

    def replace_data(self, data):
        """替换测试用例中的变量数据"""
        pattern = r"\${(.+?)}"
        data_str = str(data)
        self._log("替换数据原始内容：", data_str)

        max_loop = 100
        loop_count = 0
        has_unresolved = True

        while has_unresolved and loop_count < max_loop:
            loop_count += 1
            original_str = data_str

            for match_data in list(re.finditer(pattern, data_str)):
                full_match = match_data.group()
                key = match_data.group(1)

                self._log(f"第{loop_count}次匹配：{full_match} → 提取内容：{key}")

                # 步骤1：从临时变量 self.env 取值
                value = self._local_env.get(key)
                # 步骤2：从全局变量 shared_env["envs"] 取值
                if value is None:
                    value = self._shared_env.get("envs", {}).get(key)
                # 步骤3：仍无值 → 直接使用 key 作为值（可能是函数调用）
                if value is None:
                    self._log(f"变量 {key} 无临时/全局值，尝试作为函数调用处理")
                    value = key

                # 执行函数（支持带参数）
                value_after_exec = self.execute_function_if_exists(value)
                data_str = data_str.replace(full_match, str(value_after_exec))
                self._log(f"替换结果：{full_match} → {value_after_exec}")

            has_unresolved = re.search(pattern, data_str) is not None
            if original_str == data_str:
                has_unresolved = False

        if loop_count >= max_loop:
            self._log(f"变量替换达到最大循环次数 {max_loop}，强制退出（可能存在循环引用）")

        # 还原数据类型
        try:
            return ast.literal_eval(data_str)
        except (ValueError, SyntaxError):
            self._log(f"数据 {data_str} 无法还原类型，返回字符串格式")
            return data_str

    def execute_function_if_exists(self, value):
        """
        支持带参数函数调用，增加异常兜底（避免返回None）
        """
        if not isinstance(value, str):
            return value

        func_pattern = r"^(\w+)\((.*)\)$"
        func_match = re.match(func_pattern, value.strip())
        if not func_match:
            return value

        func_name = func_match.group(1)
        func_args_str = func_match.group(2).strip()

        try:
            func = getattr(global_func, func_name)
            if not callable(func):
                logger.warning(f"{func_name} 不是可调用函数，返回原格式")
                return value
        except AttributeError:
            logger.warning(f"全局函数 {func_name} 不存在，返回原格式")
            return value

        # 解析参数
        func_args = []
        if func_args_str:
            try:
                func_args = ast.literal_eval(f"[{func_args_str}]")
            except Exception as e:
                logger.error(f"解析函数 {func_name} 参数失败：{str(e)}，返回原格式")
                return value

        # 执行函数
        logger.info(f"执行函数 {func_name}，参数：{func_args}，参数类型：{[type(x) for x in func_args]}")
        try:
            func_result = func(*func_args)
            logger.info(f"函数 {func_name} 执行结果：{func_result}，类型：{type(func_result)}")
            return func_result
        except Exception as e:
            logger.error(f"执行 {func_name} 抛出异常：{str(e)}", exc_info=True)
            return value
