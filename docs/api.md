# REST API устройства

Базовый адрес: `http://<IP устройства>:8000/api/v1`. Интерактивное описание (Swagger) — `http://<IP>:8000/docs`.
Формат — JSON, время — ISO 8601 с часовым поясом устройства, яркость 0..100, цветовая температура в кельвинах.

## Доступ

Все запросы, кроме `GET /health`, требуют заголовок с ключом устройства:

```
X-API-Key: <ключ из device/.env>
```

Нет ключа или ключ неверный → `401`. Если в `.env` ключ пустой, проверка отключена (только для разработки).
По HTTP ключ передаётся открытым текстом: это защита от посторонних в сети, а не от перехвата трафика.

## Ошибки

| Код | Когда |
|---|---|
| 401 | нет или неверный API-ключ |
| 404 | нет такой комнаты, лампы или датчика |
| 409 | действие нарушает правило: авто без датчика онлайн, лампа уже в другой комнате, у комнаты уже есть датчик |
| 422 | неверные данные: яркость вне 0..100, температура вне диапазона, `from >= to` |

Тело ошибки: `{"detail": "текст для человека"}`.

## Основные ресурсы

### Система
| Метод | Путь | Что делает |
|---|---|---|
| GET | `/health` | устройство на связи: `{name, version, runtime: "virtual"\|"hardware", time}` — **без ключа** |
| GET | `/auth/check` | ключ верный → `200 {"ok": true}` |
| GET/PATCH | `/site` | объект: `{name, tariff_rub_per_kwh}` |

### Комнаты
| Метод | Путь | Что делает |
|---|---|---|
| GET | `/rooms` | список комнат с состоянием |
| POST | `/rooms` | создать: `{name, target_lux?}` |
| GET / PATCH / DELETE | `/rooms/{id}` | комната; PATCH `{name?, target_lux?}`; DELETE отвязывает лампы и датчик |
| PATCH | `/rooms/{id}/control` | управление: `{mode?, brightness?, color_mode?, color_temp_k?}` |
| POST | `/rooms/{id}/power` | `{on: true}` — последняя уставка, `{on: false}` — 0 |
| PUT / DELETE | `/rooms/{id}/lamps/{lamp_id}` | привязать / отвязать лампу |
| PUT / DELETE | `/rooms/{id}/sensor/{sensor_id}` | привязать / отвязать датчик |

Пример `GET /rooms/1`:

```json
{
  "id": 1,
  "name": "Гостиная",
  "is_on": true,
  "mode": "auto",
  "brightness": 62,
  "last_brightness": 62,
  "target_lux": 300,
  "color_mode": "circadian",
  "color_temp_k": 3500,
  "sensor": { "id": 1, "status": "online", "lux": 296.4, "cct": 3720 },
  "lamps": [
    { "id": 1, "name": "Люстра", "brightness": 61.8, "color_temp_k": 3510, "power_w": 8.1 },
    { "id": 2, "name": "Торшер", "brightness": 62.0, "color_temp_k": 3500, "power_w": 3.5 }
  ],
  "power_w": 11.6
}
```

`is_on` вычисляется: `brightness > 0`. `brightness` и `color_temp_k` у комнаты — уставки, у ламп — фактические значения (во время плавного перехода они отличаются).

Правила `PATCH /rooms/{id}/control`:
- `brightness` в режиме `auto` переводит комнату в `manual`;
- `color_temp_k` в режиме `circadian` переводит оттенок в `manual`;
- `mode: "auto"` без датчика онлайн → `409`.

### Лампы и датчики (реестры)
| Метод | Путь | Что делает |
|---|---|---|
| GET | `/lamps?free=true` | все лампы (или только свободные): фактическая яркость, K, мощность, комната |
| PATCH | `/lamps/{id}` | `{name}` |
| GET | `/sensors?free=true` | датчики: lux, CCT, статус, комната |
| PATCH | `/sensors/{id}` | `{name}` |

Сами лампы и датчики описываются в `device/device.yaml` (что физически подключено), API их не создаёт.

### История и энергия
| Метод | Путь | Что делает |
|---|---|---|
| GET | `/sensors/{id}/readings?from&to&bucket=minute\|hour` | средние lux и CCT по интервалам |
| GET | `/energy?from&to&bucket=hour\|day&room_id?` | энергия за период — для графика |

Пример `GET /energy?from=2026-10-13T00:00:00%2B05:00&to=2026-10-20T00:00:00%2B05:00&bucket=day`:

```json
{
  "bucket": "day",
  "points": [
    { "ts": "2026-10-13T00:00:00+05:00", "energy_wh": 182.4, "cost_rub": 1.09 },
    { "ts": "2026-10-14T00:00:00+05:00", "energy_wh": 205.0, "cost_rub": 1.23 }
  ],
  "total_kwh": 1.31,
  "total_cost_rub": 7.86,
  "by_room": [ { "room_id": 1, "name": "Гостиная", "energy_wh": 702.5 } ]
}
```

## Только для эмуляции (`RUNTIME=virtual`)

| Метод | Путь | Что делает |
|---|---|---|
| POST | `/sim/daylight` | `{lux}` — задать уличный свет, `{lux: null}` — вернуть суточную кривую |
| POST | `/sim/sensors/{id}/fault` | `{fault: true}` — «оборвать провод» датчика |
| POST | `/sim/clock` | `{time: "19:30"}` — перемотать, `{speed: 600}` — ускорить, `{reset: true}` — текущее время |

В режиме `hardware` эти пути отвечают `404`.

## Позже

Расписания (`/schedules`), мгновенные обновления (`WS /ws/state`), мастер подключения ламп через API (`/hardware/pins`, `/hardware/i2c/scan`).
