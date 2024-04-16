import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

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
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    filename='program.log',
    encoding='utf-8')


def check_tokens():
    """Проверяет доступность переменных окружения."""
    ENV_TOKENS = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID
    }
    missing_tokens = []
    for token_name, token_value in ENV_TOKENS.items():
        if token_value is None:
            missing_tokens.append(
                f'Отсутствует переменная окружения: "{token_name}"')
    return missing_tokens


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        logging.debug('Отправка сообщения в Telegram: %s', message)
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Сообщение успешно отправлено в Telegram: %s', message)
    except Exception as error:
        logging.error('Сбой при отправке сообщения в Telegram: %s', str(error))


def get_api_answer(timestamp):
    """Делает запрос к API-сервису и возвращает ответ."""
    payload = {'from_date': timestamp}

    try:
        logging.debug('Отправка запроса к API: %s', ENDPOINT)
        response = requests.get(url=ENDPOINT, headers=HEADERS, params=payload)
        response.raise_for_status()
        response_json = response.json()
    except requests.RequestException:
        raise Exception(f'Ошибка при запросе к API: {ENDPOINT}.')

    if response.status_code != HTTPStatus.OK:
        raise Exception(f'Ошибка статуса HTTP: {response.status_code}')

    return response_json


def check_response(response):
    """Проверяет ответ API на соответствие документации."""
    if not isinstance(response, dict):
        raise TypeError('Ответ от API должен быть словарем')

    if 'homeworks' not in response:
        raise KeyError('Отсутствует ключ "homeworks" в ответе API')

    if not isinstance(response['homeworks'], list):
        raise TypeError('Данные по ключу "homeworks" не являются списком')

    if 'current_date' not in response:
        raise KeyError('Отсутствует ключ "current_date" в ответе API')


def parse_status(homework):
    """Извлекает статус работы из информации о домашней работе."""
    homework_name = homework.get('homework_name')
    if not homework_name:
        raise ValueError('Отсутствует ключ "homework_name" в ответе API')

    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Недокументированный статус работы: "{status}"')

    verdict = HOMEWORK_VERDICTS.get(status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    missing_tokens = check_tokens()
    if missing_tokens:
        error_message = '\n'.join(missing_tokens)
        logging.critical(error_message)
        sys.exit('Ошибка: Токены не прошли валидацию')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    logging.info('Бот запущен')
    timestamp = int(time.time())
    last_status = None
    status_message = None

    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            homeworks = response.get('homeworks')
            if homeworks:
                status_message = parse_status(homeworks[0])
            if status_message != last_status:
                send_message(bot, status_message)
                logging.info('Статус изменился')
                last_status = status_message
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
        finally:
            logging.info('Программа завершена')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
