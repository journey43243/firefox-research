# firefox-research

# Инструкции по запуску
1. Создать директории Cases и Logs в корне проекта
2. С помощью команды ```bash
   pip install -r requirements.txt```
   исполненой в корне проекта, установить зависимости
4. С помощью команды ```bash
   python Run.py```, исполненой в корневой директории запустить проект

# Структура данных Firefox

## 1. Профили
**Файл**
```
%appdata%\Mozilla\Firefox\profiles.ini
```

**Пример содержимого**
```
[Install308046B0AF4A39CB]
Default=Profiles/g579o6f5.default-release
Locked=1

[Profile1]
Name=default
IsRelative=1
Path=Profiles/fcy693hd.default
Default=1

[Profile0]
Name=default-release
IsRelative=1
Path=Profiles/g579o6f5.default-release

[General]
StartWithLastProfile=1
Version=2

```

## 2. История посещений
**Файл:**
```
%appdata%\Mozilla\Firefox\Profiles\<профиль>\places.sqlite
```

**Таблица:** `moz_places`

| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | int (PK) | Уникальный идентификатор записи |
| `url` | text | URL страницы |
| `title` | text | Название вкладки |
| `rev_host` | text | Домен в обратном порядке ya.ru. -> .ur.ay|
| `visit_count` | int | Количество посещений |
| `hidden` | int | 0 — отображается в истории, 1 — скрыт |
| `typed` | int | 1 — введён вручную, 0 — переход по ссылке |
| `frecency` | int | Метрика «частота + недавность» |
| `last_visit_date` | int | Время последнего посещения (UNIX Timestamp) |
| `guid` | text | Уникальный идентификатор (для Firefox Sync) |
| `foreign_count` | int | Кол-во внешних ссылок (закладки, аннотации) |
| `url_hash` | int | Хэш URL |
| `description` | text | Описание страницы (редко используется сайтами) |
| `site_name` | text | Обычно NULL |

---

## 3. Загрузки
**Файл:**
```
%appdata%\Mozilla\Firefox\Profiles\<профиль>\places.sqlite
```

**Таблица:** `moz_annost`

| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | int | Идентификатор |
| `place_id` | FK (moz_places.id) | Ссылка на URL |
| `anno_attribute_id` | int | 1 — метаданные, 2 — URI |
| `content` | text | JSON-строка с параметрами загрузки |
| `flags` | int | Не используется |
| `dateAdded` | int | Время добавления (UNIX Timestamp) |
| `lastModified` | int | Время изменения (UNIX Timestamp) |

**Пример структуры `content`:**
```json
{
  "state": 1,
  "deleted": false,
  "endTime": 1714782228000,
  "fileSize": 1234567
}
```

---

## 4. Закладки
**Файл:**
```
%appdata%\Mozilla\Firefox\Profiles\<профиль>\places.sqlite
```

**Таблица:** `moz_bookmarks`

| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | int (PK) | Идентификатор |
| `type` | int | 1 — закладка, 2 — папка, 3 — разделитель |
| `fk` | int | Внешний ключ на moz_places.id |
| `parent` | int | Родительская папка |
| `position` | int | Индекс в папке |
| `title` | text | Имя закладки |
| `dateAdded` | int | Дата добавления (UNIX Timestamp) |
| `lastModified` | int | Дата изменения (UNIX Timestamp) |
| `guid` | text | Идентификатор Sync |
| `syncStatus` | int | 0 — не изменено, 1 — локально, 2 — синхронизировано |

---

## 5. Расширения

Файл **extensions.json** хранит информацию обо всех установленных расширениях, темах и плагинах для конкретного профиля Firefox.

**Путь:**
```
%appdata%\Mozilla\Firefox\Profiles\<профиль>\extensions.json
```

**Общая структура**
```json
{
  "schemaVersion": <int>,
  "addons": [ <AddonObject>, ... ]
}
```

| Поле | Тип | Описание |
|------|-----|-----------|
| `schemaVersion` | int | Версия схемы структуры файла (меняется с обновлениями Firefox) |
| `addons` | array of objects | Список объектов, каждый описывает одно расширение, тему или плагин |

**Структура конкретного расширения**
```json
{
            "id": "ipvfoo@pmarks.net",
            "syncGUID": "{7df26574-1f96-4dad-83de-5aa37c9ff217}",
            "version": "2.27",
            "type": "extension",
            "loader": null,
            "updateURL": null,
            "installOrigins": null,
            "manifestVersion": 3,
            "optionsURL": "options.html",
            "optionsType": 5,
            "optionsBrowserStyle": false,
            "aboutURL": null,
            "defaultLocale": {
                "name": "IPvFoo",
                "description": "Display the server IP address, with a realtime summary of IPv4, IPv6, and HTTPS information across all page elements.",
                "creator": null,
                "homepageURL": "https://github.com/pmarks-net/ipvfoo",
                "developers": null,
                "translators": null,
                "contributors": null
            },
            "visible": true,
            "active": true,
            "userDisabled": false,
            "appDisabled": false,
            "embedderDisabled": false,
            "installDate": 1761479631776,
            "updateDate": 1761479631776,
            "applyBackgroundUpdates": 1,
            "path": "C:\\Users\\1\\AppData\\Roaming\\Mozilla\\Firefox\\Profiles\\g579o6f5.default-release\\extensions\\ipvfoo@pmarks.net.xpi",
            "skinnable": false,
            "sourceURI": "https://addons.mozilla.org/firefox/downloads/file/4598160/ipvfoo-2.27.xpi",
            "releaseNotesURI": null,
            "softDisabled": false,
            "foreignInstall": false,
            "strictCompatibility": true,
            "locales": [],
            "targetApplications": [{
                    "id": "toolkit@mozilla.org",
                    "minVersion": "115.0",
                    "maxVersion": null
                }
            ],
            "targetPlatforms": [],
            "signedState": 2,
            "signedTypes": [2, 1],
            "signedDate": 1760477439000,
            "seen": true,
            "dependencies": [],
            "incognito": "spanning",
            "userPermissions": {
                "permissions": ["contextMenus", "storage", "webNavigation", "webRequest"],
                "origins": [],
                "data_collection": []
            },
            "optionalPermissions": {
                "permissions": [],
                "origins": ["<all_urls>"],
                "data_collection": []
            },
            "requestedPermissions": {
                "permissions": [],
                "origins": ["<all_urls>"],
                "data_collection": []
            },
            "icons": {
                "16": "icon16.png",
                "128": "icon128.png"
            },
            "iconURL": null,
            "blocklistAttentionDismissed": false,
            "blocklistState": 0,
            "blocklistURL": null,
            "startupData": null,
            "hidden": false,
            "installTelemetryInfo": {
                "source": "amo",
                "sourceURL": "https://addons.mozilla.org/ru/firefox/addon/ipvfoo/",
                "method": "amWebAPI"
            },
            "recommendationState": null,
            "rootURI": "jar:file:///C:/Users/1/AppData/Roaming/Mozilla/Firefox/Profiles/g579o6f5.default-release/extensions/ipvfoo@pmarks.net.xpi!/",
            "location": "app-profile"
        }
```

---

**Описание полей**

| Поле | Тип | Описание |
|------|-----|-----------|
| `id` | string | Уникальный идентификатор расширения (например, `ipvfoo@pmarks.net`). |
| `syncGUID` | string | GUID для синхронизации расширения через Firefox Sync. |
| `version` | string | Версия расширения. |
| `type` | string | Тип объекта — обычно `extension`, но может быть также `theme` или `plugin`. |
| `loader` | null / string | Тип загрузчика расширения (в современных версиях Firefox обычно `null`). |
| `updateURL` | null / string | URL для проверки обновлений (если указан разработчиком). |
| `installOrigins` | null / array | Источники установки расширения, если оно установлено не из AMO. |
| `manifestVersion` | int | Версия манифеста расширения (2 или 3). |
| `optionsURL` | string | Путь к странице настроек расширения. |
| `optionsType` | int | Тип интерфейса опций (например, 5 — встроенная страница). |
| `optionsBrowserStyle` | bool | Использует ли страница настроек встроенный стиль браузера. |
| `aboutURL` | null / string | URL страницы “О расширении” (если есть). |
| `defaultLocale` | object | Содержит локализованные сведения о расширении: `name`, `description`, `homepageURL`, `creator`, `developers`, `contributors`. |
| `visible` | bool | Видимо ли расширение пользователю (в интерфейсе). |
| `active` | bool | Активно ли расширение в данный момент. |
| `userDisabled` | bool | Отключено ли пользователем. |
| `appDisabled` | bool | Отключено ли приложением (например, несовместимо). |
| `embedderDisabled` | bool | Отключено ли внешним компонентом (редко используется). |
| `installDate` | int | Время установки (UNIX timestamp в миллисекундах). |
| `updateDate` | int | Время последнего обновления. |
| `applyBackgroundUpdates` | int | Режим обновлений: 0 — никогда, 1 — по умолчанию, 2 — всегда. |
| `path` | string | Полный путь к файлу расширения `.xpi` или директории. |
| `skinnable` | bool | Может ли расширение менять темы оформления. |
| `sourceURI` | string | URL источника установки (например, с AMO). |
| `releaseNotesURI` | null / string | Ссылка на заметки к релизу (если указана). |
| `softDisabled` | bool | Мягкое отключение (например, из-за несовместимости, но без удаления). |
| `foreignInstall` | bool | Установлено ли расширение не через Firefox Add-ons. |
| `strictCompatibility` | bool | Требует ли точного совпадения версии Firefox. |
| `locales` | array | Список дополнительных локалей (обычно пуст). |
| `targetApplications` | array | Массив объектов, описывающих совместимые приложения (например, `toolkit@mozilla.org`). |
| `targetPlatforms` | array | Массив поддерживаемых платформ (часто пуст). |
| `signedState` | int | Статус подписи: 0 — не подписано, 2 — подписано Mozilla. |
| `signedTypes` | array | Массив типов подписи (например, `[2, 1]`). |
| `signedDate` | int | Время подписи расширения (UNIX timestamp). |
| `seen` | bool | Было ли расширение уже загружено и обработано Firefox. |
| `dependencies` | array | Зависимости от других дополнений (часто пусто). |
| `incognito` | string | Режим работы с приватными окнами: `spanning`, `not_allowed` и т.д. |
| `userPermissions` | object | Разрешения, запрошенные пользователем (`permissions`, `origins`, `data_collection`). |
| `optionalPermissions` | object | Необязательные разрешения. |
| `requestedPermissions` | object | Разрешения, запрошенные при установке. |
| `icons` | object | Список иконок в разных разрешениях (`16`, `128` и т.д.). |
| `iconURL` | null / string | URL основной иконки. |
| `blocklistAttentionDismissed` | bool | Отмечено ли пользователем предупреждение о блокировке. |
| `blocklistState` | int | Состояние в чёрном списке (0 — нет, >0 — есть). |
| `blocklistURL` | null / string | URL страницы блокировки (если есть). |
| `startupData` | null / object | Данные для инициализации при запуске (редко используется). |
| `hidden` | bool | Скрыто ли расширение из списка (например, системное). |
| `installTelemetryInfo` | object | Источник и способ установки (`source`, `sourceURL`, `method`). |
| `recommendationState` | null / int | Состояние рекомендаций (используется AMO). |
| `rootURI` | string | URI корневого ресурса (`jar:file:///...xpi!/`). |
| `location` | string | Местоположение установки (`app-profile`, `system`, `user`). |

---
## 6. Кэш
### Шаг 1: Поиск нужного файла
- В папке профиля нашли файл `favicons.sqlite`
- Запустили файл в HxD с правми администратора
  
**favicons.sqlite** - это база данных Firefox, отвечающая за кэширование и управление иконками веб-сайтов (favicons).
  
**Конкретные функции:**

#### 1. Хранение favicon-иконок
- Сохраняет маленькие значки сайтов (16x16, 32x32 пикселей)
- Кэширует иконки для быстрой загрузки при повторном посещении
- Поддерживает различные форматы: PNG, ICO, SVG

#### 2. Связь иконок с URL-адресами
- Создает соответствие между иконками и посещенными страницами
- Хранит связи в таблице moz_icons_to_pages
- Позволяет быстро находить иконку для любого URL из истории

#### 3. Оптимизация производительности
- Уменьшает количество HTTP-запросов к сайтам
- Ускоряет отображение вкладок, закладок и истории
- Снижает потребление трафика
  
## Шаг 3: Получение информации
- Заголовок SQLite: `SQLite format 3`
- В HEX: `53 51 4C 69 74 65 20 66 6F 72 6D 61 74 20 33`
- Это БД SQLite, но она содержит бинарные данные иконок и текстовые URL

**Обнаруженные таблицы в файле:**
- `moz_icons` - основная таблица с иконками. В HEX:6D 6F 7A 5F 69 63 6F 6E 73. Смещение: 76360
- `moz_pages_w_icons` - таблица с URL страниц. В HEX: 6D 6F 7A 5F 70 61 67 65 73 5F 77 5F 69 63 6F 6E 73. Смещение: 76752   
- `moz_icons_to_pages` - связующая таблица. В HEX:6D 6F 7A 5F 69 63 6F 6E 73 5F 74 6F 5F 70 61 67 65 73. Смещение: 75772

## Шаг 4: Анализ контекста найденных URL
### Для каждого найденного URL:
#### Записали полный URL, который виден в правой панели:
- https://support.mozilla.org/products/firefox (технический сайт). В HEX: 68 74 74 70 73 3A 2F 2F 73 75 70 70 6F 72 74 2E 6D 6F 7A 69 6C 6C 61 2E 6F 72 67 2F 70 72 6F 64 75 63 74 73 2F 66 69 72 65 66 6F 78. Смещение: 274053
  
- https://yastatic.net/s3/web4static/_/v2/static/media/AppFavicon-Icon_size64_ru (сервис Яндекса). В HEX: 68 74 74 70 73 3A 2F 2F 79 61 73 74 61 74 69 63 2E 6E 65 74 2F 73 33 2F 77 65 62 34 73 74 61 74 69 63 2F 5F 2F 76 32 2F 73 74 61 74 69 63 2F 6D 65 64 69 61 2F 41 70 70 46 61 76 69 63 6F 6E 2D 49 63 6F 6E 5F 73 69 7A 65 36 34 5F 72 75. Смещение:225421
  
- https://yastatic.net/s3/home-static/_/nova/B5CxuyJ3.png (прямой путь к иконке). В HEX:68 74 74 70 73 3A 2F 2F 79 61 73 74 61 74 69 63 2E 6E 65 74 2F 73 33 2F 68 6F 6D 65 2D 73 74 61 74 69 63 2F 5F 2F 6E 6F 76 61 2F 42 35 43 78 75 79 4A 33 2E 70 6E 67. Смещение: 230724

- https://yastatic.net/s3/home-static/_/nova/Bbcs5LWW.png. В HEX:68 74 74 70 73 3A 2F 2F 79 61 73 74 61 74 69 63 2E 6E 65 74 2F 73 33 2F 68 6F 6D 65 2D 73 74 61 74 69 63 2F 5F 2F 6E 6F 76 61 2F 42 62 63 73 35 4C 57 57 2E 70 6E 67. Смещение: 232157
  
- https://max.zolotyh.su/favicon.ico (персональный сайт/ реальный favicon). В HEX: 68 74 74 70 73 3A 2F 2F 6D 61 78 2E 7A 6F 6C 6F 74 79 68 2E 73 75 2F 66 61 76 69 63 6F 6E 2E 69 63 6F. Смещение: 236504
  
- https://dzen.ru/logo-redesign-192.png (прямой путь к иконке). В HEX: 68 74 74 70 73 3A 2F 2F 64 7A 65 6E 2E 72 75 2F 6C 6F 67 6F 2D 72 65 64 65 73 69 67 6E 2D 31 39 32 2E 70 6E 67. Смещение: 251503
  
- https://dzen.ru/logo-redesign-48.svg (прямой путь к иконке). В HEX: 68 74 74 70 73 3A 2F 2F 64 7A 65 6E 2E 72 75 2F 6C 6F 67 6F 2D 72 65 64 65 73 69 67 6E 2D 34 38 2E 73 76 67. Смещение: 262506
  
- http://www.w3.org/2000/svg (технические стандарты). В HEX: 68 74 74 70 3A 2F 2F 77 77 77 2E 77 33 2E 6F 72 67 2F 32 30 30 30 2F 73 76 67. Смещение: 262672
  
- https://www.mozilla.org/about/ (технический сайт). В HEX: 68 74 74 70 73 3A 2F 2F 77 77 77 2E 6D 6F 7A 69 6C 6C 61 2E 6F 72 67 2F 61 62 6F 75 74 2F.   265613
  
- https://www.mozilla.org/contribute/ (технический сайт).  В HEX: 68 74 74 70 73 3A 2F 2F 77 77 77 2E 6D 6F 7A 69 6C 6C 61 2E 6F 72 67 2F 63 6F 6E 74 72 69 62 75 74 65 2F. Смещение: 266645
  
- https://support.mozilla.org (технический сайт). В HEX: 68 74 74 70 73 3A 2F 2F 73 75 70 70 6F 72 74 2E 6D 6F 7A 69 6C 6C 61 2E 6F 72 67. Смещение: 267705
  
- https://yandex.ru/search/ (сервис Яндекса). В HEX: 68 74 74 70 73 3A 2F 2F 79 61 6E 64 65 78 2E 72 75 2F 73 65 61 72 63 68. Смещение: 475711
  
- https://ya.ru/search/?text=ArsenyBalakin&lr=5 (поисковый запрос). В HEX: 68 74 74 70 73 3A 2F 2F 79 61 2E 72 75 2F 73 65 61 72 63 68 2F 3F 74 65 78 74 3D 41 72 73 65 6E 79 42 61 6C 61 6B 69 6E 26 6C 72 3D 35. Смещение: 476563
- 
**Ключевая находка:** 
  - lr=5 - регион поиска: Москва
  - W3C - консорциум веб-стандартов
  - SVG - формат векторной графики
    
## Шаг 5: Поиск URL иконок
**Поиск: favicon.ico или favicon:**
- https://max.zolotyh.su/favicon.ico

## Шаг 6: Поиск бинарных данных PNG
- Поиск HEX-значений: `89 50 4E 47`
- Это сигнатура PNG файлов
- В текстовом виде отображается как `‰PNG`

**Найденные смещения:**
- смещение 225567
- смещение 231026  
- смещение 232264
- смещение 236563
- смещение 243224
- смещение 244541
- смещение 247301
- смещение 250577
- смещение 251566
- смещение 270157
- смещение 274144

## Выводы
### Результаты исследования бинарных данных в файле favicons.sqlite:

**1. Персональная идентификационная информация**
- Местонахождение: Смещение 476563 - URL с поисковым запросом text=ArsenyBalakin&lr=5
- Содержание: Имя пользователя "ArsenyBalakin" и геолокация (Москва, lr=5)
- Значимость: Прямая идентификация личности и местоположения

**2. История посещения веб-сайтов**
- Местонахождение: Многочисленные смещения (225421, 230724, 236504, 251503 и др.)
- Содержание: Полные URL посещенных сайтов: Сервисы Яндекса (поиск, Дзен), Технические ресурсы Mozilla, Персональный домен max.zolotyh.su
- Значимость: Полная картина веб-активности пользователя

**3. Бинарные данные графических файлов**
- Местонахождение: Смещения 225567, 231026, 232264, 236563 и др.
- Содержание: PNG изображения (сигнатура 89 50 4E 47)
- Значимость: Визуальные доказательства посещения сайтов через favicon-иконки

**4. Метаданные браузерной активности**
- Местонахождение: Смещения 76360, 76752, 75772
- Содержание: Структуры таблиц БД (moz_icons, moz_pages_w_icons)
- Значимость: Организационная информация о хранении данных активности

## Заключение: 
- В бинарных файлах Firefox содержится комплексная информация о пользователе, включая персональные идентификаторы, географические данные, полную историю браузинга и визуальные артефакты посещенных сайтов, что подтверждает наличие значимой информации в бинарном формате, доступной для извлечения через HEX-редактор.
