"""Kathmandu Valley municipalities and their wards.

Municipality names, districts, types and ward counts are real. Ward centroids
are generated: real ward boundary data for Nepal is not freely available as a
clean dataset, so wards are laid out on a deterministic grid around each
municipality centre. That is accurate enough to demonstrate ward isolation and
distance-based matching, and it is stable across reseeds.
"""

import math

MUNICIPALITY_SEEDS: list[dict] = [
    {
        "code": "KMC",
        "name_en": "Kathmandu Metropolitan City",
        "name_ne": "काठमाडौं महानगरपालिका",
        "district": "Kathmandu",
        "province": "Bagmati",
        "type": "metropolitan",
        "center_lat": 27.7172,
        "center_lon": 85.3240,
        "ward_count": 32,
        "spread_km": 4.5,
    },
    {
        "code": "LMC",
        "name_en": "Lalitpur Metropolitan City",
        "name_ne": "ललितपुर महानगरपालिका",
        "district": "Lalitpur",
        "province": "Bagmati",
        "type": "metropolitan",
        "center_lat": 27.6588,
        "center_lon": 85.3247,
        "ward_count": 29,
        "spread_km": 4.0,
    },
    {
        "code": "BKT",
        "name_en": "Bhaktapur Municipality",
        "name_ne": "भक्तपुर नगरपालिका",
        "district": "Bhaktapur",
        "province": "Bagmati",
        "type": "municipality",
        "center_lat": 27.6710,
        "center_lon": 85.4298,
        "ward_count": 10,
        "spread_km": 2.5,
    },
    {
        "code": "BDN",
        "name_en": "Budhanilkantha Municipality",
        "name_ne": "बूढानीलकण्ठ नगरपालिका",
        "district": "Kathmandu",
        "province": "Bagmati",
        "type": "municipality",
        "center_lat": 27.7789,
        "center_lon": 85.3620,
        "ward_count": 13,
        "spread_km": 3.0,
    },
    {
        "code": "KTP",
        "name_en": "Kirtipur Municipality",
        "name_ne": "कीर्तिपुर नगरपालिका",
        "district": "Kathmandu",
        "province": "Bagmati",
        "type": "municipality",
        "center_lat": 27.6786,
        "center_lon": 85.2775,
        "ward_count": 10,
        "spread_km": 2.5,
    },
]

# A handful of real place names so demo tickets read plausibly. Wards beyond
# this list fall back to "Ward N".
WARD_NAMES: dict[str, dict[int, tuple[str, str]]] = {
    "KMC": {
        1: ("Naxal", "नक्साल"),
        3: ("Maharajgunj", "महाराजगन्ज"),
        4: ("Baluwatar", "बालुवाटार"),
        5: ("Chabahil", "चाबहिल"),
        6: ("Gaushala", "गौशाला"),
        7: ("Chuchchepati", "चुच्चेपाटी"),
        10: ("Baneshwor", "बानेश्वर"),
        11: ("Anamnagar", "अनामनगर"),
        14: ("Kalimati", "कालीमाटी"),
        15: ("Swayambhu", "स्वयम्भू"),
        16: ("Balaju", "बालाजु"),
        17: ("Chhetrapati", "क्षेत्रपाटी"),
        22: ("Ason", "असन"),
        26: ("Teku", "टेकु"),
        29: ("Kalanki", "कलंकी"),
        31: ("Koteshwor", "कोटेश्वर"),
        32: ("Mulpani", "मूलपानी"),
    },
    "LMC": {
        2: ("Kupondole", "कुपन्डोल"),
        3: ("Jhamsikhel", "झम्सिखेल"),
        4: ("Sanepa", "सानेपा"),
        10: ("Patan Durbar", "पाटन दरबार"),
        14: ("Satdobato", "सातदोबाटो"),
        20: ("Imadol", "इमाडोल"),
        25: ("Bhaisepati", "भैंसेपाटी"),
    },
    "BKT": {
        1: ("Bhaktapur Durbar", "भक्तपुर दरबार"),
        4: ("Dattatreya", "दत्तात्रय"),
        7: ("Suryabinayak", "सूर्यविनायक"),
        10: ("Kamalbinayak", "कमलविनायक"),
    },
    "BDN": {
        1: ("Budhanilkantha Temple", "बूढानीलकण्ठ मन्दिर"),
        4: ("Kapan", "कपन"),
        8: ("Chapali", "चापली"),
        11: ("Tokha Road", "तोखा सडक"),
    },
    "KTP": {
        1: ("Kirtipur Bazar", "कीर्तिपुर बजार"),
        3: ("Naya Bazar", "नयाँ बजार"),
        5: ("Panga", "पाँगा"),
        8: ("Chobhar", "चोभार"),
    },
}

KM_PER_DEG_LAT = 110.574


def _km_per_deg_lon(lat: float) -> float:
    return 111.320 * math.cos(math.radians(lat))


def ward_centroid(
    center_lat: float,
    center_lon: float,
    ward_number: int,
    ward_count: int,
    spread_km: float,
) -> tuple[float, float]:
    """Place a ward on a deterministic spiral around the municipality centre.

    A spiral rather than a grid so wards are not all equidistant, which would
    make distance-based matching look artificially tidy.
    """
    if ward_count <= 1:
        return center_lat, center_lon

    index = ward_number - 1
    # Golden-angle spiral: even coverage, no two wards stacked.
    angle = index * 2.399963
    radius_km = spread_km * math.sqrt(index / (ward_count - 1))

    d_lat = (radius_km * math.cos(angle)) / KM_PER_DEG_LAT
    d_lon = (radius_km * math.sin(angle)) / _km_per_deg_lon(center_lat)

    return round(center_lat + d_lat, 6), round(center_lon + d_lon, 6)


def build_wards(municipality: dict) -> list[dict]:
    """Expand a municipality seed into its ward rows."""
    names = WARD_NAMES.get(municipality["code"], {})
    wards = []

    for number in range(1, municipality["ward_count"] + 1):
        lat, lon = ward_centroid(
            municipality["center_lat"],
            municipality["center_lon"],
            number,
            municipality["ward_count"],
            municipality["spread_km"],
        )
        name_en, name_ne = names.get(number, (f"Ward {number}", f"वडा {number}"))

        wards.append(
            {
                "number": number,
                "name_en": name_en,
                "name_ne": name_ne,
                "centroid_lat": lat,
                "centroid_lon": lon,
            }
        )

    return wards
