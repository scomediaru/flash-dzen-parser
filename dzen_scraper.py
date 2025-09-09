import asyncio
import json
import logging
import random
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List
import hashlib
import sqlite3
from urllib.parse import urlparse

from playwright.async_api import async_playwright
import aiofiles


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.FileHandler("logs/dzen_scraper.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class DzenRSSNewsScraper:
    def __init__(self):
        self.base_url = "https://dzen.ru/news"
        self.browser = None
        self.page = None
        self.collected_news = []
        self.db_path = "output/news_database.db"

        # Создаем директории если их нет
        Path("output").mkdir(exist_ok=True)
        Path("logs").mkdir(exist_ok=True)

        self.init_database()

        self.selectors = {
            "rubric_tabs": '[data-testid="rubric-tabs-scroll-container"] a',
            "news_cards": '[data-testid="other-cards"] [data-testid="card-link"]',
            "story_title": ".news-site--StoryHead-desktop__title-1t a, h1",
            "story_digest": '[data-testid="story-digest"]',
            "summarization_items": '[data-testid="summarization-item"]',
            "source_links": '[data-testid="source-link"]',
            "story_tail_items": ".news-story-tail__list-items .news-site--card-text__cardLink-kh",
            "article_body": '[data-testid="article-body"]',
            "article_paragraphs": '[data-testid="article-render__block"] p, [data-testid="article-render__block"] span',
        }

    def init_database(self):
        """Инициализирует SQLite базу данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Создаем таблицу для уникальных новостей
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processed_news (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    story_url TEXT UNIQUE NOT NULL,
                    story_id TEXT NOT NULL,
                    title TEXT,
                    rubric TEXT,
                    text TEXT,
                    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_story_url ON processed_news(story_url)
            """)

            conn.commit()
            conn.close()
            logger.info(f"База данных инициализирована: {self.db_path}")

        except Exception as e:
            logger.error(f"Ошибка при инициализации базы данных: {e}")

    def clean_story_url(self, url: str) -> str:
        """Очищает URL от лишних параметров, оставляя только базовую часть"""
        try:
            parsed = urlparse(url)

            path_parts = parsed.path.split("/")
            if "story" in path_parts:
                story_index = path_parts.index("story")
                if len(path_parts) > story_index + 1:
                    story_id = path_parts[story_index + 1]
                    clean_url = f"https://dzen.ru/news/story/{story_id}"
                    return clean_url

            return url

        except Exception as e:
            logger.warning(f"Ошибка при очистке URL {url}: {e}")
            return url

    def is_story_processed(self, story_url: str) -> bool:
        """Проверяет, была ли уже обработана новость с данным URL"""
        try:
            clean_url = self.clean_story_url(story_url)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                "SELECT COUNT(*) FROM processed_news WHERE story_url = ?", (clean_url,)
            )
            count = cursor.fetchone()[0]

            conn.close()

            return count > 0

        except Exception as e:
            logger.error(f"Ошибка при проверке URL в базе данных: {e}")
            return False

    def mark_story_processed(
        self, story_url: str, story_id: str, title: str, rubric: str, text: str = ""
    ):
        """Отмечает новость как обработанную в базе данных"""
        try:
            clean_url = self.clean_story_url(story_url)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR IGNORE INTO processed_news (story_url, story_id, title, rubric, text)
                VALUES (?, ?, ?, ?, ?)
            """,
                (clean_url, story_id, title, rubric, text),
            )

            conn.commit()
            conn.close()

            logger.debug(f"Новость отмечена как обработанная: {clean_url}")

        except Exception as e:
            logger.error(f"Ошибка при сохранении в базу данных: {e}")

    async def init_browser(self):
        """Инициализация браузера с настройками"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-background-timer-throttling",
                "--disable-renderer-backgrounding",
                "--disable-backgrounding-occluded-windows",
            ],
        )

        context = await self.browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        self.page = await context.new_page()
        await self.page.set_extra_http_headers(
            {
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            }
        )

        logger.info("Браузер инициализирован успешно")

    async def get_rubrics(self) -> List[Dict[str, str]]:
        """Получает список всех рубрик с главной страницы"""
        try:
            logger.info(f"Переход на главную страницу: {self.base_url}")
            await self.page.goto(self.base_url, wait_until="networkidle", timeout=70000)
            await self.page.wait_for_timeout(3000)

            # Ждем загрузки вкладок рубрик
            await self.page.wait_for_selector(
                self.selectors["rubric_tabs"], timeout=10000
            )

            rubrics = []
            rubric_elements = await self.page.query_selector_all(
                self.selectors["rubric_tabs"]
            )

            for element in rubric_elements:
                href = await element.get_attribute("href")
                text = await element.inner_text()

                if href and text:
                    rubrics.append(
                        {
                            "name": text.strip(),
                            "url": href,
                            "slug": self._generate_slug(text.strip()),
                        }
                    )

            logger.info(f"Найдено рубрик: {len(rubrics)}")
            for rubric in rubrics:
                logger.info(f"  - {rubric['name']}: {rubric['url']}")

            return rubrics

        except Exception as e:
            logger.error(f"Ошибка при получении рубрик: {e}")
            return []

    def _generate_slug(self, text: str) -> str:
        """Генерирует slug из текста"""
        return re.sub(r"[^\w\s-]", "", text.lower()).replace(" ", "-")

    async def get_stories_from_rubric(
        self, rubric: Dict[str, str]
    ) -> List[Dict[str, str]]:
        """Получает список сюжетов из рубрики"""
        try:
            logger.info(f"Сбор новостей из рубрики: {rubric['name']}")
            await self.page.goto(rubric["url"], wait_until="networkidle", timeout=30000)
            await self.page.wait_for_timeout(2000)

            stories = []

            # Ждем загрузки карточек новостей
            try:
                await self.page.wait_for_selector(
                    self.selectors["news_cards"], timeout=10000
                )
            except Exception:
                logger.warning(
                    f"Карточки новостей не найдены в рубрике {rubric['name']}"
                )
                return stories

            story_elements = await self.page.query_selector_all(
                self.selectors["news_cards"]
            )

            for element in story_elements[
                :10
            ]:  # Ограничиваем до 10 новостей на рубрику
                try:
                    href = await element.get_attribute("href")
                    title_element = await element.query_selector(
                        "p, .news-site--card-top-avatar__text-SL"
                    )
                    title = (
                        await title_element.inner_text()
                        if title_element
                        else "Без заголовка"
                    )

                    if href and title:
                        # Проверяем, не обрабатывали ли мы уже эту новость
                        if self.is_story_processed(href):
                            logger.info(f"Новость уже обработана, пропускаем: {title}")
                            continue

                        story_id = self._extract_story_id(href)
                        stories.append(
                            {
                                "id": story_id,
                                "title": title.strip(),
                                "url": href,
                                "rubric": rubric["name"],
                                "rubric_slug": rubric["slug"],
                            }
                        )

                except Exception as e:
                    logger.warning(f"Ошибка при обработке элемента: {e}")
                    continue

            logger.info(f"Собрано {len(stories)} новостей из рубрики {rubric['name']}")
            return stories

        except Exception as e:
            logger.error(f"Ошибка при сборе новостей из рубрики {rubric['name']}: {e}")
            return []

    async def get_article_full_texts(self, story_url: str) -> List[str]:
        """Получает полные тексты статей со страницы сюжета"""
        article_texts = []

        try:
            logger.info("Поиск детальных статей для сюжета")

            try:
                detail_links = await self.page.query_selector_all(
                    self.selectors["story_tail_items"]
                )

                if not detail_links:
                    detail_links = await self.page.query_selector_all(
                        ".news-site--card-text__cardLink-kh"
                    )

                logger.info(f"Найдено {len(detail_links)} ссылок на детальные статьи")

                for i, link in enumerate(detail_links[:2]):
                    try:
                        href = await link.get_attribute("href")
                        if href and "dzen.ru/a/" in href:
                            logger.info(
                                f"Получение полного текста статьи {i+1}: {href}"
                            )

                            await self.page.goto(
                                href, wait_until="domcontentloaded", timeout=30000
                            )
                            await self.page.wait_for_timeout(2000)

                            article_text = await self._extract_article_text()
                            if article_text:
                                article_texts.append(article_text)
                                logger.info(
                                    f"Получен текст статьи {i+1} ({len(article_text)} символов)"
                                )

                            await asyncio.sleep(random.uniform(1, 2))

                    except Exception as e:
                        logger.warning(f"Ошибка при получении статьи {i+1}: {e}")
                        continue

            except Exception as e:
                logger.warning(f"Не удалось найти ссылки на детальные статьи: {e}")

        except Exception as e:
            logger.error(f"Ошибка при получении полных текстов: {e}")

        return article_texts

    async def _extract_article_text(self) -> str:
        """Извлекает текст статьи со страницы"""
        try:
            await self.page.wait_for_selector(
                '[data-testid="article-body"]', timeout=10000
            )

            paragraphs = []

            text_elements = await self.page.query_selector_all(
                '[data-testid="article-render__block"] p span, [data-testid="article-render__block"].content--common-block__block-3U span'
            )

            for element in text_elements:
                try:
                    text = await element.inner_text()
                    text = text.strip()
                    if text and len(text) > 10:  # Фильтруем короткие тексты
                        paragraphs.append(text)
                except Exception:
                    continue

            # Объединяем параграфы
            full_text = " ".join(paragraphs)

            # Очищаем текст от лишних пробелов
            full_text = re.sub(r"\s+", " ", full_text).strip()

            return full_text

        except Exception as e:
            logger.warning(f"Ошибка при извлечении текста статьи: {e}")
            return ""

    def _extract_story_id(self, url: str) -> str:
        """Извлекает ID сюжета из URL"""
        match = re.search(r"/story/([^/?]+)", url)
        if match:
            return match.group(1)
        return hashlib.md5(url.encode()).hexdigest()[:16]

    async def get_story_content(self, story: Dict[str, str]) -> Dict[str, str]:
        """Получает саммари сюжета со страницы Dzen"""
        try:
            logger.info(f"Сбор контента для: {story['title']}")

            # Используем более быструю стратегию загрузки
            try:
                await self.page.goto(
                    story["url"], wait_until="domcontentloaded", timeout=30000
                )
                await self.page.wait_for_timeout(1000)

                # Пробуем дождаться основного контента
                try:
                    await self.page.wait_for_selector(
                        self.selectors["story_digest"], timeout=5000
                    )
                except Exception:
                    # Если не дождались, попробуем еще раз с другим селектором
                    try:
                        await self.page.wait_for_selector("h1", timeout=3000)
                    except Exception:
                        logger.warning(
                            f"Контент не полностью загрузился для {story['title']}"
                        )

            except Exception as e:
                logger.warning(f"Проблемы с загрузкой страницы {story['title']}: {e}")
                # Попробуем продолжить работу с частично загруженной страницей
                # Если страница вообще не загрузилась, вернем базовую информацию
                if "Timeout" in str(e):
                    logger.error(f"Timeout при загрузке {story['title']}, пропускаем")
                    return {
                        "id": story["id"],
                        "title": story["title"],
                        "url": story["url"],
                        "rubric": story["rubric"],
                        "rubric_slug": story["rubric_slug"],
                        "summary": "Контент недоступен (timeout)",
                        "pub_date": datetime.now(timezone.utc).isoformat(),
                        "scraped_at": datetime.now().isoformat(),
                    }

            # Получаем заголовок
            title = story["title"]
            try:
                title_element = await self.page.query_selector(
                    self.selectors["story_title"]
                )
                if title_element:
                    title = await title_element.inner_text()
                    title = title.strip()
            except Exception as e:
                logger.warning(f"Не удалось получить заголовок: {e}")

            summary_parts = []
            source_names = []

            try:
                await self.page.wait_for_selector(
                    self.selectors["story_digest"], timeout=10000
                )
                summary_items = await self.page.query_selector_all(
                    self.selectors["summarization_items"]
                )

                for item in summary_items:
                    # Получаем текст саммари
                    text_span = await item.query_selector("span")
                    if text_span:
                        text = await text_span.inner_text()
                        summary_parts.append(text.strip())

                    # Получаем название источника
                    source_link = await item.query_selector(
                        self.selectors["source_links"]
                    )
                    if source_link:
                        source_text = await source_link.inner_text()
                        # Убираем иконки и лишние символы
                        source_text = re.sub(r"[^\w\s\-\.]+", "", source_text).strip()
                        if source_text:
                            source_names.append(source_text)

            except Exception as e:
                logger.warning(f"Не удалось получить саммари для {story['title']}: {e}")

            # Формируем полное описание
            full_description = ""

            # Получаем полные тексты статей
            article_texts = []
            try:
                article_texts = await self.get_article_full_texts(story["url"])
                if article_texts:
                    logger.info(f"Получено {len(article_texts)} полных текстов статей")

                # Возвращаемся обратно к странице сюжета
                await self.page.goto(
                    story["url"], wait_until="domcontentloaded", timeout=30000
                )
                await self.page.wait_for_timeout(1000)
            except Exception as e:
                logger.warning(f"Ошибка при получении полных текстов: {e}")

            # Формируем итоговый контент
            final_content = full_description
            if article_texts:
                full_articles_text = (
                    "\n\n--- ПОЛНЫЕ ТЕКСТЫ СТАТЕЙ ---\n\n"
                    + "\n\n---\n\n".join(article_texts)
                )
                final_content = f"{full_description}\n\n{full_articles_text}"

            # Отмечаем новость как обработанную в базе данных
            self.mark_story_processed(story["url"], story["id"], title, story["rubric"])

            return {
                "id": story["id"],
                "title": title,
                "url": self.clean_story_url(story["url"]),  # Используем очищенный URL
                "rubric": story["rubric"],
                "rubric_slug": story["rubric_slug"],
                "summary": final_content,
                "pub_date": datetime.now(timezone.utc).isoformat(),
                "scraped_at": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Ошибка при получении контента сюжета {story['title']}: {e}")
            # Возвращаем базовую информацию в случае ошибки
            return {
                "id": story["id"],
                "title": story["title"],
                "url": self.clean_story_url(story["url"]),  # Используем очищенный URL
                "rubric": story["rubric"],
                "rubric_slug": story["rubric_slug"],
                "summary": "",
                "pub_date": datetime.now(timezone.utc).isoformat(),
                "scraped_at": datetime.now().isoformat(),
            }

    def generate_rss(self, news_items: List[Dict]) -> str:
        """Генерирует RSS-ленту"""
        # Создаем корневой элемент RSS
        rss = ET.Element("rss", version="2.0")
        rss.set("xmlns:content", "http://purl.org/rss/1.0/modules/content/")
        rss.set("xmlns:atom", "http://www.w3.org/2005/Atom")

        channel = ET.SubElement(rss, "channel")

        # Метаданные канала
        ET.SubElement(channel, "title").text = "Dzen.ru - Новости"
        ET.SubElement(channel, "link").text = "https://dzen.ru/news"
        ET.SubElement(
            channel, "description"
        ).text = "Новости с портала Dzen.ru по всем рубрикам"
        ET.SubElement(channel, "language").text = "ru-RU"
        ET.SubElement(channel, "lastBuildDate").text = datetime.now(
            timezone.utc
        ).strftime("%a, %d %b %Y %H:%M:%S %z")
        ET.SubElement(channel, "generator").text = "Dzen RSS Scraper"

        # Добавляем элементы новостей
        for item_data in news_items:
            item = ET.SubElement(channel, "item")

            ET.SubElement(item, "title").text = item_data["title"]
            ET.SubElement(item, "link").text = item_data["url"]
            ET.SubElement(item, "guid").text = item_data["id"]
            ET.SubElement(item, "category").text = item_data["rubric"]

            # Описание
            description = item_data.get("summary", "")

            ET.SubElement(item, "description").text = (
                description[:1000] + "..." if len(description) > 1000 else description
            )

            # Полный контент
            content_elem = ET.SubElement(
                item, "{http://purl.org/rss/1.0/modules/content/}encoded"
            )
            content_elem.text = f"<![CDATA[{description}]]>"

            # Дата публикации
            if "pub_date" in item_data:
                try:
                    pub_date = datetime.fromisoformat(
                        item_data["pub_date"].replace("Z", "+00:00")
                    )
                    ET.SubElement(item, "pubDate").text = pub_date.strftime(
                        "%a, %d %b %Y %H:%M:%S %z"
                    )
                except Exception:
                    ET.SubElement(item, "pubDate").text = datetime.now(
                        timezone.utc
                    ).strftime("%a, %d %b %Y %H:%M:%S %z")

        # Форматируем XML с отступами
        self._indent_xml(rss)
        xml_content = ET.tostring(rss, encoding="unicode", method="xml")

        # Добавляем XML декларацию для читаемости
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_content}'

    def _indent_xml(self, elem, level=0):
        """Добавляет отступы для читаемости XML"""
        i = "\n" + level * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                self._indent_xml(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    async def scrape_all_news(self) -> List[Dict]:
        """Основной метод для сбора всех новостей"""
        try:
            await self.init_browser()

            # Получаем все рубрики
            rubrics = await self.get_rubrics()
            if not rubrics:
                logger.error("Не удалось получить рубрики")
                return []

            all_news = []

            rubrics = rubrics[:1]
            for rubric in rubrics:
                await asyncio.sleep(random.uniform(2, 4))
                stories = await self.get_stories_from_rubric(rubric)
                stories = stories[:3]

                for story in stories:
                    try:
                        await asyncio.sleep(random.uniform(1, 3))
                        full_story = await self.get_story_content(story)
                        all_news.append(full_story)
                        logger.info(f"Обработано: {full_story['title']}")
                    except Exception as e:
                        logger.error(
                            f"Ошибка при обработке сюжета {story['title']}: {e}"
                        )
                        basic_story = {
                            "id": story["id"],
                            "title": story["title"],
                            "url": self.clean_story_url(story["url"]),
                            "rubric": story["rubric"],
                            "rubric_slug": story["rubric_slug"],
                            "summary": "Контент недоступен",
                            "pub_date": datetime.now(timezone.utc).isoformat(),
                            "scraped_at": datetime.now().isoformat(),
                        }
                        all_news.append(basic_story)
                        self.mark_story_processed(
                            story["url"], story["id"], story["title"], story["rubric"]
                        )

            logger.info(f"Всего собрано новостей: {len(all_news)}")
            return all_news

        except Exception as e:
            logger.error(f"Ошибка при сборе новостей: {e}")
            return []
        finally:
            if self.browser:
                await self.browser.close()
            if hasattr(self, "playwright"):
                await self.playwright.stop()

    async def save_results(self, news_items: List[Dict]):
        """Сохраняет результаты в файлы"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        json_file = f"output/dzen_news_{timestamp}.json"
        async with aiofiles.open(json_file, "w", encoding="utf-8") as f:
            await f.write(json.dumps(news_items, ensure_ascii=False, indent=2))
        logger.info(f"JSON сохранен: {json_file}")

        rss_content = self.generate_rss(news_items)

        current_rss_file = "output/dzen_news_current.rss"
        async with aiofiles.open(current_rss_file, "w", encoding="utf-8") as f:
            await f.write(rss_content)
        logger.info(f"Актуальная RSS лента: {current_rss_file}")


async def main():
    """Главная функция"""
    scraper = DzenRSSNewsScraper()

    try:
        logger.info("Запуск сбора новостей с Dzen.ru")
        news_items = await scraper.scrape_all_news()

        if news_items:
            await scraper.save_results(news_items)
            logger.info(f"Успешно обработано {len(news_items)} новостей")
        else:
            logger.warning("Не удалось собрать новости")

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}")


if __name__ == "__main__":
    asyncio.run(main())
