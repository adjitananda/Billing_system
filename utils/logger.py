"""
Модуль логирования для биллинговой системы.
Предоставляет простой логгер с выводом в консоль.
"""

import sys
from datetime import datetime
from typing import Optional

class Logger:
    """Простой логгер для вывода сообщений в консоль с временными метками."""
    
    LEVELS = {
        'DEBUG': 10,
        'INFO': 20,
        'WARNING': 30,
        'ERROR': 40,
        'CRITICAL': 50
    }
    
    def __init__(self, name: str = "Billing", level: str = "INFO"):
        """
        Инициализация логгера.
        
        Args:
            name: Имя логгера (будет отображаться в сообщениях)
            level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        """
        self.name = name
        self.level = self.LEVELS.get(level.upper(), 20)
    
    def _log(self, level: str, message: str) -> None:
        """
        Внутренний метод для форматирования и вывода сообщения.
        
        Args:
            level: Уровень сообщения
            message: Текст сообщения
        """
        if self.LEVELS.get(level, 0) >= self.level:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = f"[{timestamp}] [{self.name}] [{level}] {message}"
            
            # Для ошибок выводим в stderr, для остального в stdout
            if level in ('ERROR', 'CRITICAL'):
                print(log_entry, file=sys.stderr)
            else:
                print(log_entry)
    
    def debug(self, message: str) -> None:
        """Отправка сообщения уровня DEBUG."""
        self._log("DEBUG", message)
    
    def info(self, message: str) -> None:
        """Отправка сообщения уровня INFO."""
        self._log("INFO", message)
    
    def warning(self, message: str) -> None:
        """Отправка сообщения уровня WARNING."""
        self._log("WARNING", message)
    
    def error(self, message: str) -> None:
        """Отправка сообщения уровня ERROR."""
        self._log("ERROR", message)
    
    def critical(self, message: str) -> None:
        """Отправка сообщения уровня CRITICAL."""
        self._log("CRITICAL", message)


# Создаем глобальный экземпляр логгера для использования во всем приложении
# Уровень логирования можно будет позже читать из .env
logger = Logger()

# Функция для удобного импорта
def get_logger(name: Optional[str] = None) -> Logger:
    """
    Возвращает экземпляр логгера.
    
    Args:
        name: Имя логгера (если None, используется глобальный экземпляр)
    
    Returns:
        Logger: Экземпляр логгера
    """
    if name:
        return Logger(name)
    return logger