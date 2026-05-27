# OpenCart Product Categorizer Template

A reusable Python skeleton for building product categorization scripts for OpenCart 3.x / ocStore.

## Features

- Dry-run mode by default (no DB changes until you explicitly enable)
- Quality filter: only processes products with image, name, price > 0
- Duplicate-safe: uses `INSERT IGNORE`, skips already-categorized products
- Cleanup support: removes products from staging/technical categories after categorization
- Brand aliases: maps non-standard names (e.g. `Mercedes-Benz` → `Mercedes`)
- Structured logging to both file and stdout
- Cron-ready: designed for scheduled weekly runs

## Requirements

```bash
pip install pymysql
```

## Configuration

| Variable | Description | Default |
|----------|-------------|----------|
| `DB_HOST` | MySQL host | `localhost` |
| `DB_USER` | MySQL user | `ocuser` |
| `DB_PASS` | MySQL password | *(required)* |
| `DB_NAME` | Database name | `ocstore` |
| `DRY_RUN` | Safe mode, no DB writes | `True` |
| `LOG_FILE` | Path to log file | `/tmp/categorize.log` |

> Never hardcode credentials. Use environment variables or a `.env` file.

## Usage

**Step 1:** Dry run (safe, no DB changes)
```bash
python3 categorize_template.py
```

**Step 2:** Review the log
```bash
grep MATCH /tmp/categorize.log | head -20
grep NOMATCH /tmp/categorize.log
```

**Step 3:** Run for real
```bash
DRY_RUN=False python3 categorize_template.py
```

**Cron** (every Friday at 6am):
```cron
0 6 * * 5 DRY_RUN=False python3 /path/to/categorize_template.py
```

## How it works

```
Products (filtered by manufacturer_id, quality)
         ↓
  classify_product(name)
         ↓
  match found?  →  no match
       ↓                ↓
 Add to CAT_ROOT    Add to CAT_FALLBACK
 Add to subcategory
 Remove from CLEANUP_CATEGORIES
```

## Customization

1. Set your category IDs in the configuration section
2. Set your manufacturer IDs in `MANUFACTURER_IDS`
3. Implement `classify_product(name)` — your matching logic goes here
4. Add brand aliases to `BRAND_ALIASES` as needed

**Example: categorizing by car brand:**
```python
def classify_product(name):
    match = re.search(r'for\s+(\w+)', name)
    if match:
        brand = match.group(1).capitalize()
        brand = BRAND_ALIASES.get(brand, brand)
        return CAT_ROOT, [brand]
    return CAT_FALLBACK, []
```

**Example: categorizing by keyword:**
```python
def classify_product(name):
    name_lower = name.lower()
    if 'radio' in name_lower or 'stereo' in name_lower:
        return CAT_HEAD_UNITS, ['head_unit']
    if 'camera' in name_lower:
        return CAT_CAMERAS, ['camera']
    return CAT_FALLBACK, []
```

## Log output example

```
2026-01-01 12:00:00 INFO  Categorizer start DRY_RUN=True
2026-01-01 12:00:00 INFO  DRY RUN MODE — no DB changes will be made
2026-01-01 12:00:00 INFO  Loaded 25 categories under CAT_ROOT=100
2026-01-01 12:00:00 INFO  Found 500 products to process
2026-01-01 12:00:00 INFO  MATCH id=12345 names=['Toyota'] Toyota Camry 2018
2026-01-01 12:00:00 INFO  DRY  product=12345 cat=100 main=0
2026-01-01 12:00:00 INFO  DRY  product=12345 cat=101 main=1
2026-01-01 12:00:00 INFO  DRY- product=12345 remove from cat=999
2026-01-01 12:00:00 INFO  Done: categorized=450 fallback=20 already_ok=25 nomatch=5
2026-01-01 12:00:00 INFO  DRY RUN complete — no changes were made to the database
```

## Database tables used

| Table | Operation |
|-------|-----------|
| `oc_product` | READ |
| `oc_product_description` | READ |
| `oc_category` | READ |
| `oc_category_description` | READ |
| `oc_product_to_category` | READ / INSERT / DELETE |

## License

MIT — free to use and adapt for your own OpenCart projects.
