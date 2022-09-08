import logging
import os
import time
from http import HTTPStatus
from logging.handlers import RotatingFileHandler

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('YATOKEN')
TELEGRAM_TOKEN = os.getenv('TGTOKEN')
TELEGRAM_CHAT_ID = 329170525

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s'
)
logger = logging.getLogger(__name__)
handler = RotatingFileHandler('bot.log', maxBytes=50000000, backupCount=5)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения ботом."""
    bot.send_message(
        TELEGRAM_CHAT_ID,
        message
    )


def get_api_answer(current_timestamp):
    """Получение ответа от API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as e:
        logging.error(f'Ошибка "{e}" при запросе к API')
    if response.status_code != HTTPStatus.OK:
        logging.error(f'Проблемы с доступом: {response.status_code}')
        raise Exception('Страница не отвечает')
    return response.json()


def check_response(response):
    """Проверка корректности ответа от API."""
    homework = response['homeworks']
    if type(homework) is not list:
        raise Exception('Ответ от API пришел не в виде ожидаемого списка')
    if not homework:
        raise Exception('Отсутствуют домашние работы за данный период')
    if homework is None:
        logging.error('Некорректный ответ API')
    else:
        return homework


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        raise Exception('Неизвестный статус домашней работы')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    tokens = [TELEGRAM_CHAT_ID, PRACTICUM_TOKEN, TELEGRAM_TOKEN]
    if None in tokens:
        logging.critical('Отсутствует обязательная переменная окружения!')
        return False
    return True


def main():
    """Основная логика работы бота."""
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if message:
                send_message(bot, message)
            time.sleep(RETRY_TIME)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            bot.send_message(TELEGRAM_CHAT_ID, message)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
