import logging
import os
import requests
import time

import telegram

from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    filemode='w',
    format='%(asctime)s, %(levelname)s, %(message)s'
)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(f'Сообщение "{message}" в Telegram отправлено.')
    except Exception:
        logging.error(f'Сбой при отправке сообщения "{message}".')


def get_api_answer(current_timestamp):
    """Делает запрос к API-сервису."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except Exception as error:
        logging.error(f'Ошибка при запросе к API: {error}.')
    if response.status_code != 200:
        raise requests.ConnectionError(
            f'Ошибка подключения. {response.status_code}'
        )
    try:
        return response.json()
    except ValueError as error:
        raise error('Невозможно преобразовать данные.')


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Формат ответа API отличается от ожидаемого.')
    if 'homeworks' not in response:
        raise KeyError('Ответ API не содержит ключ "homeworks".')
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('Формат ответа API отличается от ожидаемого.')
    if homeworks != []:
        return homeworks


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    if ('homework_name' or 'status') not in homework:
        logging.error('Отсутствие ожидаемых ключей.')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_STATUSES:
        logging.error('Недокументированный статус домашней работы.')
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in tokens:
        if token is None:
            logging.critical(f'Отсутствует переменная окружения {token}.')
            return False
    return True


def main():
    """Основная логика работы бота."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    errors = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks is not None:
                for homework in homeworks:
                    send_message(bot, parse_status(homework))
                    current_timestamp = response.get('current_date')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}.'
            logging.error(message)
            if message != errors:
                send_message(bot, message)
                errors = message
            time.sleep(RETRY_TIME)
        else:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
