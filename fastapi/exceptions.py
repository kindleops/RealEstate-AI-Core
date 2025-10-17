class HTTPException(Exception):
    """Simplified HTTPException that mimics FastAPI's interface."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
