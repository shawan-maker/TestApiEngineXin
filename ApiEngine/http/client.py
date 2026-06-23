import requests
from urllib.parse import urlencode

from ApiEngine.http.files import FileHandler


class HttpClient:
    """HTTP 请求客户端"""

    def __init__(self):
        self.session = requests.Session()

    def build_request(self, data, shared_env, replacer):
        """
        构建请求参数
        :param data: 用例数据 dict
        :param shared_env: 共享环境数据
        :param replacer: 变量替换器实例
        :return: 构建好的请求参数 dict
        """
        request_data = {}

        # 1、处理请求url
        url = data.get("interface").get("url")
        if url.startswith("http"):
            request_data["url"] = url
        else:
            request_data["url"] = shared_env.get("base_url") + url
        request_data["method"] = data.get("interface").get("method")

        # 2、处理请求头（使用副本，避免污染全局 shared_env）
        request_data["headers"] = dict(shared_env.get("headers") or {})
        request_data["headers"].update(data.get("headers") or {})

        # 3、处理请求参数
        request_data["params"] = data.get("request").get("params")
        content_type = request_data["headers"].get("Content-Type", "")
        _req = data.get("request") or {}
        if "application/json" in content_type:
            request_data["json"] = _req.get("json") or _req.get("data")
        if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
            request_data["data"] = _req.get("data") or _req.get("json")
        if "multipart/form-data" in content_type:
            request_data["files"] = data.get("request").get("files")

        # 4、替换请求中的变量（files 保持原值，避免 open 文件对象被 eval 破坏）
        files_raw = request_data.get("files")
        request_data_for_replace = dict(request_data)
        if "files" in request_data_for_replace:
            request_data_for_replace.pop("files")
        request_data = replacer.replace_data(request_data_for_replace)
        if files_raw is not None:
            request_data["files"] = files_raw

        return request_data

    def send(self, request_data, log_func=None):
        """
        发送 HTTP 请求
        :param request_data: 构建好的请求参数
        :param log_func: 日志函数
        :return: response 对象和请求信息
        """
        files_param = request_data.get("files")
        opened_files = []

        # 文件转换
        if isinstance(files_param, dict):
            files_param, new_opened = FileHandler.convert_files(files_param, log_func)
            opened_files.extend(new_opened)

        try:
            response = self.session.request(
                method=request_data.get("method"),
                url=request_data.get("url"),
                headers=request_data.get("headers"),
                params=request_data.get("params"),
                data=request_data.get("data"),
                json=request_data.get("json"),
                files=files_param,
                allow_redirects=False
            )

            # 拼接完整URL（包含params参数）
            full_url = request_data.get("url", "")
            params = request_data.get("params")
            if params:
                query_string = urlencode(params)
                full_url = f"{full_url}?{query_string}"

            return response, {
                "url": full_url,
                "method": request_data.get("method", ""),
                "request_headers": request_data.get("headers", {}),
                "request_body": response.request.body,
                "status_code": response.status_code,
                "response_headers": response.headers,
                "response_body": response.text,
            }
        finally:
            for f in opened_files:
                try:
                    f.close()
                except Exception:
                    pass
            if opened_files and log_func:
                log_func(f"已关闭 {len(opened_files)} 个文件句柄")

    def close(self):
        """关闭 session"""
        self.session.close()
