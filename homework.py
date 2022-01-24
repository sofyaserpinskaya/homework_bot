import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram


class RequestFailedException(Exception):
    """Неудачный запрос."""

    pass


load_dotenv()

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename=(__file__ + '.log'),
        filemode='w',
        format=('%(asctime)s, %(levelname)s, '
                '%(funcName)s, %(lineno)s, %(message)s')
    )

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(funcName)s '
        '- %(lineno)s - %(message)s'
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')


RETRY_TIME = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


MESSAGE_SENT_INFO = 'Сообщение "{message}" в Telegram отправлено.'
SENDING_MESSAGE_ERROR = ('Не удалось отправить сообщение "{message}" '
                         'в Telegram.')
ERROR_MESSAGE = 'Сбой в работе программы: {error}.'
API_ANSWER_ERROR = ('Ошибка при запросе к {endpoint} с авторизацией {headers} '
                    'и параметрами {params}: {error}.')
API_RESPONSE_ERROR = 'Формат ответа API отличается от ожидаемого. {error}'
RESPONSE_KEY_ERROR = 'Ответ API не содержит ключ "homeworks".'
WRONG_STATUS_ERROR = ('Недокументированный статус домашней работы '
                      '{homework_name}: {status}.')
STATUS_VERDICT = ('Изменился статус проверки работы "{homework_name}". '
                  '{verdict}')
TOKENS_ERROR = 'Отсутствует переменная окружения {name}.'


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logging.info(MESSAGE_SENT_INFO.format(message=message))
    except Exception:
        logging.exception(SENDING_MESSAGE_ERROR.format(message=message))
    else:
        return True


def get_api_answer(current_timestamp):
    """Делает запрос к API-сервису."""
    params = {'from_date': current_timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.exceptions.RequestException as error:
        raise Exception(API_ANSWER_ERROR.format(
            endpoint=ENDPOINT, headers=HEADERS, params=params, error=error
        ))
    if response.status_code != 200:
        raise RequestFailedException(API_ANSWER_ERROR.format(
            endpoint=ENDPOINT, headers=HEADERS, params=params,
            error=response.status_code
        ))
    result = response.json()
    if ('error' or 'code') in result:
        error = result.get('error') or result.get('code')
        raise Exception(API_ANSWER_ERROR.format(
            endpoint=ENDPOINT, headers=HEADERS, params=params, error=error
        ))
    return result


def check_response(response):
    """Проверяет ответ API на корректность."""
    if not isinstance(response, dict):
        raise TypeError(API_RESPONSE_ERROR.format(error=type(response)))
    if 'homeworks' not in response:
        raise KeyError(RESPONSE_KEY_ERROR)
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError(API_RESPONSE_ERROR.format(error=type(homeworks)))
    if homeworks != []:
        return homeworks
    return None


def parse_status(homework):
    """Извлекает из информации о домашней работе статус этой работы."""
    homework_name = homework['homework_name']
    status = homework['status']
    if status not in VERDICTS:
        raise KeyError(WRONG_STATUS_ERROR.format(
            homework_name=homework_name, status=status
        ))
    return (STATUS_VERDICT.format(
        homework_name=homework_name, verdict=VERDICTS[status]
    ))


def check_tokens():
    """Проверяет доступность переменных окружения."""
    for name in ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']:
        if globals()[name] is None:
            logging.critical(TOKENS_ERROR.format(name=name))
    if (PRACTICUM_TOKEN or TELEGRAM_TOKEN or TELEGRAM_CHAT_ID) is None:
        return False
    return True


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        sys.exit()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    errors = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks is not None:
                homework = homeworks[0]
                send_message(bot, parse_status(homework))
                current_timestamp = response.get(
                    'current_date', default=current_timestamp
                )
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logging.error(message)
            if message != errors:
                send_message(bot, message)
                if True:
                    errors = message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
