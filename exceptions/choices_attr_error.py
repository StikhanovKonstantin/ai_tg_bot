class AttrChoicesError(Exception):
    """
    Исключение - аттрибут `choices` класса `list` либо отсутствует,
    либо имеет другой тип данных.
    """

    def __str__(self):
        return (
            'Ошибка: аттрибут `choices` либо отсутствует в ответе, '
            'либо тип данных не равен `list`.'
        )


class AttrChoicesEmptyError(Exception):
    """Исключение - аттрибут `choices` класса `list` пустой."""

    def __str__(self):
        return 'Ошибка: аттрибут choices пуст.'
