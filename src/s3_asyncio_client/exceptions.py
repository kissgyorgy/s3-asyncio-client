class S3Error(Exception):
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        error_code: str | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

    def __str__(self) -> str:
        if self.status_code and self.error_code:
            return f"{self.error_code} ({self.status_code}): {self.message}"
        elif self.status_code:
            return f"HTTP {self.status_code}: {self.message}"
        return self.message


class S3ClientError(S3Error):
    pass


class S3ServerError(S3Error):
    pass


class S3NotFoundError(S3ClientError):
    def __init__(self, message: str = "The specified resource was not found"):
        super().__init__(message, status_code=404, error_code="NoSuchKey")


class S3AccessDeniedError(S3ClientError):
    def __init__(self, message: str = "Access denied"):
        super().__init__(message, status_code=403, error_code="AccessDenied")


class S3InvalidRequestError(S3ClientError):
    def __init__(self, message: str = "Invalid request"):
        super().__init__(message, status_code=400, error_code="InvalidRequest")
