import re


class AssertionEngine:
    """断言引擎：支持中英文关键字、智能类型归一化"""

    METHOD_MAP = {
        # 相等
        "相等": lambda a, b: a == b,
        "equals": lambda a, b: a == b,
        "eq": lambda a, b: a == b,
        "==": lambda a, b: a == b,
        # 相等忽略大小写
        "相等忽略大小写": lambda a, b: a.lower() == b.lower(),
        "equals_ignore_case": lambda a, b: a.lower() == b.lower(),
        "eq_ignore_case": lambda a, b: a.lower() == b.lower(),
        # 不相等
        "不相等": lambda a, b: a != b,
        "not_equals": lambda a, b: a != b,
        "ne": lambda a, b: a != b,
        "!=": lambda a, b: a != b,
        # 包含
        "包含": lambda a, b: a in b,
        "contains": lambda a, b: a in b,
        "in": lambda a, b: a in b,
        # 不包含
        "不包含": lambda a, b: a not in b,
        "not_contains": lambda a, b: a not in b,
        "not_in": lambda a, b: a not in b,
        # 大于
        "大于": lambda a, b: a > b,
        "greater_than": lambda a, b: a > b,
        "gt": lambda a, b: a > b,
        ">": lambda a, b: a > b,
        # 小于
        "小于": lambda a, b: a < b,
        "less_than": lambda a, b: a < b,
        "lt": lambda a, b: a < b,
        "<": lambda a, b: a < b,
        # 大于等于
        "大于等于": lambda a, b: a >= b,
        "greater_than_or_equals": lambda a, b: a >= b,
        "ge": lambda a, b: a >= b,
        ">=": lambda a, b: a >= b,
        # 小于等于
        "小于等于": lambda a, b: a <= b,
        "less_than_or_equals": lambda a, b: a <= b,
        "le": lambda a, b: a <= b,
        "<=": lambda a, b: a <= b,
        # 正则匹配
        "正则匹配": lambda a, b: re.search(a, b),
        "regex_match": lambda a, b: re.search(a, b),
        "regex": lambda a, b: re.search(a, b),
        "match": lambda a, b: re.search(a, b),
    }

    @staticmethod
    def _normalize_for_compare(expect, actual):
        """
        智能类型归一化，解决 str/int/float 类型不一致导致的断言失败
        """
        if type(expect) == type(actual):
            return expect, actual

        try:
            if isinstance(actual, (int, float)) and isinstance(expect, str):
                if '.' in str(expect):
                    return float(expect), actual
                else:
                    return int(expect), actual
            elif isinstance(expect, (int, float)) and isinstance(actual, str):
                if '.' in str(actual):
                    return expect, float(actual)
                else:
                    return expect, int(actual)
        except (ValueError, TypeError):
            pass

        return expect, actual

    @classmethod
    def assert_value(cls, method, expect, actual, debug_log=None, info_log=None, error_log=None):
        """
        执行断言
        :param method: 断言比较方式
        :param expect: 预期结果
        :param actual: 实际结果
        """
        expect, actual = cls._normalize_for_compare(expect, actual)

        assert_fun = cls.METHOD_MAP.get(method)
        if assert_fun is None:
            raise Exception("不支持的断言方法")
        else:
            if debug_log:
                debug_log(f"断言比较方法是：{method}")
                debug_log(f"预期结果是：{expect}")
                debug_log(f"实际结果是：{actual}")
        try:
            assert assert_fun(expect, actual)
        except AssertionError:
            msg = f"断言失败，实际结果({actual}) 不满足({method}) 期望结果({expect})"
            if error_log:
                error_log(msg)
            raise AssertionError(msg)
        else:
            if info_log:
                info_log(f"断言成功，实际结果({actual}) 满足({method}) 期望结果({expect})")
