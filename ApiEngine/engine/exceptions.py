class PreconditionChainError(Exception):
    """前置条件链执行错误（用于 stop 模式中止）"""
    def __init__(self, errors):
        self.errors = errors
        super().__init__(f"前置条件链中止，共 {len(errors)} 个错误")
