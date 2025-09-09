# Dzen News Scraper

Профессиональный скрапер новостей с сайта Dzen.ru с обходом защиты от ботов и автоматическим сбором полных текстов статей.

## Возможности

- 🚀 **Обход защиты от ботов**: Использует Playwright для эмуляции реального пользователя
- 📰 **Полный сбор данных**: Заголовки, ссылки, краткие описания и полные тексты статей
- 🛡️ **Устойчивость**: Множественные селекторы, обработка ошибок, задержки между запросами
- ⏰ **Автоматизация**: Планировщик задач для регулярного сбора новостей
- 📊 **Множественные форматы**: Сохранение в JSON и Markdown
- 🐳 **Docker-ready**: Готовое решение для развертывания в контейнерах

## Быстрый старт

### Локальная установка

1. **Клонирование репозитория**
```bash
git clone <repository-url>
cd ai-news-rss
```

2. **Установка зависимостей**
```bash
pip install -r requirements.txt
playwright install chromium
```

3. **Запуск**
```bash
# Разовый запуск
python dzen_scraper.py

# Запуск планировщика
python scheduler.py
```

### Docker развертывание

**Запуск с Docker Compose:**
```bash
# Сборка и запуск
docker-compose up -d

# Просмотр логов
docker-compose logs -f

# Остановка
docker-compose down
```

## Архитектура

### Основные компоненты

- **`dzen_scraper.py`** - Основной модуль скрапера
- **`scheduler.py`** - Планировщик задач  
- **`config.py`** - Конфигурация приложения
- **`requirements.txt`** - Python зависимости
- **`dockerfile`** - Docker образ
- **`docker-compose.yml`** - Оркестрация контейнеров

### Принцип работы

1. **Инициализация браузера**: Запуск Playwright с настройками обхода детекции ботов
2. **Сбор карточек**: Парсинг главной страницы для получения списка новостей
3. **Извлечение контента**: Переход по ссылкам и сбор полных текстов
4. **Сохранение данных**: Экспорт в JSON и Markdown форматах

## Конфигурация

Основные переменные окружения:

```bash
# Основные настройки
MAX_ARTICLES=30                 # Максимальное количество статей
SAVE_FORMAT=both               # json, markdown, both
HEADLESS=true                  # Режим браузера

# Задержки (секунды)
MIN_DELAY=2.0                  # Минимальная задержка
MAX_DELAY=4.0                  # Максимальная задержка
ARTICLE_DELAY_MIN=3.0          # Задержка между статьями
ARTICLE_DELAY_MAX=6.0
```

## Структура выходных данных

### JSON формат

```json
[
  {
    "title": "Заголовок новости",
    "url": "https://dzen.ru/news/story/...",
    "summary": "Краткое описание новости...",
    "content": "Полный текст статьи...",
    "publish_date": "2024-01-15T10:30:00",
    "scraped_at": "2024-01-15T11:00:00",
    "content_length": 1250
  }
]
```

### Markdown формат

```markdown
# Новости Dzen.ru

**Дата сбора:** 2024-01-15 11:00:00
**Количество статей:** 25

## 1. Заголовок новости

**URL:** https://dzen.ru/news/story/...
**Полный текст:** Полный текст статьи...
```

## Решение проблем

### Частые проблемы

1. **Капча или блокировка**
   - Увеличьте задержки в конфигурации
   - Проверьте ротацию User-Agent'ов

2. **Не находятся элементы**
   - Обновите селекторы в config.py
   - Проверьте изменения в структуре сайта

3. **Высокое потребление памяти**
   - Уменьшите MAX_ARTICLES
   - Увеличьте задержки между запросами

### Отладка

```bash
# Запуск в debug режиме
HEADLESS=false LOG_LEVEL=DEBUG python dzen_scraper.py

# Просмотр логов
docker-compose logs -f

# Подключение к контейнеру
docker-compose exec dzen-scraper /bin/bash
```

## Конфигурация

### Переменные окружения

```bash
# Основные настройки
MAX_ARTICLES=30                 # Максимальное количество статей
SAVE_FORMAT=both               # json, markdown, both
HEADLESS=true                  # Режим браузера

# Задержки (секунды)
MIN_DELAY=2.0                  # Минимальная задержка
MAX_DELAY=4.0                  # Максимальная задержка
ARTICLE_DELAY_MIN=3.0          # Задержка между статьями
ARTICLE_DELAY_MAX=6.0

# Директории
OUTPUT_DIR=./output            # Папка для результатов
LOGS_DIR=./logs               # Папка для логов

# Браузер
BROWSER_TIMEOUT=30000         # Таймаут браузера (мс)
PAGE_TIMEOUT=20000            # Таймаут страницы (мс)
```

### Настройка селекторов

Селекторы автоматически адаптируются к изменениям на сайте:

```python
SELECTORS = {
    'news_cards': 'article[data-testid="news-card"], .news-card, [data-entity="news-card"]',
    'card_title': 'h2, .news-card__title, [data-testid="news-card-title"]',
    'card_link': 'a',
    'article_content': 'article, .article-content, .news-content'
}
```

## Развертывание на сервере

### Автоматическая установка

```bash
# Скачивание скрипта установки
curl -fsSL https://raw.githubusercontent.com/your-repo/dzen-scraper/main/setup_server.sh -o setup_server.sh
chmod +x setup_server.sh

# Запуск установки
./setup_server.sh

# Переключение на пользователя scraper
sudo su - scraper

# Переход в рабочую директорию
cd /opt/dzen-scraper

# Копирование файлов проекта
# (скопируйте все файлы проекта в эту директорию)

# Развертывание
./deploy.sh production
```

### Ручная установка

1. **Подготовка сервера**
```bash
# Обновление системы
sudo apt-get update && sudo apt-get upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
```

2. **Создание пользователя**
```bash
sudo useradd -m -s /bin/bash scraper
sudo usermod -aG docker scraper
sudo mkdir -p /opt/dzen-scraper
sudo chown scraper:scraper /opt/dzen-scraper
```

3. **Настройка systemd сервиса**
```bash
sudo tee /etc/systemd/system/dzen-scraper.service > /dev/null << EOF
[Unit]
Description=Dzen News Scraper
Requires=docker.service
After=docker.service

[Service]
Type=forking
Restart=always
User=scraper
Group=scraper
WorkingDirectory=/opt/dzen-scraper
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable dzen-scraper
```

## Мониторинг и обслуживание

### Просмотр статуса

```bash
# Статус контейнеров
docker-compose ps

# Логи в реальном времени
docker-compose logs -f

# Статус системного сервиса
sudo systemctl status dzen-scraper
```

### Обслуживание

```bash
# Ручной запуск скрапера
docker-compose exec dzen-scraper python dzen_scraper.py

# Перезапуск сервиса
sudo systemctl restart dzen-scraper

# Обновление
./update.sh

# Очистка логов
sudo logrotate -f /etc/logrotate.d/dzen-scraper
```

### Мониторинг ресурсов

```bash
# Использование ресурсов контейнерами
docker stats

# Размер данных
du -sh output/ logs/

# Свободное место на диске
df -h
```

## Автоматизация

### Cron задачи

Автоматически настраиваются при установке:

```bash
# Мониторинг каждые 30 минут
*/30 * * * * /opt/dzen-scraper/monitor.sh

# Перезапуск контейнера раз в день в 3:00
0 3 * * * cd /opt/dzen-scraper && docker-compose restart

# Очистка старых файлов (старше 7 дней)
0 2 * * * find /opt/dzen-scraper/output -name "*.json" -mtime +7 -delete
```

### Планировщик

По умолчанию запускается каждые 30 минут в рабочие часы (9:00-22:00) и дополнительно в ключевые новостные часы.

## Структура выходных данных

### JSON формат

```json
[
  {
    "title": "Заголовок новости",
    "url": "https://dzen.ru/news/story/...",
    "summary": "Краткое описание новости...",
    "content": "Полный текст статьи...",
    "publish_date": "2024-01-15T10:30:00",
    "scraped_at": "2024-01-15T11:00:00",
    "content_length": 1250
  }
]
```

### Markdown формат

```markdown
# Новости Dzen.ru

**Дата сбора:** 2024-01-15 11:00:00
**Количество статей:** 25

## 1. Заголовок новости

**URL:** https://dzen.ru/news/story/...
**Дата публикации:** 2024-01-15T10:30:00
**Краткое описание:** Краткое описание новости...

**Полный текст:**
Полный текст статьи...
```

## Решение проблем

### Частые проблемы

1. **Капча или блокировка**
   - Увеличьте задержки в конфигурации
   - Проверьте ротацию User-Agent'ов
   - Рассмотрите использование прокси

2. **Не находятся элементы**
   - Обновите селекторы в config.py
   - Проверьте изменения в структуре сайта
   - Запустите в режиме headless=false для отладки

3. **Высокое потребление памяти**
   - Уменьшите MAX_ARTICLES
   - Увеличьте задержки между запросами
   - Настройте ограничения в docker-compose.yml

### Отладка

```bash
# Запуск в debug режиме
HEADLESS=false LOG_LEVEL=DEBUG python dzen_scraper.py

# Просмотр детальных логов
docker-compose logs -f --tail=100

# Подключение к контейнеру
docker-compose exec dzen-scraper /bin/bash
```

## Лицензия

MIT License - см. файл LICENSE

## Вклад в проект

1. Создайте форк репозитория
2. Создайте ветку для вашей функции
3. Зафиксируйте изменения
4. Отправьте пулл-реквест

## Поддержка

При возникновении проблем создавайте issue в GitHub репозитории с подробным описанием проблемы и логами.