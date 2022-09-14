import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot

import exceptions

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
    except telegram.error.TelegramError as mess_err:
        raise exceptions.TelegramError(
            f'Не удалось отправить сообщение: {mess_err}'
        )


def get_api_answer(current_timestamp):
    """Получение ответа от API."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as ex:
        raise requests.exceptions.RequestException(
            f'Ошибка при запросе к API: {ex}'
        )
    if response.status_code != HTTPStatus.OK:
        raise exceptions.ResponseStatusError(
            f'Проблема с ответом API: {response.status_code}',
            f'Причина: {response.reason}',
            f'Текст ответа: {response.text}',
            f'Параметры запроса: {params}'
        )
    return response.json()


def check_response(response):
    """Проверка корректности ответа от API."""
    if not isinstance(response, dict):
        raise TypeError('Ответ от API пришел не в виде ожидаемого словаря')
    if response.get('homeworks') is None:
        raise TypeError('Отсутствует список заданий')
    if response.get('current_date') is None:
        raise TypeError('Отсутствует дата')
    if not isinstance(response.get('homeworks'), list):
        raise TypeError('Домашка под ключом "homeworks" не в виде списка')
    else:
        return response.get('homeworks')


def parse_status(homework):
    """Извлекает статус конкретной домашней работы."""
    try:
        homework_name = homework['homework_name']
    except KeyError:
        raise KeyError('Отсутствует ключ "homework_name"')
    try:
        homework_status = homework['status']
    except KeyError:
        raise KeyError('Отсутствует ключ "status"')
    if homework_status not in HOMEWORK_STATUSES:
        raise exceptions.UnknownStatusError(
            'Неизвестный статус домашней работы'
        )
    verdict = HOMEWORK_STATUSES.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка доступности переменных окружения."""
    return all([TELEGRAM_CHAT_ID, PRACTICUM_TOKEN, TELEGRAM_TOKEN])


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        logger.critical('Отсутствует обязательная переменная окружения!')
        sys.exit('Отсутствует обязательная переменная окружения!')
    else:
        bot = Bot(token=TELEGRAM_TOKEN)
        current_timestamp = int(time.time())
        while True:
            try:
                response = get_api_answer(current_timestamp)
                homeworks = check_response(response)
                message = parse_status(homeworks[0])
                prev_msg = ''
                if homeworks == []:
                    logger.info('Новые работы отсутствуют')
                if homeworks != [] and message != prev_msg:
                    send_message(bot, message)
                    logger.info('Статус работы отправлен')
                    current_timestamp = response['current_date']
                    prev_msg = message
            except exceptions.TelegramError as e:
                logger.error(f'Не удалось отправить сообщение: {e}')
            except Exception as error:
                prev_error = ''
                message = f'Сбой в работе программы: {error}'
                logger.error(message)
                if error != prev_error:
                    bot.send_message(TELEGRAM_CHAT_ID, message)
                    prev_error = error
            finally:
                time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
