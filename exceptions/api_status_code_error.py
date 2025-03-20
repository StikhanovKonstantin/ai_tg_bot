class ApiStatusCodeError(Exception):
    """Исключение: статус-код ответа от API-Deepseek не равен 200."""

    def __str__(self):
        return 'Ошибка: статус-код ответа от API-Deepseek не равен 200.'
