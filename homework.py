import logging
import os
import sys
import time
from http import HTTPStatus

import requests
from dotenv import load_dotenv
from telegram import Bot

load_dotenv()


PRACTICUM_TOKEN = os.getenv('YATOKEN')
TELEGRAM_TOKEN = os.getenv('TGTOKEN')
TELEGRAM_CHAT_ID = os.getenv('CHAT_ID')

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
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
    filename='bot.log',
    filemode='w'
)
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def send_message(bot, message):
    """Отправка сообщения ботом."""
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message
        )
    except Exception as mess_err:
        logger.error(f'Не удалось отправить сообщение: {mess_err}')


def get_api_answer(current_timestamp):
    """Получение ответа от API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as e:
        logger.error(f'Ошибка при запросе к API: {e}')
    if response.status_code != HTTPStatus.OK:
        logger.error(f'Проблемы с доступом: {response.status_code}')
        raise Exception(f'Кажется, есть проблема: {response.status_code}')
    return response.json()


def check_response(response):
    """Проверка корректности ответа от API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ от API пришел не в виде ожидаемого словаря')
    if response.get('homeworks') is None:
        logger.error('Отсутствует список заданий')
        raise Exception('Отсутствует список заданий')
    if response.get('current_date') is None:
        logger.error('Отсутствует значение ключа "current"')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Домашка под ключом "homeworks" не в виде списка')
    else:
        return response.get('homeworks')

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
    if all([TELEGRAM_CHAT_ID, PRACTICUM_TOKEN, TELEGRAM_TOKEN]):
        return True
    else:
        logger.critical('Отсутствует обязательная переменная окружения!')
        return False

def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks != []:
                send_message(bot, parse_status(homeworks[0]))
                logger.info('Статус работы отправлен')
                current_timestamp = response['current_date']
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message)
            bot.send_message(TELEGRAM_CHAT_ID, message)
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
