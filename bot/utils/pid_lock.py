import os
import sys
import signal
import psutil
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class PIDLock:
    """Класс для управления PID-файлом и предотвращения множественных инстансов"""
    
    def __init__(self, pid_file_path="logs/bot.pid"):
        self.pid_file = Path(pid_file_path)
        self.pid = os.getpid()
        
    def acquire(self) -> bool:
        """Попытка захватить блокировку"""
        # Создаем директорию если не существует
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Проверяем существующий PID файл
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                
                # Проверяем, жив ли процесс с этим PID
                if self._is_process_running(old_pid):
                    logger.error(f"Бот уже запущен с PID {old_pid}")
                    # Пытаемся определить, это Python процесс или нет
                    try:
                        process = psutil.Process(old_pid)
                        cmdline = ' '.join(process.cmdline())
                        if 'python' in cmdline.lower() and 'bot' in cmdline.lower():
                            logger.error(f"Обнаружен активный процесс бота: {cmdline[:100]}")
                            return False
                    except:
                        pass
                else:
                    logger.info(f"Старый PID {old_pid} не активен, перезаписываем")
                    
            except (ValueError, IOError) as e:
                logger.warning(f"Ошибка чтения PID файла: {e}")
        
        # Записываем наш PID
        try:
            with open(self.pid_file, 'w') as f:
                f.write(str(self.pid))
            logger.info(f"PID {self.pid} записан в {self.pid_file}")
            return True
        except IOError as e:
            logger.error(f"Не удалось записать PID файл: {e}")
            return False
    
    def release(self):
        """Освободить блокировку"""
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    file_pid = int(f.read().strip())
                
                # Удаляем только если это наш PID
                if file_pid == self.pid:
                    self.pid_file.unlink()
                    logger.info(f"PID файл {self.pid_file} удален")
                else:
                    logger.warning(f"PID в файле ({file_pid}) не совпадает с нашим ({self.pid})")
            except Exception as e:
                logger.error(f"Ошибка при удалении PID файла: {e}")
    
    def _is_process_running(self, pid: int) -> bool:
        """Проверка, запущен ли процесс с данным PID"""
        try:
            # Проверяем существование процесса
            os.kill(pid, 0)
            return True
        except OSError:
            return False
        except Exception:
            return False
    
    def kill_existing(self) -> bool:
        """Завершить существующий процесс бота"""
        if self.pid_file.exists():
            try:
                with open(self.pid_file, 'r') as f:
                    old_pid = int(f.read().strip())
                
                if self._is_process_running(old_pid):
                    # Проверяем что это действительно бот
                    try:
                        process = psutil.Process(old_pid)
                        cmdline = ' '.join(process.cmdline())
                        if 'python' in cmdline.lower() and 'bot' in cmdline.lower():
                            logger.warning(f"Завершаем старый процесс бота PID {old_pid}")
                            os.kill(old_pid, signal.SIGTERM)
                            # Даем время на graceful shutdown
                            import time
                            time.sleep(2)
                            
                            # Если все еще жив - убиваем жестко
                            if self._is_process_running(old_pid):
                                logger.warning(f"Процесс {old_pid} не завершился, используем SIGKILL")
                                os.kill(old_pid, signal.SIGKILL)
                                time.sleep(1)
                            
                            return True
                    except Exception as e:
                        logger.error(f"Ошибка при завершении процесса: {e}")
            except Exception as e:
                logger.error(f"Ошибка при чтении PID файла: {e}")
        return False
    
    def __enter__(self):
        """Context manager вход"""
        if not self.acquire():
            sys.exit(1)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager выход"""
        self.release()