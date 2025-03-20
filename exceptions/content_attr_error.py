class AttrContentError(Exception):
    """
    Исключение: атрибут `content` класса `str` либо отсутвует,
    либо имеет другой тип данных.
    """

    def __str__(self):
        return (
            'Ошибка: аттрибут `content` либо отсутсвует в ответе, '
            'либо его тип данных не соответсвует классу `str`.'
        )


class AttrContentEmptyError(Exception):
    """Исключение: аттрибут `content` пуст."""

    def __str__(self):
        return 'Ошибка: аттрибут `content` пуст.'
