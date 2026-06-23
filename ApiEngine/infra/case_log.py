import time
import logging


class CaseLogHandler:
    """用例日志处理类"""
    _logger = logging.getLogger("ApiEngine")

    def save_log(self, msg, level):
        """保存日志"""
        ts = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time()))
        msg = ts + " | " + msg
        # 1、判断当前实例是否有日志属性
        if not hasattr(self, "log_data"):
            setattr(self, "log_data", [])
        # 2、将日志数据保存到属性中
        getattr(self, "log_data").append((level, msg))
        # 3、保留 print 输出（兼容上层 stdout 捕获）
        print((level, msg))
        # 4、增量：标准 logging（上层可按需配置 handler）
        log_level = getattr(logging, level, logging.INFO)
        self._logger.log(log_level, msg)

    def print_log(self, *args):
        """记录print日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg, "PRINT")

    def debug_log(self, *args):
        """记录debug日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg, "DEBUG")

    def info_log(self, *args):
        """记录info日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg, "INFO")

    def warning_log(self, *args):
        """记录warning日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg, "WARNING")

    def error_log(self, *args):
        """记录error日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg, "ERROR")

    def critical_log(self, *args):
        """记录critical日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg, "CRITICAL")
