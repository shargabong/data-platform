"""Практическая работа 01 · Каталог товаров.

Задача 1 — страница витрины каталога из базы shop.
Задача 2 — приёмка поставки в песочнице sandbox.

Запуск:
    python solution.py
Адрес сервера можно переопределить переменной MONGO_URI.
"""

import os

from pymongo import MongoClient
from pymongo.errors import BulkWriteError

URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(URI)

shop = client["shop"]["products"]       # эталон: только читаем
sandbox = client["sandbox"]["products"]  # песочница: здесь меняем

PAGE_FIELDS = {"_id": 0, "sku": 1, "title": 1, "price": 1, "rating": 1}


def catalog_page(category=None, page=1, per_page=5, sort_field="price", desc=True):
    """Одна страница каталога: (items, total)."""
    query = {}
    if category:
        query["category"] = category

    total = shop.count_documents(query)
    direction = -1 if desc else 1
    skip = (page - 1) * per_page

    items = list(
        shop.find(query, PAGE_FIELDS)
        .sort([(sort_field, direction), ("sku", 1)])
        .skip(skip)
        .limit(per_page)
    )
    return items, total


def print_catalog():
    print("=" * 60)
    print("ЗАДАЧА 1 · витрина каталога")
    print("=" * 60)

    items, total = catalog_page(category="ноутбуки", page=1, per_page=3)
    print(f"\nНоутбуки, страница 1 из 2 (всего {total}):")
    for item in items:
        print(f"  {item['price']:>7} ₽  {item['title']:<32} рейтинг {item['rating']}")

    items, _ = catalog_page(category="ноутбуки", page=2, per_page=3)
    print("\nСтраница 2:")
    for item in items:
        print(f"  {item['price']:>7} ₽  {item['title']:<32} рейтинг {item['rating']}")

    items, total = catalog_page(page=1, per_page=5)
    print(f"\nВесь каталог, топ-5 по цене (всего {total}):")
    for item in items:
        print(f"  {item['price']:>7} ₽  {item['title']}")

    items, total = catalog_page(category="ноутбуки", page=9, per_page=3)
    print(f"\nСтраница 9: найдено {len(items)} товаров, total всё ещё {total}")


ARRIVED = {"SKU-NB-001": 5, "SKU-PH-006": 12, "SKU-PR-010": 3}

NEW_PRODUCTS = [
    {"_id": "p-101", "sku": "SKU-AC-101", "title": "Подставка для ноутбука",
     "brand": "OEM", "category": "аксессуары", "price": 2490, "reviews": 0},
    {"_id": "p-102", "sku": "SKU-AC-102", "title": "Чехол для планшета",
     "brand": "OEM", "category": "аксессуары", "price": 1890, "reviews": 0},
]

DISCONTINUED = ["SKU-CP-018"]


def receive_supply():
    print("\n" + "=" * 60)
    print("ЗАДАЧА 2 · приёмка поставки")
    print("=" * 60)

    report = {}

    updated = 0
    for sku, quantity in ARRIVED.items():
        result = sandbox.update_one({"sku": sku}, {"$inc": {"qty_total": quantity}})
        if result.matched_count == 0:
            print(f"  ВНИМАНИЕ: артикул {sku} не найден")
        updated += result.modified_count
    report["остатки обновлены"] = updated

    try:
        inserted = sandbox.insert_many(NEW_PRODUCTS, ordered=False)
        report["новых позиций"] = len(inserted.inserted_ids)
    except BulkWriteError as error:
        duplicates = len(error.details["writeErrors"])
        report["новых позиций"] = len(NEW_PRODUCTS) - duplicates
        print(f"  {duplicates} позиций уже были в каталоге — пропущены")

    query = {"sku": {"$in": DISCONTINUED}}
    print(f"\n  под снятие с продажи попало: {sandbox.count_documents(query)}")
    for doc in sandbox.find(query, {"_id": 1, "title": 1, "price": 1}):
        print(f"    {doc}")
    report["снято с продажи"] = sandbox.delete_many(query).deleted_count

    accessories = {"category": "аксессуары"}
    print(f"\n  бесплатная доставка коснётся: {sandbox.count_documents(accessories)} товаров")
    result = sandbox.update_many(accessories, {"$set": {"free_shipping": True}})
    report["бесплатная доставка"] = result.modified_count

    report["итого в каталоге"] = sandbox.count_documents({})

    print("\nОтчёт о приёмке:")
    for name, value in report.items():
        print(f"  {name:<24} {value}")


if __name__ == "__main__":
    print_catalog()
    receive_supply()
    client.close()
