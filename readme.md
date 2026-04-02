# RiskLab: Инструкция по запуску

## Рассказ о продукте
Мы разрабатываем интерактивный веб-тренажёр, который позволяет на реальных данных Московской биржи собрать инвестиционный портфель и проверить его устойчивость с помощью стресс-сценариев


## Инструкция
Следуйте этой инструкции для настройки и запуска проекта **RiskLab**. Все команды выполняются в терминале.  
**Важно:** Убедитесь, что у вас установлены `Python` и `pip`.

---

## Запуск проекта

### 1 скачайте и запустите докер:

[Docker Desktop](https://www.docker.com/products/docker-desktop/)

### 2 Клонируйте проект:

#### Для Windows:
```bash
git clone https://github.com/nto-itmo-hub/IT-liceisti/
```

#### Для macOS/Linux:
```bash
git clone https://github.com/nto-itmo-hub/IT-liceisti/
```

---

### 3 Перейдите в папку проекта:

#### Для Windows:
```bash
cd web
```

#### Для macOS/Linux:
```bash
cd web
```

---

### 4 Создайте файл окружения `.env` на основе `env.example`:

#### Для Windows:
```bash
copy env.example .env
```

#### Для macOS/Linux:
```bash
cp env.example .env
```

---

### 5 Настройте файл `.env`:

Откройте файл `.env` в любом текстовом редакторе и настройте параметры:  

- **DJANGO_DEBUG**: `true` для разработки, `false` для продакшн.
- **DJANGO_SECRET_KEY**: Уникальный секретный ключ.
- **DJANGO_ALLOWED_HOSTS**: Разрешенные хосты, разделенные запятыми (например, `127.0.0.1,localhost`).
- **POSTGRES_DB=fsp**: Название базы данных для PostgreSQL.
- **POSTGRES_USER=postgres**: Имя пользователя для PostgreSQL.
- **POSTGRES_PASSWORD=admin**: Пароль для PostgreSQL.
- **POSTGRES_HOST=postgres**: Хост базы данных PostgreSQL (по умолчанию postgres).
- **POSTGRES_PORT=5432**: Порт для подключения к базе данных PostgreSQL (по умолчанию 5432).

---

### 6 Запустите проект с помощью Docker Compose:
Выполните следующую команду для сборки и запуска контейнеров:
```bash
docker-compose up --build
```

Эта команда:
1. Скачает необходимые Docker-образы.
2. Соберет контейнеры для вашего проекта.
3. Запустит сервисы: Django, PostgreSQL и миграции.


---

### 7 Откройте сайт:
Перейдите по адресу:  
[http://127.0.0.1:8000/](http://127.0.0.1:8000/)

> **Важно:** Не закрывайте терминал, пока сервер работает.

---

## Настройка файла `.env`

Файл `.env` содержит конфигурацию вашего проекта. Вы можете создать его на основе `env.example` и изменить параметры, если это необходимо.  
Пример содержимого `env.example`:

```env
DJANGO_DEBUG=true
DJANGO_SECRET_KEY=secret_key
DJANGO_ALLOWED_HOSTS=127.0.0.1
POSTGRES_DB=fsp
POSTGRES_USER=postgres
POSTGRES_PASSWORD=admin
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
```

---

## Возможные ошибки запуска

### Ошибка при запуске docker-compose up --build:
Если вы сталкиваетесь с ошибками, попробуйте выполнить следующие шаги:
1. Убедитесь, что у вас установлены последние версии Docker и Docker Compose.
2. Перезапустите Docker.
3. Попробуйте выполнить команду с флагом --no-cache, чтобы избежать использования кэша:
    ```bash
    docker-compose up --build --no-cache
    ```

---

 **Совет:** Если у вас возникнут вопросы, создайте Issue в репозитории GitHub.
