import logging
from logging.handlers import RotatingFileHandler
from .config import Config

def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(Config.LOG_LEVEL)

    formatter = logging.Formatter('[%(asctime)s] %(levelname)s %(name)s: %(message)s')

    # File handler
    file_handler = RotatingFileHandler(
        Config.LOG_FILE,
        maxBytes=Config.LOG_MAX_SIZE,
        backupCount=Config.LOG_BACKUP_COUNT
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger 