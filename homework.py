import os
import sys
import logging
import time
import telegram
import requests

from http import HTTPStatus

from dotenv import load_dotenv

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
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Отправляет сообщение в чат телеграмма."""
    try:
        logging.debug('Бот собирается отправить сообщение')
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except telegram.error.TelegramError as error:
        raise Exception(f'Сообщение не было отправлено, {error}')
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
            raise Exception('API возвращает код, отличный от 200')
    except requests.RequestException as error:
        raise Exception(f'Ошибка при запросе к основному API: {error}')
    return response.json()


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарём')
    if 'homeworks' not in response:
        raise KeyError('Ключ не найден')
    if 'current_date' not in response:
        raise KeyError('Ключ не найден')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Ответ API не является списком')


def parse_status(homework):
    """Извлекает статус из ответа API."""
    if 'status' not in homework:
        raise KeyError('Ключ не найден')
    if 'homework_name' not in homework:
        raise KeyError('Ключ не найден')
    status = homework['status']
    homework_name = homework['homework_name']
    try:
        verdict = HOMEWORK_VERDICTS[status]
        return f'Изменился статус проверки работы "{homework_name}". {verdict}'
    except Exception:
        raise KeyError('Неожиданный статус домашней работы в ответе API')


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical(
            'Отсутсвует одна или несколько обезательных переменных'
        )
        sys.exit()
    logging.debug('Бот запушен')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_message = ''
    while True:
        try:
            response = get_api_answer(timestamp)
            check_response(response)
            homework = response['homeworks']
            if homework:
                message = parse_status(homework[0])
                send_message(bot, message)
            else:
                logging.debug('Статус остался прежним')
            timestamp = response.get('current_date', timestamp)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if (
                last_message != message
                and not isinstance(error, telegram.error.TelegramError)
            ):
                bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.debug('Работа бота приостановлена')
