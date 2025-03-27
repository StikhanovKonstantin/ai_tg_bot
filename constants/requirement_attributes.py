"""В файле хранятся все необходимые атрибут из ответа Deepseek."""


# Словарь, содержащий необходимые атрибуты,
# учитывая вложенность этих атрибутов.
REQUIREMENT_ATTRS: dict[str, str] = {
    'response': 'choices',
    'choices': 'message',
    'message': 'content'
}
