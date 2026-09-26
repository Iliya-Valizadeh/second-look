"""Invented merchant names for the synthetic statement generator.

None of these are real companies. Every list is fixed (not drawn from the per-statement
`random.Random(seed)`), so the same merchant always has the same city, prefix and
suffix across every statement. Store numbers and which merchant is a statement's
"favourite" are drawn per statement instead (see `generator.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class MerchantDef:
    name: str
    city_prov: str
    category: str
    prefix: str = ""
    suffix: str = ""
    has_store_number: bool = False

    def describe(self, store_number: str | None = None) -> str:
        text = f"{self.prefix}{self.name}" if self.prefix else self.name
        if store_number is not None:
            text = f"{text} #{store_number}"
        if self.suffix:
            text = f"{text} {self.suffix}"
        return f"{text} {self.city_prov}"


# Groceries: 4 merchants, all carry store numbers.
GROCERIES = [
    MerchantDef(
        "MAPLEBROOK GROCERS", "TORONTO ON", "Groceries", suffix="INC", has_store_number=True
    ),
    MerchantDef("HARVEST LANE MARKET", "MISSISSAUGA ON", "Groceries", has_store_number=True),
    MerchantDef("NORTHFIELD FOODS", "OTTAWA ON", "Groceries", has_store_number=True),
    MerchantDef("RIVERSTONE GROCERY", "HAMILTON ON", "Groceries", has_store_number=True),
]

# Restaurants: 8 merchants, half start with "SQ *".
RESTAURANTS = [
    MerchantDef("BLUE HERON DINER", "TORONTO ON", "Restaurants", prefix="SQ *"),
    MerchantDef("PEPPER AND VINE", "VANCOUVER BC", "Restaurants", prefix="SQ *"),
    MerchantDef("GOLDEN WOK KITCHEN", "CALGARY AB", "Restaurants", prefix="SQ *"),
    MerchantDef("CEDAR ST NOODLE BAR", "MONTREAL QC", "Restaurants", prefix="SQ *"),
    MerchantDef("HARBOUR GRILL", "HALIFAX NS", "Restaurants", suffix="LTD"),
    MerchantDef("OAKWOOD PIZZERIA", "EDMONTON AB", "Restaurants"),
    MerchantDef("SUNSET TACO HOUSE", "WINNIPEG MB", "Restaurants"),
    MerchantDef("LANTERN STREET EATERY", "TORONTO ON", "Restaurants"),
]

# Coffee: 3 merchants, roughly half start with "SQ *". Amounts come from a fixed menu.
COFFEE = [
    MerchantDef("BREWPOINT COFFEE", "TORONTO ON", "Coffee", prefix="SQ *"),
    MerchantDef("MILL STREET ROASTERS", "OTTAWA ON", "Coffee", prefix="SQ *"),
    MerchantDef("DAYBREAK CAFE", "VANCOUVER BC", "Coffee"),
]
COFFEE_MENU = ("2.45", "3.25", "4.75", "5.95")

# Transit: 1 merchant. Amount is always 3.35.
TRANSIT = MerchantDef("CITY TRANSIT FARE", "TORONTO ON", "Transit")

# Fuel: 3 merchants, all carry store numbers.
FUEL = [
    MerchantDef("SUMMIT FUEL AND GO", "MISSISSAUGA ON", "Fuel", has_store_number=True),
    MerchantDef("PARKWAY GAS STATION", "CALGARY AB", "Fuel", suffix="INC", has_store_number=True),
    MerchantDef("EASTGATE PETROLEUM", "WINNIPEG MB", "Fuel", has_store_number=True),
]

# Shopping: 6 merchants, no store numbers.
SHOPPING = [
    MerchantDef("CLEARVIEW HOME GOODS", "TORONTO ON", "Shopping", suffix="LTD"),
    MerchantDef("NORTHSTAR APPAREL", "VANCOUVER BC", "Shopping"),
    MerchantDef("PINECREST HARDWARE", "OTTAWA ON", "Shopping"),
    MerchantDef("SILVERLEAF BOOKS", "HAMILTON ON", "Shopping"),
    MerchantDef("BRIGHTSIDE PET SUPPLY", "CALGARY AB", "Shopping"),
    MerchantDef("FIELDSTONE OUTFITTERS", "MONTREAL QC", "Shopping", suffix="INC"),
]

# Pharmacy: 2 merchants, both carry store numbers.
PHARMACY = [
    MerchantDef("WELLPOINT PHARMACY", "TORONTO ON", "Pharmacy", has_store_number=True),
    MerchantDef("CARELINE DRUG MART", "EDMONTON AB", "Pharmacy", has_store_number=True),
]

# Entertainment: 3 merchants, no store numbers.
ENTERTAINMENT = [
    MerchantDef("STARLIGHT CINEMA", "TORONTO ON", "Entertainment"),
    MerchantDef("RIVERBEND BOWLING", "WINNIPEG MB", "Entertainment", suffix="LTD"),
    MerchantDef("EVERGREEN ARCADE", "OTTAWA ON", "Entertainment"),
]

BACKGROUND_CATEGORIES: dict[str, dict[str, Any]] = {
    "groceries": {"merchants": GROCERIES, "visits": (4, 8), "median": "60", "sigma": 0.5},
    "restaurants": {"merchants": RESTAURANTS, "visits": (2, 6), "median": "32", "sigma": 0.5},
    "coffee": {"merchants": COFFEE, "visits": (6, 14), "median": None, "sigma": None},
    "fuel": {"merchants": FUEL, "visits": (1, 3), "median": "55", "sigma": 0.25},
    "shopping": {"merchants": SHOPPING, "visits": (1, 4), "median": "40", "sigma": 0.7},
    "pharmacy": {"merchants": PHARMACY, "visits": (0, 2), "median": "22", "sigma": 0.6},
    "entertainment": {"merchants": ENTERTAINMENT, "visits": (0, 2), "median": "28", "sigma": 0.4},
}

# Categories duplicates and unusual "spike" charges are allowed to copy.
DUPLICATE_SPIKE_CATEGORIES = (
    "groceries",
    "restaurants",
    "fuel",
    "shopping",
    "pharmacy",
    "entertainment",
)

# Subscription merchants: at least 20 invented names, separate from the above.
SUBSCRIPTION_MERCHANTS = [
    "STREAMFLIX",
    "TUNEWAVE MUSIC",
    "CLOUDBOX STORAGE",
    "FITPULSE GYM",
    "DAILY NEWS DIGEST",
    "PIXELFORGE STUDIO",
    "MEALBOX DELIVERY",
    "ZENFLOW YOGA",
    "PLAYVAULT GAMES",
    "SKYLINE VPN",
    "WORDNEST LEARNING",
    "GLOWBOX BEAUTY",
    "PODCAST PLUS",
    "HOMEGUARD SECURITY",
    "FRESHCROP BOX",
    "NOTESPACE PRO",
    "TRAILMIX PODCASTS",
    "BRIGHTDESK SOFTWARE",
    "PAWSITIVE PET BOX",
    "INKWELL BOOK CLUB",
    "CIRCUIT FITNESS APP",
    "LOOPCAST RADIO",
    "VAULTKEY PASSWORDS",
    "SUNROOM MAGAZINE",
]

# One-time merchants for "large charge at a new merchant": at least 10 invented names.
NEW_MERCHANT_NAMES = [
    "APEX ELECTRONICS",
    "HORIZON FURNITURE",
    "SKYLINE TRAVEL AGENCY",
    "RAPID AUTO REPAIR",
    "CRESTVIEW APPLIANCES",
    "TRUEPATH DENTAL LAB",
    "IRONWOOD FLOORING",
    "BAYVIEW OPTICAL",
    "NORTHLIGHT CAMERA SHOP",
    "STONEBRIDGE MATTRESS CO",
    "COPPERLEAF JEWELLERS",
    "WESTGATE TIRE CENTRE",
]

RENT_DESCRIPTION = "MAPLE RIDGE PROPERTY MGMT"
VARYING_BILL_DESCRIPTION = "CIVIC HYDRO AND POWER"
