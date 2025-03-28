import os
import sys
from typing import Optional
import logging
from http import HTTPStatus
from requests.exceptions import RequestException

import openai
from telebot import TeleBot
from telebot.types import Message
from telebot.apihelper import ApiTelegramException
from openai import OpenAI
from openai.types.chat.chat_completion import ChatCompletion
from dotenv import load_dotenv

from exceptions.choices_attr_error import (
    AttrChoicesError, AttrChoicesEmptyError
)
from exceptions.message_attr_error import AttrMessageError
from exceptions.content_attr_error import (
    AttrContentError, AttrContentEmptyError
)
from exceptions.clear_dialogue_error import ClearContextError
from exceptions.api_status_code_error import ApiStatusCodeError
from constants.numeric_constants import MESSAGE_LENGTH_LIMIT
from constants.message_constants import (
    WELCOME_MESSAGE, SEND_MESSAGE_ERROR, CLEAR_CONTEXT_MESSAGE,
    CLEAR_CONTEXT_ERROR_MESSAGE
)
from constants.requirement_attributes import REQUIREMENT_ATTRS
from storing_query_history import (
    update_user_history, update_deepseek_history, full_context
)


load_dotenv()

logger = logging.getLogger(__name__)

# Константы - токены, url - адрес Deepseek.
DEEPSEEK_TOKEN: Optional[str] = os.getenv('DEEPSEEK_TOKEN')
DEEPSEEK_URL: Optional[str] = os.getenv('DEEPSEEK_URL')
TELEGRAM_TOKEN: Optional[str] = os.getenv('TELEGRAM_TOKEN')

bot = TeleBot(token=TELEGRAM_TOKEN)

# Создаем клиент для работы с Deepseek.
client = OpenAI(
    api_key=DEEPSEEK_TOKEN,
    base_url=DEEPSEEK_URL
)

# Словарь, хранящий в себе историю запросов пользователя,
# а также ответы Deepseek.
dialogues: dict[str, list[dict[str, str]]] = {}


@bot.message_handler(commands=['start', 'help'])
def get_info(message: Message) -> None:
    """
    При вводе команд [ /start, /help ] присылает пользователю
    информационное сообщение по использованию бота.
    """
    chat = message.chat
    name = chat.first_name
    try:
        bot.send_message(
            chat_id=chat.id,
            text=(WELCOME_MESSAGE.format(name=name))
        )
    except (ApiTelegramException, RequestException) as e:
        logger.error(SEND_MESSAGE_ERROR.format(error=e))


@bot.message_handler(commands=['clear'])
def delete_context(message: Message) -> None:
    chat_id = message.chat.id
    first_name = message.from_user.first_name
    try:
        dialogues[chat_id].clear()
        logger.debug(
            CLEAR_CONTEXT_MESSAGE.format(name=first_name)
        )
        bot.send_message(
            text=CLEAR_CONTEXT_MESSAGE.format(
                name=first_name,
            ),
            chat_id=chat_id
        )
    except KeyError:
        logger.error(CLEAR_CONTEXT_ERROR_MESSAGE.format(name=first_name))
        raise ClearContextError(CLEAR_CONTEXT_ERROR_MESSAGE(name=first_name))
    except (ApiTelegramException, RequestException) as e:
        logger.error(SEND_MESSAGE_ERROR + str(e))


@bot.message_handler(content_types=['text'])
def send_ai_message(message: Message) -> None:
    """
    Высылает пользователю ответ на запрос, удостоверившись,
    что все проверки прошли успешно.
    """
    chat_id = message.chat.id
    text = message.text
    # Обновляем историю запросов от пользователя.
    update_user_history(chat_id, dialogues, text)

    # Присылаем сообщение о начале обработки запроса,
    # сохраняем в переменную для доступа к message_id.
    processing_msg = send_processing_message(chat_id)
    try:
        logger.debug(f'Запрос: {text}.')
        response = get_ai_answer(chat_id)
    except (ConnectionError, ApiStatusCodeError) as e:
        error_message: str = f'Сбой в работе программы: {e}. Запрос: {text}.'
        logger.error(error_message)
        bot.send_message(chat_id=chat_id, text=error_message)
        return
    try:
        ai_text_answer = check_response(response)
        # Обновляем историю ответа от Deepseek.
        update_deepseek_history(chat_id, dialogues, ai_text_answer)
        # Проверяем на лимит по кол-ву символовов,
        # высылаем сообщение от Deepseek.
        send_long_message(ai_text_answer, chat_id)
        if processing_msg:
            bot.delete_message(chat_id, processing_msg.message_id)
        logger.debug(
            f'Сообщение: ```{ai_text_answer}``` - отправлено успешно.'
        )
    except (
        TypeError, AttrChoicesError, AttrChoicesEmptyError,
        AttrMessageError, AttrContentError, AttrContentEmptyError
    ) as e:
        error_message: str = (
            f'Ошибка в структуре ответа API-Deepseek: {e}. Запрос: {text}'
        )
        logger.error(error_message)
        bot.send_message(chat_id=chat_id, text=error_message)
        return
    except Exception as e:
        error_message: str = (
            f'Внезапная ошибка в работе программы: {e}. Запрос: {text}'
        )
        logger.error(error_message)
        bot.send_message(chat_id=chat_id, text=error_message)
        return


def check_tokens() -> bool:
    """Проверяет наличие всех переменных окружения."""
    tokens: dict[str, Optional[str]] = {
        'DEEPSEEK_TOKEN': DEEPSEEK_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN
    }
    missing_tokens: list[str] = [
        name for name, token in tokens.items() if not token
    ]
    if missing_tokens:
        error_message: str = (
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        raise EnvironmentError(error_message)
    return True


def send_processing_message(chat_id: int) -> Optional[Message]:
    """Подготавливает сообщение пользователю об обработке запроса."""
    try:
        return bot.send_message(
                chat_id=chat_id,
                text='⌛ DeepSeek обрабатывает ваш запрос. '
                'Пожалуйста, немного подождите, и вы получите свой ответ...'
            )
    except (ApiTelegramException, RequestException) as e:
        logger.error(SEND_MESSAGE_ERROR + str(e))


def send_long_message(ai_text_answer: str, chat_id: int) -> None:
    """
    Обрабатывает случай, когда сообщение от Deepseek больше чем 4096.
    Присылает сообщение в чат пользователю.
    """
    if len(ai_text_answer) > MESSAGE_LENGTH_LIMIT:
        for i in range(0, len(ai_text_answer), MESSAGE_LENGTH_LIMIT):
            bot.send_message(
                chat_id=chat_id, text=ai_text_answer[
                    i:i + MESSAGE_LENGTH_LIMIT
                ]
            )
    else:
        bot.send_message(chat_id=chat_id, text=ai_text_answer)


def get_ai_answer(chat_id: int) -> ChatCompletion:
    """
    Получает ответ от API-Deepseek.
    Проверяет на корректное подключение к сервису.
    """
    try:
        # Получаем полный контекст диалога с пользователем.
        messages = full_context(chat_id, dialogues)
        response: ChatCompletion = client.chat.completions.create(
            model='deepseek-chat',
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant'},
                *messages
            ],
            stream=False
        )
    except openai.APIConnectionError as e:
        logger.error(
            'Ошибка подключения к API-сервису. '
            f'Причина: {e.__cause__}.'
        )
        raise ConnectionError(
            'Ошибка подключения к API-сервису Deepseek. '
            f'Получена ошибка: {e}.'
        ) from e
    except openai.APIStatusError as e:
        logger.error(
            f'Статус-код ответа отличен от {HTTPStatus.OK}. '
            f'Статус код: {e.status_code}.'
        )
        raise ApiStatusCodeError from e
    return response


def check_response(response: ChatCompletion) -> str:
    """
    Проверяет все необходимые аттрибуты для работы с ботом.

    response - основной объект класса ChatCompletion, должен иметь choices;
    choices - список, объект класса Choice. Должен иметь message;
    message - объект класса ChatCompletionMessage. Должен иметь content;
    content - аттрибут хранящий в себе текст сообщения, тип - `str`.
    """
    if not isinstance(response, ChatCompletion):
        raise TypeError(
            'response - должен быть типом `ChatCompletion`. '
            f'Сейчас response - это класс {type(response)}.'
        )
    if (
        not hasattr(response, REQUIREMENT_ATTRS['response']) or not
        isinstance(response.choices, list)
    ):
        raise AttrChoicesError
    if not response.choices:
        raise AttrChoicesEmptyError
    # Переходим к 1 выбору из ответа Deepseek.
    first_choice = response.choices[0]
    if (
        not hasattr(first_choice, REQUIREMENT_ATTRS['choices'])
    ):
        raise AttrMessageError
    if (
        not hasattr(first_choice.message, REQUIREMENT_ATTRS['message']) or not
        isinstance(first_choice.message.content, str)
    ):
        raise AttrContentError
    if not first_choice.message.content:
        raise AttrContentEmptyError
    return first_choice.message.content


def main() -> None:
    if not check_tokens():
        exit()
    bot.polling()


if __name__ == '__main__':
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.addHandler(handler)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    try:
        main()
    except Exception as e:
        logger.error(f'Критическая ошибка при запуске бота: {e}.')
