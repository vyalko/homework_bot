import logging
import os
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
    ENV_TOKENS = [PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]
    for token in ENV_TOKENS:
        if token is None:
            logging.critical(f'Отсутствует переменная окружения: "{token}"')
            return False
        else:
            logging.info(f'Токен {token} успешно проверен.')
    return True


def send_message(bot, message):
    """Отправляет сообщение в Telegram чат."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
        logging.debug('Сообщение успешно отправлено в Telegram: %s', message)
    except Exception as error:
        logging.error('Сбой при отправке сообщения в Telegram: %s', str(error))


def get_api_answer(timestamp):
    """Делает запрос к API-сервису и возвращает ответ."""
    headers = {'Authorization': 'OAuth PRACTICUM_TOKEN'}
    payload = {'from_date': timestamp}

    try:
        response = requests.get(url=ENDPOINT, headers=headers, params=payload)
        response.raise_for_status()
        response_json = response.json()
    except requests.RequestException:
        raise (f'Ошибка при запросе к API: {ENDPOINT}')

    if response.status_code != HTTPStatus.OK:
        raise Exception.HTTPStatusError

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
        logging.error('Отсутствует ключ "current_date" в ответе API')
        return False

    return True


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
    if not check_tokens():
        logging.critical('Проверьте переменные окружения')
        raise ValueError('Проверьте переменные окружения')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())

    while True:
        try:
            response = get_api_answer(timestamp)
            if check_response(response):
                homeworks = response['homeworks']
                for homework in homeworks:
                    try:
                        status_message = parse_status(homework)
                        send_message(bot, status_message)
                    except Exception as parse_error:
                        logging.error(
                            f'Ошибка при обработке статуса'
                            f' домашней работы: {parse_error}')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)

        time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
