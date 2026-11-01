# ДЗ № 4 · План запроса и индексы

Практикум: <https://maximbytecamp.github.io/mongodb_theory_makarov/praktiki/onlayn-razbor-zaprosa/>

## Среда

- MongoDB Community 9.0.4, локальный сервер `mongodb://127.0.0.1:27017`;
- база `logs`, коллекция `events` — 1200 документов, индексов кроме `_id_` нет;
- планы сняты через `explain("executionStats")` скриптом на драйвере Node.js
  (`mongodb`), результат записан в файлы `plan-*.json`.

Перед снятием каждого плана индекс создавался, затем удалялся, поэтому
в коллекции остался только `_id_`. Все числа ниже — реальный вывод сервера
на моей базе.

## Сводная таблица

| Файл | Индекс | nReturned | totalDocsExamined | totalKeysExamined | Шаги плана |
|---|---|---|---|---|---|
| `plan-1.json` | нет | 33 | 1200 | 0 | `COLLSCAN → SORT` |
| `plan-2.json` | `{ service: 1, level: 1, ts: -1, duration_ms: 1 }` | 33 | 33 | 43 | `IXSCAN → FETCH` |
| `plan-3a.json` | `{ duration_ms: 1, service: 1, level: 1, ts: -1 }` | 33 | 33 | 378 | `IXSCAN → SORT → FETCH` |
| `plan-3b.json` | `{ service: 1, level: 1, duration_ms: 1, ts: -1 }` | 33 | 33 | 33 | `IXSCAN → SORT → FETCH` |
| `plan-4-bez.json` | нет | 10 | 1200 | 0 | `COLLSCAN → SORT` |
| `plan-4.json` | `{ level: 1, duration_ms: -1 }` | 10 | 10 | 10 | `IXSCAN → FETCH → LIMIT` |

Индексы коллекции после работы: `_id_` — лишних не осталось
(`db.events.getIndexes()`).

## Задача 1. Запрос без индекса

```js
db.events.find({
  service: "payments",
  level: "error",
  duration_ms: { $gt: 500 }
}).sort({ ts: -1 })
```

`plan-1.json`: `nReturned = 33`, `totalDocsExamined = 1200`,
`totalKeysExamined = 0`, шаги `COLLSCAN → SORT`.

Сервер прочитал все 1200 документов коллекции: `totalDocsExamined` совпадает
с размером коллекции, это признак `COLLSCAN`. Индексов нет, поэтому
`totalKeysExamined = 0`. Отобранные 33 документа пришлось сортировать
в памяти отдельным шагом `SORT` — при росте коллекции это упирается
в лимит памяти сортировки (32 МБ по умолчанию для блокирующей сортировки).

## Задача 2. Индекс по правилу ESR

Запрос разбирается так:

- **Equality** — `service: "payments"` и `level: "error"`;
- **Sort** — `ts: -1`;
- **Range** — `duration_ms: { $gt: 500 }`.

Индекс `{ service: 1, level: 1, ts: -1, duration_ms: 1 }` (`plan-2.json`):
`nReturned = 33`, `totalDocsExamined = 33`, `totalKeysExamined = 43`,
шаги `IXSCAN → FETCH`.

Документов просмотрено ровно 33 — столько и вернул запрос, лишнего чтения нет.
Ключей 43: индекс просканировал диапазон по равенствам, а по `duration_ms`
проверил границы. Шага `SORT` нет — индекс уже отсортирован по `ts`.

## Задача 3. Порядок полей

Два индекса с теми же полями, но в другом порядке:

| Вариант | Индекс | totalKeysExamined | Шаги |
|---|---|---|---|
| А | `{ duration_ms: 1, service: 1, level: 1, ts: -1 }` | 378 | `IXSCAN → SORT → FETCH` |
| Б | `{ service: 1, level: 1, duration_ms: 1, ts: -1 }` | 33 | `IXSCAN → SORT → FETCH` |

В варианте А на первом месте стоит поле из диапазона (`duration_ms`). Индекс
сразу уходит в диапазонное сканирование и просматривает 378 ключей, а
равенства по `service` и `level` проверяет уже после; порядок `ts` при этом
не используется, поэтому появляется `SORT`.

В варианте Б сначала идут оба равенства — они сужают выборку до 33 записей,
и только потом диапазон. Ключей просмотрено 33. `SORT` всё равно остался,
потому что между равенствами и полем сортировки стоит диапазонное поле:
индекс не может одновременно отдать нужный порядок по `ts` и отфильтровать
`duration_ms` диапазоном. Сортировка идёт по 33 документам — это дёшево.
Вывод: равенства ставятся первыми; вариант Б заметно лучше А.

## Задача 4. Самостоятельно

```js
db.events.find({ level: "error" }).sort({ duration_ms: -1 }).limit(10)
```

Без индекса (`plan-4-bez.json`): `nReturned = 10`, `totalDocsExamined = 1200`,
`totalKeysExamined = 0`, шаги `COLLSCAN → SORT` — прочитана вся коллекция
и отсортирована целиком ради десяти документов.

Индекс `{ level: 1, duration_ms: -1 }` (`plan-4.json`): `nReturned = 10`,
`totalDocsExamined = 10`, `totalKeysExamined = 10`,
шаги `IXSCAN → FETCH → LIMIT`.

Здесь правило ESR тоже соблюдено: `level` — равенство, `duration_ms` —
сортировка, а `limit` позволяет остановиться после десяти ключей. Поэтому
и ключей, и документов ровно 10. Для такого запроса годится и вариант
`{ level: 1, duration_ms: -1 }`; направление `-1` в индексе должно совпадать
с направлением сортировки.

## Файлы

- `plan-1.json` — запрос 1 без индекса;
- `plan-2.json` — запрос 1 с индексом по ESR;
- `plan-3a.json` — вариант А задачи 3;
- `plan-3b.json` — вариант Б задачи 3;
- `plan-4-bez.json` — запрос 2 без индекса;
- `plan-4.json` — запрос 2 с индексом.

Планы можно открыть в визуализаторе
<https://dfrancour.dev/tools/mongodb-paste-the-plan>, вставив содержимое файла.
