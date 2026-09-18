"""Issue categories and their deduplication geometry.

match_radius_m is the distance within which two reports can plausibly describe
the same incident. It is category-specific on purpose: two potholes 80m apart
are two potholes, but waterlogging reported 80m apart is one flood.

dedupe_window_days is how long a ticket stays eligible to absorb duplicates.
Garbage recurs weekly, so its window is short; illegal construction persists
for months, so its window is long.
"""

CATEGORY_SEEDS: list[dict] = [
    {
        "key": "pothole",
        "name_en": "Pothole / Road Damage",
        "name_ne": "खाल्डो / सडक क्षति",
        "icon": "road",
        "base_severity": 0.60,
        "match_radius_m": 60,
        "dedupe_window_days": 45,
        "sort_order": 10,
    },
    {
        "key": "garbage",
        "name_en": "Garbage & Waste",
        "name_ne": "फोहोरमैला",
        "icon": "trash",
        "base_severity": 0.50,
        "match_radius_m": 80,
        "dedupe_window_days": 21,
        "sort_order": 20,
    },
    {
        "key": "street_light",
        "name_en": "Street Light",
        "name_ne": "सडक बत्ती",
        "icon": "lightbulb",
        "base_severity": 0.40,
        "match_radius_m": 40,
        "dedupe_window_days": 60,
        "sort_order": 30,
    },
    {
        "key": "water_supply",
        "name_en": "Water Supply",
        "name_ne": "खानेपानी आपूर्ति",
        "icon": "droplet",
        "base_severity": 0.70,
        "match_radius_m": 150,
        "dedupe_window_days": 30,
        "sort_order": 40,
    },
    {
        "key": "drainage",
        "name_en": "Drainage & Sewage",
        "name_ne": "ढल तथा निकास",
        "icon": "pipe",
        "base_severity": 0.75,
        "match_radius_m": 120,
        "dedupe_window_days": 30,
        "sort_order": 50,
    },
    {
        "key": "waterlogging",
        "name_en": "Waterlogging / Flooding",
        "name_ne": "जलजमाव / बाढी",
        "icon": "waves",
        "base_severity": 0.85,
        "match_radius_m": 250,
        "dedupe_window_days": 14,
        "sort_order": 60,
    },
    {
        "key": "electricity",
        "name_en": "Electricity / Power Line",
        "name_ne": "विद्युत लाइन",
        "icon": "zap",
        "base_severity": 0.80,
        "match_radius_m": 100,
        "dedupe_window_days": 30,
        "sort_order": 70,
    },
    {
        "key": "stray_animals",
        "name_en": "Stray Animals",
        "name_ne": "छाडा पशु",
        "icon": "paw",
        "base_severity": 0.45,
        "match_radius_m": 200,
        "dedupe_window_days": 14,
        "sort_order": 80,
    },
    {
        "key": "public_sanitation",
        "name_en": "Public Sanitation",
        "name_ne": "सार्वजनिक सरसफाइ",
        "icon": "spray",
        "base_severity": 0.50,
        "match_radius_m": 60,
        "dedupe_window_days": 30,
        "sort_order": 90,
    },
    {
        "key": "illegal_construction",
        "name_en": "Illegal Construction",
        "name_ne": "अवैध निर्माण",
        "icon": "hard-hat",
        "base_severity": 0.60,
        "match_radius_m": 80,
        "dedupe_window_days": 120,
        "sort_order": 100,
    },
    {
        "key": "pollution",
        "name_en": "Air / Noise Pollution",
        "name_ne": "वायु / ध्वनि प्रदूषण",
        "icon": "wind",
        "base_severity": 0.55,
        "match_radius_m": 300,
        "dedupe_window_days": 21,
        "sort_order": 110,
    },
    {
        "key": "other",
        "name_en": "Other",
        "name_ne": "अन्य",
        "icon": "alert",
        "base_severity": 0.40,
        "match_radius_m": 100,
        "dedupe_window_days": 30,
        "sort_order": 999,
    },
]

CATEGORY_KEYS = [c["key"] for c in CATEGORY_SEEDS]
