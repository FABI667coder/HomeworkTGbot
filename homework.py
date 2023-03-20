import json
import logging
import os
import sys
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
import telegram
from dotenv import load_dotenv

from exceptions import (HWStatusError, JSONDecorError, RequestAPIError,
                        ResponseError, Statu200Error)

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler_for_file = RotatingFileHandler(
    'logger_for_hw.log',
    maxBytes=5000000,
    backupCount=5
)
handler_for_stream = logging.StreamHandler(
    stream=sys.stdout
)
logger.addHandler(handler_for_file)
logger.addHandler(handler_for_stream)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler_for_file.setFormatter(formatter)
handler_for_stream.setFormatter(formatter)


def check_tokens():
    """Проверка доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for key, value in tokens.items():
        if not value:
            logger.critical(f'{key} not found')
            sys.exit(1)


def send_message(bot, message):
    """Отправка собщения."""
    try:
        message_info = f'Message ready to send: {message}.'
        logger.debug(message_info)
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Message sent: {message}')
        return True
    except telegram.TelegramError as error:
        logger.error(f' Message not send {error}')
        return False


def get_api_answer(timestamp):
    """Запрос к API и получение ответа."""
    params = {'from_date': timestamp, }
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        if homework.status_code != HTTPStatus.OK:
            raise Statu200Error(f'{ENDPOINT} not available')
        return homework.json()
    except requests.exceptions.RequestException as api_error:
        raise RequestAPIError(f'Bad request {api_error}')
    except json.JSONDecodeError as json_error:
        raise JSONDecorError(f'Decode error {json_error}')


def check_response(response):
    """Проверка полученных данных."""
    if not isinstance(response, dict):
        raise TypeError(
            f'Incorrect type data. '
            f'Your type: {type(response)} not "dict"'
            )
    elif 'homeworks' not in response:
        raise ResponseError('Key "homeworks" does not exist')
    elif 'current_date' not in response:
        raise ResponseError('Key "current_date" does not exist')
    elif not isinstance(response['homeworks'], list):
        raise TypeError(
            f'Incorrect type data. '
            f'Your type: {type(response)} not "list"'
        )
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    homework_name = homework.get('homework_name')
    hw_status = homework.get('status')
    lesson_name = homework.get('lesson_name')
    if hw_status is None:
        raise KeyError('Key does not exist')
    if homework_name is None:
        raise KeyError('Key does not exist')
    if hw_status not in HOMEWORK_VERDICTS:
        raise HWStatusError('Incorrect status')
    verdict = HOMEWORK_VERDICTS[hw_status]
    return (f'Изменился статус проверки работы "{homework_name}". '
            f'\n {lesson_name} \n {verdict}')


def main():
    """Основная логика работы бота."""
    logger.info('Check tokens status')
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    send_message(bot, 'Bot is active')
    last_error = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            if homework:
                current_hw = homework[0]
                hw_status = parse_status(current_hw)
                if send_message(bot, hw_status):
                    timestamp = response.get('current_date')
            else:
                logger.debug('There is no new status')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.exception(message)
            if message != last_error:
                if send_message(bot, message):
                    last_error = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='program.log',
        level=logging.DEBUG,
    )

