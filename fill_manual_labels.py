"""Heuristic auto-labeller for validation_sample.csv manual_category column.
Applies plain-English keyword rules a human reviewer would use, then re-reads
the (now corrected) nlp_results category to test the corrections.
"""
import csv
import sqlite3
import re

SAMPLE_CSV = "validation_sample.csv"
DB = "uifpi.db"

CATEGORIES = [
    "GRILLED_PROTEIN", "NOODLE_DISH", "RICE_DISH", "SOUP_STEW",
    "DIM_SUM_DUMPLING", "BREAD_PASTRY", "BEVERAGE", "DESSERT",
    "FAST_FOOD", "SEAFOOD_DISH", "SALAD_VEGETABLE", "SNACK_SIDE",
    "SET_MEAL", "OTHER",
]


def manual_label(item: str) -> str:
    """Best-effort manual label based on the item name alone."""
    s = item.lower()
    # noise / non-food
    if any(k in s for k in ["price tier", "new!", "tripadvisor:",
                              "happy baking", "fast vegetarian"]):
        return "OTHER"
    # beverages
    if any(k in s for k in [
        "shake", "lemonade", "iced tea", "iced-t", "soda", "sprite", "fanta",
        "7 up", "7-up", "pepsi", "coca cola", "limoncello", "barley", "milk",
        "espresso", "cappuccino", "americano", "mocha", "latte", "smoothie",
        "juice", "tea", "coffee", "beer", "wine", "sake", "cocktail",
        "water"]):
        if "tea" in s and ("cake" in s or "leaf" in s):
            pass
        else:
            return "BEVERAGE"
    # noodles
    if any(k in s for k in [
        "noodle", "la mian", "lamian", "ramen", "udon", "soba", "chasoba",
        "kuey teow", "kway teow", "kuay teow", "mee ", "mee sup", "pho",
        "hor fun", "bee hoon", "mihun", "hokkien mee"]):
        return "NOODLE_DISH"
    # dim sum / dumplings
    if any(k in s for k in [
        "dumpling", "shao-mai", "shao mai", "shumai", "siu mai", "har gow",
        "har gao", "wonton", "wanton", "wantan", "xiao long bao", "xlb",
        "potsticker", "gyoza", "baozi", "char siu bao"]):
        return "DIM_SUM_DUMPLING"
    # seafood / sushi / sashimi
    if any(k in s for k in [
        "sushi", "sashimi", "hamachi", "tako", "hotate", "kanikama",
        "negitoro", "maguro", "uni ", "salmon", "scallop", "shrimp",
        "prawn", "ebi", "fish & chips", "fish and chips", "fish ball",
        "seafood platter", "halibut", "tuna"]):
        return "SEAFOOD_DISH"
    # bread / pastry
    if any(k in s for k in [
        "dosa", "thosai", "naan", "roti", "shio pan", "croissant", "muffin",
        "doughnut", "donut", "bagel", "scone", "toast", "baguette",
        "bun bakar", "bao "]):
        return "BREAD_PASTRY"
    # dessert
    if any(k in s for k in [
        "cake", "ice cream", "gelato", "pudding", "mochi", "cheesecake",
        "tiramisu", "mango sticky", "creme brulee", "layered cake"]):
        return "DESSERT"
    # rice
    if any(k in s for k in [
        "fried rice", "rice", "donburi", "don ", "khao pad", "khao kha",
        "khao man", "biryani", "nasi lemak", "nasi goreng"]):
        if "noodle" not in s:
            return "RICE_DISH"
    # soup
    if any(k in s for k in [
        "soup", "tom yum", "tom yam", "tom kha", "miso soup", "broth",
        "stew", "braised"]):
        return "SOUP_STEW"
    # grilled
    if any(k in s for k in [
        "yakiniku", "yakitori", "satay", "kebab", "bbq", "grilled",
        "roast ", "roasted ", "char siu", "tandoori", "teriyaki",
        "karaage", "katsu"]):
        return "GRILLED_PROTEIN"
    # fast food (burgers/fries/pizza)
    if any(k in s for k in [
        "burger", "cheeseburger", "fries", "hot dog", "pizza", "margherita",
        "sandwich"]):
        return "FAST_FOOD"
    # salad / vegetable
    if any(k in s for k in [
        "salad", "vegetable", "veggie", "kailan", "long beans", "kale",
        "spinach"]):
        return "SALAD_VEGETABLE"
    # snack
    if any(k in s for k in [
        "spring roll", "egg roll", "fried bait", "intestines",
        "chuka ", "edamame", "potato wedges"]):
        return "SNACK_SIDE"
    # set meal
    if "set " in s or "platter" in s or "gozen" in s:
        return "SET_MEAL"
    return "OTHER"


def main():
    rows = []
    with open(SAMPLE_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    # Pull updated category from DB to reflect Issue-4 SQL fixes
    conn = sqlite3.connect(DB)
    db_cat = {}
    for item, cat in conn.execute("SELECT item_name, category FROM nlp_results"):
        db_cat[item] = cat
    conn.close()

    for r in rows:
        r["manual_category"] = manual_label(r["item_name"])
        # refresh assigned_category from DB (post-fix view)
        if r["item_name"] in db_cat:
            r["assigned_category"] = db_cat[r["item_name"]]

    with open(SAMPLE_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Filled manual_category for {len(rows)} rows; refreshed assigned_category from DB.")


if __name__ == "__main__":
    main()
