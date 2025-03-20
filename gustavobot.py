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
from exceptions.api_status_code_error import ApiStatusCodeError


load_dotenv()

logger = logging.getLogger(__name__)

# Константы - токены, url - адрес Deepseek, обязательные атрибуты.
DEEPSEEK_TOKEN: Optional[str] = os.getenv('DEEPSEEK_TOKEN')
DEEPSEEK_URL: Optional[str] = os.getenv('DEEPSEEK_URL')
TELEGRAM_TOKEN: Optional[str] = os.getenv('TELEGRAM_TOKEN')

# response - объект класса ChatCompletion, дальше вложенность
# аттрибутов схожа с матрешкой.
REQUIREMENT_ATTRS: dict[str, str] = {
    'response': 'choices',
    'choices': 'message',
    'message': 'content'
}

bot = TeleBot(token=TELEGRAM_TOKEN)

# Создаем клиент для работы с Deepseek.
client = OpenAI(
    api_key=DEEPSEEK_TOKEN,
    base_url=DEEPSEEK_URL
)


@bot.message_handler(commands=['start'])
def wake_up(message: Message) -> None:
    """
    При вводе команды /start бот начинает работу,
    а также присылает информационное сообщение пользователю.
    """
    chat = message.chat
    name = chat.first_name
    try:
        bot.send_message(
            chat_id=chat.id,
            text=(
                f'Привет, {name}, я ИИ-ассистент! '
                'Чтобы начать, напиши свой запрос, а я с радостью найду'
                ' на него ответ!'
            )
        )
    except (ApiTelegramException, RequestException) as e:
        logger.error(f'Возникла ошибка при отправке сообщения: {e}.')


@bot.message_handler(commands=['help'])
def get_help(message: Message) -> None:
    """
    При вводе команды /help бот отправит помощь пользователю
    в виде инструкции к работе.
    """
    chat = message.chat
    name = chat.first_name
    try:
        bot.send_message(
            chat_id=chat.id,
            text=(
                'Запутался? Ничего! Чтобы начать, введи любой запрос в чат, '
                'я любезно отвечу на любой твой вопрос, найду лучшее решение!'
                f' Удачи тебе, {name}!'
            )
        )
    except (ApiTelegramException, RequestException) as e:
        logger.error(f'Возникла ошибка при отправке сообщения: {e}.')


@bot.message_handler(content_types=['text'])
def send_ai_message(message: Message) -> None:
    """
    Высылает пользователю ответ на запрос, удостоверившись,
    что все проверки прошли успешно.
    """
    chat_id = message.chat.id
    text = message.text
    # Присылаем сообщение о начале обработки запроса.
    processing_msg = send_processing_message(chat_id)
    try:
        logger.debug(f'Запрос: {text}.')
        response = get_ai_answer(text)
    except (ConnectionError, ApiStatusCodeError) as e:
        error_message = f'Сбой в работе программы: {e}. Запрос: {text}.'
        logger.error(error_message)
        bot.send_message(chat_id=chat_id, text=error_message)
        return
    try:
        ai_text_answer = check_response(response)
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
        error_message = (
            f'Ошибка в структуре ответа API-Deepseek: {e}. Запрос: {text}'
        )
        logger.error(error_message)
        bot.send_message(chat_id=chat_id, text=error_message)
        return
    except Exception as e:
        error_message = (
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
        error_message = (
            'Отсутствуют обязательные переменные окружения: '
            f'{", ".join(missing_tokens)}'
        )
        logger.critical(error_message)
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
        logger.error(f'Возникла ошибка при отправке сообщения: {e}.')


def send_long_message(ai_text_answer: str, chat_id: int) -> None:
    """
    Обрабатывает случай, когда сообщение от Deepseek больше чем 4096.
    Присылает сообщение в чат пользователю.
    """
    if len(ai_text_answer) > 4096:
        for i in range(0, len(ai_text_answer), 4096):
            bot.send_message(
                chat_id=chat_id, text=ai_text_answer[i:i + 4096]
            )
    else:
        bot.send_message(chat_id=chat_id, text=ai_text_answer)


def get_ai_answer(text: str) -> ChatCompletion:
    """
    Получает ответ от API-Deepseek.
    Проверяет на корректное подключение к сервису.
    """
    try:
        response = client.chat.completions.create(
            model='deepseek-chat',
            messages=[
                {'role': 'system', 'content': 'You are a helpful assistant'},
                {'role': 'user', 'content': text},
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
    # Переходим к 1 выбору из ответа нейросети.
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
        exit
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
