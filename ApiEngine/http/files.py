import os


class FileHandler:
    """文件上传参数转换"""

    @staticmethod
    def convert_files(param, log_func=None):
        """
        递归转换文件参数
        :param param: 文件参数 dict
        :param log_func: 日志函数
        :return: (converted_dict, opened_files_list)
        """
        if not isinstance(param, dict):
            return param, []

        local_opened = []
        converted = {}

        for field, val in param.items():
            if isinstance(val, dict) and "path" in val:
                # 格式 A: {"path": "...", "name": "..."}
                try:
                    file_path = val["path"]
                    filename = val.get("name") or os.path.basename(file_path)
                    f = open(file_path, "rb")
                    local_opened.append(f)
                    if log_func:
                        log_func(f"成功加载文件: {field} = {filename}")
                    converted[field] = (filename, f)
                except Exception as e:
                    if log_func:
                        log_func(f"文件加载失败 [{val.get('path')}]: {e}")

            elif isinstance(val, list):
                # 格式 C: 列表格式（单字段多文件）
                file_list = []
                for item in val:
                    if isinstance(item, tuple) and len(item) == 2:
                        file_list.append(item)
                    elif isinstance(item, dict) and "path" in item:
                        try:
                            fp = item["path"]
                            fn = item.get("name") or os.path.basename(fp)
                            f = open(fp, "rb")
                            local_opened.append(f)
                            file_list.append((fn, f))
                        except Exception as e:
                            if log_func:
                                log_func(f"列表项文件加载失败 [{item.get('path')}]: {e}")
                    else:
                        file_list.append(item)
                if file_list:
                    converted[field] = file_list
            else:
                # 格式 B: 直接传值/元组
                converted[field] = val

        return converted if converted else None, local_opened
