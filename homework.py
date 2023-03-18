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

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='program.log',
    level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = RotatingFileHandler(
    'logger_for_hw.log',
    maxBytes=5000000,
    backupCount=5
)
logger.addHandler(handler)
formatter = logging.Formatter(
    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
handler.setFormatter(formatter)


def check_tokens():
    """Проверка доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID,
    }
    for key, value in tokens.items():
        if value is None:
            logger.critical(f'{key} not found')
            sys.exit(1)


def send_message(bot, message):
    """Отправка собщения."""
    try:
        message_info = f'Message ready to send: {message}.'
        logger.debug(message_info)
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug(f'Message sent: {message}')
    except telegram.TelegramError as error:
        logger.error(f' Message not send {error}')


def get_api_answer(timestamp):
    """Запрос к API и получение ответа."""
    params = {'from_date': timestamp, }
    try:
        homework = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=params,
        )
        request_status = homework.status_code
        if request_status != HTTPStatus.OK:
            raise Statu200Error(f'{ENDPOINT} not available')
        return homework.json()
    except requests.exceptions.RequestException as api_error:
        raise RequestAPIError(f'Bad request {api_error}')
    except json.JSONDecodeError as json_error:
        raise JSONDecorError(f'Decode error {json_error}')


def check_response(response):
    """Проверка полученных данных."""
    if not isinstance(response, dict):
        raise TypeError('Incorrect type data')
    elif 'homeworks' not in response:
        raise ResponseError('Key "homeworks" does not exist')
    elif not isinstance(response['homeworks'], list):
        raise TypeError('Incorrect type data')
    return response.get('homeworks')


def parse_status(homework):
    """Извлекает информацию о конкретной домашней работе."""
    homework_name = homework.get("homework_name")
    hw_status = homework.get("status")
    if hw_status is None:
        raise HWStatusError('Status is empty')
    if hw_status not in HOMEWORK_VERDICTS:
        raise HWStatusError('Incorrect status')
    if homework_name is None:
        raise HWStatusError('Name is empty')
    verdict = HOMEWORK_VERDICTS[hw_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


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
            timestamp = response.get("current_date")
            homework = check_response(response)
            if homework:
                current_hw = homework[0]
                lesson_name = current_hw["lesson_name"]
                hw_status = parse_status(current_hw)
                message = f'{lesson_name} \n {hw_status}'
                send_message(bot, message)
            else:
                logger.debug('There is no new status')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            if message != last_error:
                send_message(bot, HOMEWORK_VERDICTS)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
