class APIError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        param: str | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.param = param
        super().__init__(message)


class AniDBIDNotFoundError(APIError):
    def __init__(self, anidb_id: int) -> None:
        super().__init__(
            status_code=404,
            code="ANIDB_ID_NOT_FOUND",
            message=f"AniDB ID {anidb_id} was not found in the local titles dump.",
            param="anidb_id",
        )


class DumpNotReadyError(APIError):
    def __init__(self) -> None:
        super().__init__(
            status_code=503,
            code="DUMP_NOT_READY",
            message="The AniDB titles dump is still loading. Please retry shortly.",
        )
