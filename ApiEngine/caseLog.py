class CaseLogHandler:
    """用例日志处理类"""
    def save_log(self,msg,level):
        """保存日志"""
        # 1、判断当前实例是否有日志属性
        if not hasattr(self,"log_data"):
            setattr(self,"log_data",[])
        # 2、将日志数据保存到属性中
        getattr(self,"log_data").append((level,msg))
        print((level,msg))

    def print_log(self,*args):
        """记录debug日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg,"PRINT")

    def debug_log(self,*args):
        """记录debug日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg,"DEBUG")

    def info_log(self,*args):
        """记录info日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg,"INFO")

    def warning_log(self,*args):
        """记录warning日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg,"WARNING")

    def error_log(self,*args):
        """记录error日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg,"ERROR")

    def critical_log(self,*args):
        """记录critical日志"""
        msg = " ".join([str(i) for i in args])
        self.save_log(msg,"CRITICAL")


class PreconditionChainError(Exception):
    """前置条件链执行错误（用于 stop 模式中止）"""
    def __init__(self, errors):
        self.errors = errors  # 所有收集到的步骤错误
        super().__init__(f"前置条件链中止，共 {len(errors)} 个错误")
