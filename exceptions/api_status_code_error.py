from http import HTTPStatus


class ApiStatusCodeError(Exception):
    """Исключение: статус-код ответа от API-Deepseek не равен 200."""

    def __init__(self, status_code: int) -> None:
        self.status_code = status_code

    def __str__(self) -> str:
        return (
            f'Статус-код ответа отличен от {HTTPStatus.OK}. '
            f'Статус код: {self.status_code}.'
        )
