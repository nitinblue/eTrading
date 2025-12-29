# trading_bot/logger.py
import logging
import logging.config

class Logger:
    """Configurable logger."""
    @staticmethod
    def setup(config: Dict[str, str]):
        level = config.get('level', 'INFO')
        file = config.get('file', 'trading_bot.log')
        logging.basicConfig(filename=file, level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        return logging.getLogger(__name__)