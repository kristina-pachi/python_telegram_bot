import os
import sys
import logging
import time
import telegram
import requests

from dotenv import load_dotenv

from http import HTTPStatus

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
)

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    tokens = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    for name, token in tokens.items():
        if token is None:
            logging.critical(f'Переменная {name} не задана')
            return False
    return True


def send_message(bot, message):
    """Отправляет сообщение в чат телеграмма."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        logging.error(f'Сообщение не было отправлено, {error}')
    else:
        logging.debug('Удачная отправка сообщения')


def get_api_answer(timestamp):
    """Делает запрос к API."""
    TIMESTAMP = {'from_date': timestamp}
    try:
        response = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params=TIMESTAMP
        )
        if response.status_code != HTTPStatus.OK:
            message = 'API возвращает код, отличный от 200'
            logging.error(message)
            raise Exception(message)
    except TypeError:
        logging.error('Не все аргументы переданные при запросе типа str')
    except requests.RequestException as error:
        logging.error(f'Ошибка при запросе к основному API: {error}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарём')
    if 'homeworks' not in response:
        logging.error('Отсутствует ожидаемый ключ в ответе API')
        raise KeyError('Ключ не найден')
    if 'current_date' not in response:
        logging.error('Отсутствует ожидаемый ключ в ответе API')
        raise KeyError('Ключ не найден')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ответ API не является списком')


def parse_status(homework):
    """Извлекает статус из ответа API."""
    if 'status' not in homework:
        logging.error('Отсутствует ожидаемый ключ в ответе API')
        raise KeyError('Ключ не найден')
    if 'homework_name' not in homework:
        logging.error('Отсутствует ожидаемый ключ в ответе API')
        raise KeyError('Ключ не найден')
    status = homework['status']
    homework_name = homework['homework_name']
    try:
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except Exception:
        message = 'Неожиданный статус домашней работы в ответе API'
        logging.error(message)
        raise KeyError(message)


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 1682365739
    if not check_tokens():
        raise AssertionError()
        sys.exit()
    logging.debug('Бот запушен')
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            if not response['homeworks']:
                raise TypeError('Список пуст')
            homework = response['homeworks'][0]
            if homework:
                message = parse_status(homework)
                send_message(bot, message)
                timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.debug('Работа бота приостановлена')
