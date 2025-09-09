#!/usr/bin/env python3
"""
Планировщик задач для Dzen News Scraper
Запускает скрапинг по расписанию
"""

import asyncio
import logging
import schedule
import time
from dzen_scraper import main as dzen_main
from config import Config

# Настройка логирования
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT,
    handlers=[
        logging.FileHandler(f"{Config.LOGS_DIR}/scheduler.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)


class NewsScraperScheduler:
    def __init__(self) -> None:
        self.scraper = None
        self.is_running = False

    async def run_scraper_job(self):
        """Задача для планировщика"""
        if self.is_running:
            logger.warning("Скрапер уже выполняется. Пропускаем задачу.")
            return

        self.is_running = True
        logger.info("Запуск планированного скрапинга...")

        try:
            await dzen_main()

        except Exception as e:
            logger.error(f"Ошибка при выполнении планированного скрапинга: {e}")

        finally:
            self.is_running = False

    def schedule_job(self):
        """Синхронная обертка для асинхронной задачи"""
        asyncio.run(self.run_scraper_job())

    def setup_schedule(self):
        """Настройка расписания"""
        logger.info("Немедленный запуск скрапинга (первый запуск сейчас)")
        self.schedule_job()

        for hour in range(9, 23):
            schedule.every().day.at(f"{hour:02d}:00").do(self.schedule_job)
            schedule.every().day.at(f"{hour:02d}:30").do(self.schedule_job)

        schedule.every().day.at("07:00").do(self.schedule_job)  # Утренние новости
        schedule.every().day.at("12:00").do(self.schedule_job)  # Дневные новости
        schedule.every().day.at("19:00").do(self.schedule_job)  # Вечерние новости
        schedule.every().day.at("23:00").do(self.schedule_job)  # Поздние новости

        logger.info(
            "Расписание настроено. Скрапинг будет запускаться каждые 30 минут с 9:00 до 23:00"
        )

    def run_scheduler(self):
        """Основной цикл планировщика"""
        Config.create_directories()
        self.setup_schedule()

        logger.info("Планировщик запущен. Ожидание задач...")

        while True:
            try:
                schedule.run_pending()
                time.sleep(60)  # Проверяем каждую минуту

            except KeyboardInterrupt:
                logger.info("Получен сигнал остановки. Завершение работы...")
                break
            except Exception as e:
                logger.error(f"Ошибка в планировщике: {e}")
                time.sleep(60)


def main():
    """Основная функция"""
    scheduler = NewsScraperScheduler()

    # Запуск немедленно при старте
    logger.info("Выполняем первоначальный скрапинг...")
    scheduler.schedule_job()

    # Запуск планировщика
    scheduler.run_scheduler()


if __name__ == "__main__":
    main()
