class DomainError(Exception):
    """Erro de regra de negócio. A mensagem é exibida ao usuário (em português)."""

    status_code: int = 400

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFound(DomainError):
    status_code = 404


class Forbidden(DomainError):
    status_code = 403


class Unauthorized(DomainError):
    status_code = 401


class Conflict(DomainError):
    """Regra de negócio violada (andar lotado, vaga ocupada...)."""

    status_code = 409


class InvalidInput(DomainError):
    status_code = 422
