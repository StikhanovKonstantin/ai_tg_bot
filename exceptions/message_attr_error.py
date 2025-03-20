class AttrMessageError(Exception):
    """Исключение - аттрибут `message` отсутсвует."""

    def __str__(self):
        return 'Ошибка: атрибут `message` отсутсвует в ответе.'
