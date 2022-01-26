import logging
import os
import time

from dotenv import load_dotenv
import requests
import telegram


class RequestFailedError(Exception):
    """Неудачный запрос."""

    pass


class ApiAnswerError(Exception):
    """Ошибка в ответе от API-сервиса."""

    pass


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
TOKENS = ['PRACTICUM_TOKEN', 'TELEGRAM_TOKEN', 'TELEGRAM_CHAT_ID']


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
                         'в Telegram. - {error}')
ERROR_MESSAGE = 'Сбой в работе программы: {error}.'
API_ANSWER_ERROR = ('Ошибка при запросе к {url} с авторизацией {headers} '
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
        return True
    except Exception as error:
        logging.error(SENDING_MESSAGE_ERROR.format(
            message=message, error=error
        ))
        return False


def get_api_answer(current_timestamp):
    """Делает запрос к API-сервису."""
    params = {'from_date': current_timestamp}
    request_params = dict(url=ENDPOINT, headers=HEADERS, params=params)
    try:
        response = requests.get(**request_params)
    except requests.exceptions.RequestException as error:
        raise ConnectionError(API_ANSWER_ERROR.format(
            error=error, **request_params
        ))
    if response.status_code != 200:
        raise RequestFailedError(API_ANSWER_ERROR.format(
            error=response.status_code, **request_params
        ))
    result = response.json()
    for key in ['error', 'code']:
        if key in result:
            raise ApiAnswerError(API_ANSWER_ERROR.format(
                error={key: result.get(key)}, **request_params
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
    name = homework['homework_name']
    status = homework['status']
    if status not in VERDICTS:
        raise ValueError(WRONG_STATUS_ERROR.format(
            homework_name=name, status=status
        ))
    return STATUS_VERDICT.format(
        homework_name=name, verdict=VERDICTS[status]
    )


def check_tokens():
    """Проверяет доступность переменных окружения."""
    missed_tokens = [name for name in TOKENS if globals()[name] is None]
    if missed_tokens:
        logging.critical(TOKENS_ERROR.format(name=missed_tokens))
    return not missed_tokens


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        raise ValueError
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    errors = ''
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            current_timestamp = response.get(
                'current_date', current_timestamp
            )
            if homeworks:
                if send_message(bot, parse_status(homeworks[0])):
                    errors = ''
        except Exception as error:
            message = ERROR_MESSAGE.format(error=error)
            logging.error(message)
            if message != errors and send_message(bot, message):
                errors = message
        time.sleep(RETRY_TIME)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format=('%(asctime)s, %(levelname)s, '
                '%(funcName)s, %(lineno)s, %(message)s'),
        handlers=[
            logging.FileHandler((__file__ + '.log'), mode='w'),
            logging.StreamHandler()
        ]
    )

    main()
