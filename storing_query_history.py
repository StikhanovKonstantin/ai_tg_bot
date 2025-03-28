def update_user_history(
        chat_id: int, dialogues: dict[str, list[dict[str, str]]],
        message_text: str
) -> None:
    """
    Обновляет историю запросов пользователя, для передачи
    всего контекста в запросе к Deepseek.
    """
    if chat_id not in dialogues:
        dialogues[chat_id] = []
    dialogues[chat_id].append({'role': 'user', 'content': message_text})


def full_context(
        chat_id: int, dialogues: dict[str, list[dict[str, str]]]
) -> list[dict[str, str]]:
    """Подготавливает весь контекст диалога для отправки запроса к Deepseek."""
    if chat_id in dialogues:
        messages = dialogues[chat_id]
    else:
        messages = []
    return messages


def update_deepseek_history(
        chat_id: int, dialogues: dict[str, list[dict[str, str]]],
        response: str
) -> None:
    """Обновляет историю ответов от нейросети Deepseek."""
    if chat_id in dialogues:
        dialogues[chat_id].append({'role': 'system', 'content': response})