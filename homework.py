import logging
import os
import sys
import time

import requests
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

import exceptions

# Здесь задана глобальная конфигурация для всех логгеров
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s'
)

# Здесь создаем логгер
logger = logging.getLogger(__name__)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)

# Загружаем данные в переменные окружения
load_dotenv()

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
    """Отправка сообщения в Телеграм."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
        logging.info('удачная отправка сообщения в Telegram')
    except TelegramError as error:
        logging.error(f'сбой при отправке сообщения в Telegram: {error}')


def get_api_answer(current_timestamp):
    """Получение данных из API Практикума."""
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=params)
    except requests.RequestException:
        raise exceptions.EndpointException(
            'недоступность эндпоинта'
            'https://practicum.yandex.ru/api/user_api/homework_statuses/')
    if response.status_code != 200:
        raise exceptions.EndpointException(
            'API возвращает код, отличный от 200')
    return response.json()


def check_response(response):
    """Проверка полученных из API данных."""
    if type(response) != dict:
        # Хочу выбрасывать CheckResponseException, но тесты ожидают TypeError
        raise TypeError('API возвращает не словарь')
    errors = response.get('error')
    if errors:
        raise exceptions.CheckResponseException(
            'API возвращает ошибки (ошибки в запросе)')
    homeworks = response.get('homeworks')
    if homeworks is None:
        raise exceptions.CheckResponseException(
            'ответ от API не содержит ключа "homeworks"')
    if type(homeworks) != list:
        raise exceptions.CheckResponseException(
            'домашки приходят не в виде списка в ответ от API')
    return homeworks


def parse_status(homework):
    """Получение статуса домашних работ."""
    homework_name = homework.get('homework_name')
    if homework_name is None:
        # Хочу выбрасывать ParseStatusException, но тесты ожидают KeyError
        raise KeyError(
            'Отсутствие ожидаемых ключей в ответе API (homework_name)')
    homework_status = homework.get('status')
    if homework_status is None:
        # Хочу выбрасывать ParseStatusException, но тесты ожидают KeyError
        raise KeyError('Отсутствие ожидаемых ключей в ответе API (status)')
    verdict = HOMEWORK_STATUSES.get(homework_status)
    if verdict is None:
        raise exceptions.ParseStatusException(
            'Недокументированный статус домашней работы в ответе от API')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка токенов."""
    return PRACTICUM_TOKEN and TELEGRAM_TOKEN and TELEGRAM_CHAT_ID


def logging_procedure(error):
    """Процедура логирования."""
    if type(error) in (TypeError, KeyError):
        logger.error(error)
    elif isinstance(error, exceptions.ErrorException):
        logger.error(error)
    elif isinstance(error, exceptions.CriticalException):
        logger.critical(error)
    else:
        logger.warning(error)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Нет переменных окружения')
        raise exceptions.NoTokensException('Нет переменных окружения')
    bot = Bot(token=TELEGRAM_TOKEN)
    current_timestamp = int(time.time())
    message_cache = None
    while True:
        try:
            response = get_api_answer(current_timestamp)
            homeworks = check_response(response)
            if homeworks:
                for homework in homeworks:
                    message = parse_status(homework)
                    send_message(bot, message)
                current_timestamp = int(time.time())
            else:
                logger.debug('Отсутствует новая информация')
            time.sleep(RETRY_TIME)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            if (message_cache != message
               and isinstance(error, exceptions.ErrorException)):
                send_message(bot, message)
                message_cache = message
            logging_procedure(error)
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
