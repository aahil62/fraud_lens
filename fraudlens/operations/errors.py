"""Errors the operational API turns into HTTP responses (see api/routes/operations.py)."""


class OperationError(ValueError):
    def __init__(self, detail, *, status_code=400, **fields):
        super().__init__(detail)
        self.status_code = status_code
        self.payload = {"detail": detail, **fields}


class ConflictError(OperationError):
    def __init__(self, detail, **fields):
        super().__init__(detail, status_code=409, **fields)


class NotFoundError(ValueError):
    pass
