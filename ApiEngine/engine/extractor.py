import re
from jsonpath import jsonpath


class Extractor:
    """数据提取器：JSONPath + 正则"""

    @staticmethod
    def json_extract(obj, ext):
        """通过jsonpath提取一个json数据"""
        res = jsonpath(obj, ext)
        value = res[0] if res else ""
        return value

    @staticmethod
    def json_extract_list(obj, ext):
        """通过jsonpath提取一组json数据"""
        res = jsonpath(obj, ext)
        value = res if res else []
        return value

    @staticmethod
    def re_extract(obj, ext):
        """
        通过正则提取一个数据
        obj: 响应的json数据
        ext: 匹配的正则表达式
        """
        if not isinstance(obj, str):
            obj = str(obj)
        res = re.search(ext, obj)
        value = res.group(1) if res else ""
        return value

    @staticmethod
    def re_extract_list(obj, ext):
        """
        通过正则提取一组数据
        obj: 响应的json数据
        ext: 匹配的正则表达式
        """
        if not isinstance(obj, str):
            obj = str(obj)
        res = re.findall(ext, obj)
        value = res if res else []
        return value
