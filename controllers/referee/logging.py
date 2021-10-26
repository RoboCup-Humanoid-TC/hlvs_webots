import time
from controller import AnsiCodes
import sys


log_file = open('log.txt', 'w')


def log(message, msg_type, force_flush=True):
    if type(message) is list:
        for m in message:
            log(m, msg_type, False)
        if log_file and force_flush:
            log_file.flush()
        return
    if msg_type == 'Warning':
        console_message = f'{AnsiCodes.YELLOW_FOREGROUND}{AnsiCodes.BOLD}{message}{AnsiCodes.RESET}'
    elif msg_type == 'Error':
        console_message = f'{AnsiCodes.RED_FOREGROUND}{AnsiCodes.BOLD}{message}{AnsiCodes.RESET}'
    else:
        console_message = message
    print(console_message, file=sys.stderr if msg_type == 'Error' else sys.stdout)
    if log_file:
        real_time = int(1000 * (time.time() - log.real_time)) / 1000
        log_file.write(f'[{real_time:08.3f}|{time_count / 1000:08.3f}] {msg_type}: {message}\n')  # log real and virtual times
        if force_flush:
            log_file.flush()


log.real_time = time.time()


def info(message):
    log(message, 'Info')


def warning(message):
    log(message, 'Warning')


def error(message, fatal=False):
    log(message, 'Error')

def close():
    log_file.close()
