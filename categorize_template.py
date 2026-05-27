#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OpenCart Product Categorizer Template
======================================
EN: A reusable skeleton for building product categorization scripts
    for OpenCart 3.x / ocStore.
    Supports dry-run mode, cleanup of technical categories,
    and quality filtering (image, price, name).

UA: Багаторазовий шаблон для скриптів категоризації товарів
    в OpenCart 3.x / ocStore.
    Підтримує dry-run, очищення технічних категорій
    та фільтрацію якості (фото, ціна, назва).

Usage:
    # Dry-run (no DB changes):
    python3 categorize_template.py

    # Real run (DRY_RUN=False):
    python3 categorize_template.py

    # Cron every Friday 6am:
    # 0 6 * * 5  python3 /path/to/categorize_template.py
"""

import pymysql
import re
import logging
import os
from datetime import datetime

# ---------------------------------------------------------------------------
# CONFIG  (override via environment variables or .env file)
# ---------------------------------------------------------------------------
DB_HOST    = os.environ.get('DB_HOST',    'localhost')
DB_USER    = os.environ.get('DB_USER',    'ocuser')
DB_PASS    = os.environ.get('DB_PASS',    '')
DB_NAME    = os.environ.get('DB_NAME',    'ocstore')
DB_CHARSET = 'utf8mb4'

# UA: Ніколи не хардкодь облікові дані. Використовуй змінні середовища або .env файл.

DRY_RUN = os.environ.get('DRY_RUN', 'True').lower() != 'false'
# UA: За замовчуванням True. Щоб вимкнути: DRY_RUN=False python3 ...

# Language IDs
LANG_RU = 1   # Russian
LANG_UA = 3   # Ukrainian

# Manufacturer IDs to process
# UA: Вкажи ID виробників з таблиці oc_manufacturer
MANUFACTURER_IDS = [1, 2, 3]

# Root category ID and fallback
CAT_ROOT     = 100   # Root category
CAT_FALLBACK = 101   # Fallback for unmatched products
# UA: Вкажи реальні ID категорій зі своєї бази

# Categories to clean up after categorization (staging/technical)
CLEANUP_CATEGORIES = [999, 998]
# UA: Категорії, з яких треба видалити товар після успішної категоризації

# Brand name aliases
BRAND_ALIASES = {
    'Mercedes-Benz': 'Mercedes',
    'VW': 'Volkswagen',
}
# UA: Маппінг нестандартних назв брендів

LOG_FILE = os.environ.get('LOG_FILE', '/tmp/categorize.log')

# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)-5s %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler(),
    ]
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# DB CONNECTION
# ---------------------------------------------------------------------------
def get_conn():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset=DB_CHARSET,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------
def load_category_map(conn):
    """
    EN: Load subcategories of CAT_ROOT into a dict {name: category_id}.
        Extend this function to load deeper hierarchies if needed.
    UA: Завантажує підкатегорії CAT_ROOT у словник {name: category_id}.
    """
    cur = conn.cursor()
    cur.execute(
        "SELECT c.category_id, cd.name "
        "FROM oc_category c "
        "JOIN oc_category_description cd ON c.category_id = cd.category_id "
        "WHERE c.parent_id = %s AND cd.language_id = %s",
        (CAT_ROOT, LANG_UA)
    )
    result = {row['name'].strip(): row['category_id'] for row in cur.fetchall()}
    cur.close()
    log.info(f"Loaded {len(result)} categories under CAT_ROOT={CAT_ROOT}")
    return result


def get_existing_categories(cur, product_id):
    """
    EN: Returns a set of category IDs the product already belongs to.
    UA: Повертає set category_id, до яких товар вже належить.
    """
    cur.execute(
        "SELECT category_id FROM oc_product_to_category WHERE product_id = %s",
        (product_id,)
    )
    return {row['category_id'] for row in cur.fetchall()}


def classify_product(name):
    """
    EN: Parse product name and return (target_category_id, matched_names).
        Implement your own matching logic here.
        Return (CAT_FALLBACK, []) if no match found.

    UA: Розпізнає назву товару і повертає (category_id, [matched_names]).
        Реалізуй власну логіку тут.
        Якщо збігів немає — повертає (CAT_FALLBACK, []).

    Examples:
        'Toyota Camry 2018' -> (CAT_ROOT, ['Toyota'])
        'Unknown item'      -> (CAT_FALLBACK, [])
    """
    name_lower = name.lower()
    # TODO: implement your matching logic here
    match = re.search(r'for\s+(\w+)', name_lower)
    if match:
        brand = match.group(1).capitalize()
        brand = BRAND_ALIASES.get(brand, brand)
        return CAT_ROOT, [brand]
    return CAT_FALLBACK, []


def add_to_category(cur, product_id, category_id, main=0, existing=None, dry_run=True):
    """
    EN: Insert product-category link. Skips if already exists.
        In dry_run mode only logs the intended action.
    UA: Додає зв'язок товар-категорія. Пропускає якщо вже існує.
        В dry_run лише логує дію.
    """
    if existing is not None and category_id in existing:
        return False
    if dry_run:
        log.info(f"  DRY  product={product_id} cat={category_id} main={main}")
        return True
    cur.execute(
        "INSERT IGNORE INTO oc_product_to_category "
        "(product_id, category_id, main_category) VALUES (%s, %s, %s)",
        (product_id, category_id, main)
    )
    return True


def remove_from_cleanup(cur, product_id, existing, dry_run=True):
    """
    EN: Remove product from staging/technical categories after successful categorization.
    UA: Видаляє товар із технічних/staging категорій після успішної категоризації.
    """
    to_remove = set(CLEANUP_CATEGORIES) & existing
    for cat_id in to_remove:
        if dry_run:
            log.info(f"  DRY- product={product_id} remove from cat={cat_id}")
        else:
            cur.execute(
                "DELETE FROM oc_product_to_category "
                "WHERE product_id = %s AND category_id = %s",
                (product_id, cat_id)
            )


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    log.info("-" * 60)
    log.info(f"Categorizer start  DRY_RUN={DRY_RUN}")
    if DRY_RUN:
        log.info("DRY RUN MODE — no DB changes will be made")
        log.info("To run for real: DRY_RUN=False python3 categorize_template.py")

    conn = get_conn()
    try:
        category_map = load_category_map(conn)

        cur = conn.cursor()
        cur.execute(
            "SELECT p.product_id, pd.name "
            "FROM oc_product p "
            "JOIN oc_product_description pd ON p.product_id = pd.product_id "
            "WHERE p.manufacturer_id IN %s "
            "  AND pd.language_id = %s "
            "  AND pd.name != '' "
            "  AND p.price > 0 "
            "  AND p.image IS NOT NULL "
            "  AND p.image != '' "
            "  AND p.image != 'no_image.png' "
            "ORDER BY p.product_id",
            (tuple(MANUFACTURER_IDS), LANG_UA)
        )
        products = cur.fetchall()
        cur.close()
        log.info(f"Found {len(products)} products to process")

        stats = {'categorized': 0, 'fallback': 0, 'already_ok': 0, 'nomatch': 0}

        for prod in products:
            product_id = prod['product_id']
            name       = prod['name'].strip()

            cur = conn.cursor()
            existing = get_existing_categories(cur, product_id)
            target_cat, matched_names = classify_product(name)

            if matched_names:
                # --- matched branch ---
                categorized = False
                valid_cats = set(category_map.values())

                if (valid_cats & existing) and not (set(CLEANUP_CATEGORIES) & existing):
                    stats['already_ok'] += 1
                    cur.close()
                    continue

                log.info(f"MATCH id={product_id} names={matched_names}  {name}")
                add_to_category(cur, product_id, CAT_ROOT, existing=existing, dry_run=DRY_RUN)

                for matched_name in matched_names:
                    cat_id = category_map.get(matched_name)
                    if not cat_id:
                        normalized = BRAND_ALIASES.get(matched_name, matched_name)
                        cat_id = category_map.get(normalized)
                    if not cat_id:
                        log.warning(f"  NOMATCH name={matched_name}")
                        stats['nomatch'] += 1
                        continue
                    add_to_category(cur, product_id, cat_id, main=1, existing=existing, dry_run=DRY_RUN)
                    categorized = True

                if categorized:
                    remove_from_cleanup(cur, product_id, existing, dry_run=DRY_RUN)
                    stats['categorized'] += 1

            else:
                # --- fallback branch ---
                if target_cat in existing and not (set(CLEANUP_CATEGORIES) & existing):
                    stats['already_ok'] += 1
                    cur.close()
                    continue

                log.info(f"FALLBACK id={product_id} cat={target_cat}  {name}")
                add_to_category(cur, product_id, target_cat, main=1, existing=existing, dry_run=DRY_RUN)
                remove_from_cleanup(cur, product_id, existing, dry_run=DRY_RUN)
                stats['fallback'] += 1

            if not DRY_RUN:
                conn.commit()
            cur.close()

        log.info("-" * 60)
        log.info(
            f"Done:  categorized={stats['categorized']}  "
            f"fallback={stats['fallback']}  "
            f"already_ok={stats['already_ok']}  "
            f"nomatch={stats['nomatch']}"
        )
        if DRY_RUN:
            log.info("DRY RUN complete — no changes were made to the database")

    except Exception as e:
        log.exception(f"CRITICAL ERROR: {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
