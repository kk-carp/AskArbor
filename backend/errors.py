class ServiceUnavailableError(RuntimeError):
    """系统依赖未就绪或不可用。"""


class UpstreamServiceError(RuntimeError):
    """上游模型服务调用失败。"""
