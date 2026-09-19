"""Kathmandu Valley municipalities and their wards.

Municipality names, districts, types and ward counts are real, and so are the
wards: centres from OpenStreetMap's ward boundaries, names from the
municipality where it publishes them (see REAL_WARDS for sources).
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
# Every ward's real centre and name: {code: {number: (lat, lon, name_en, name_ne)}}.
#
# Centres are the centroids of OpenStreetMap's ward boundary relations
# (boundary=administrative, "Kathmandu-09" etc.), fetched via Overpass. They
# are what ward routing falls back on when the geocoder is unreachable.
#
# Names:
#   KMC -- the ward office locations published by Kathmandu Metropolitan City
#          (kathmandu.gov.np/en/wards), spellings normalised, Nepali added.
#   LMC, BKT, BDN, KTP -- their websites do not publish ward names in a
#          readable form, so these are the OpenStreetMap locality at (or, where
#          the centre falls on a road or field, nearest to) each ward's centre.
#          Accurate as "the area", not an official designation; replace with
#          official names when available. name_ne is None where OSM has no
#          Nepali name.
REAL_WARDS: dict[str, dict[int, tuple[float, float, str, str | None]]] = {
    "KMC": {
        1: (27.71248, 85.32377, "Naxal", "नक्साल"),
        2: (27.72145, 85.32433, "Lazimpat", "लाजिम्पाट"),
        3: (27.7376, 85.33228, "Maharajgunj", "महाराजगञ्ज"),
        4: (27.72893, 85.33519, "Baluwatar", "बालुवाटार"),
        5: (27.7164, 85.33518, "Hadigaun", "हाडीगाउँ"),
        6: (27.72328, 85.36064, "Boudha", "बौद्ध"),
        7: (27.7173, 85.34729, "Mitrapark", "मित्रपार्क"),
        8: (27.70991, 85.35403, "Jayabageshwari", "जयबागेश्वरी"),
        9: (27.69612, 85.35106, "Gaushala", "गौशाला"),
        10: (27.69163, 85.33237, "Baneshwor", "बानेश्वर"),
        11: (27.69327, 85.31856, "Bhagdurbar", "भागदरबार"),
        12: (27.69654, 85.30409, "Teku", "टेकु"),
        13: (27.70175, 85.29218, "Kalimati", "कालीमाटी"),
        14: (27.68927, 85.28975, "Kalanki", "कलङ्की"),
        15: (27.71448, 85.29265, "Dallu", "डल्लु"),
        16: (27.72639, 85.30112, "Balaju", "बालाजु"),
        17: (27.71241, 85.30663, "Chhetrapati", "क्षेत्रपाटी"),
        18: (27.70956, 85.30536, "Naradevi", "नरदेवी"),
        19: (27.70642, 85.30448, "Damaitol", "दमैंटोल"),
        20: (27.70316, 85.30399, "Bhimsensthan", "भीमसेनस्थान"),
        21: (27.69817, 85.30697, "Jyawahal", "ज्याबहाल"),
        22: (27.70159, 85.311, "Tewahal", "तेबहाल"),
        23: (27.70162, 85.30707, "Ombahal", "ओमबहाल"),
        24: (27.70567, 85.30806, "Makhan", "मखन"),
        25: (27.70755, 85.31008, "Masangalli", "मसँगल्ली"),
        26: (27.72182, 85.31485, "Lainchaur", "लैनचौर"),
        27: (27.70974, 85.31379, "Mahaboudha", "महाबौद्ध"),
        28: (27.70407, 85.31833, "Old Buspark", "पुरानो बसपार्क"),
        29: (27.69906, 85.32848, "Anamnagar", "अनामनगर"),
        30: (27.70773, 85.33017, "Gyaneshwor", "ज्ञानेश्वर"),
        31: (27.69005, 85.34115, "Shantinagar", "शान्तिनगर"),
        32: (27.68939, 85.35199, "Koteshwor", "कोटेश्वर"),
    },
    "LMC": {
        1: (27.68714, 85.31293, "Bakhundol", "बखुण्डोल"),
        2: (27.68608, 85.30646, "Sanepa", "सानेपा"),
        3: (27.67996, 85.30711, "Jhamsikhel", "झम्सीखेल"),
        4: (27.66918, 85.30408, "Dhobighat", "धोबीघाट"),
        5: (27.66705, 85.31639, "Kumaripati", "कुमारीपाटी"),
        6: (27.66668, 85.32655, "Ashok Rotary Park", None),
        7: (27.66832, 85.33275, "Bhangini Nani", "भंगिनी नानी"),
        8: (27.67002, 85.33404, "Guita", "गुइटा"),
        9: (27.67558, 85.33486, "Bhola Dhoka", "भोला ढोका"),
        10: (27.68389, 85.32101, "Kupondole", "कुपन्डोल"),
        11: (27.68081, 85.32578, "Chakupat", "चाकुपाट"),
        12: (27.67038, 85.32548, "Thaina", "थईना"),
        13: (27.66339, 85.31069, "Naya Nagar", "नयाँ नगर"),
        14: (27.65428, 85.31648, "Nakhudol", "नख्खुडोल"),
        15: (27.65551, 85.32767, "Khumaltar", "खुमल्टार"),
        16: (27.67476, 85.32338, "Dhaugal Bazar", "धौगल बजार"),
        17: (27.66373, 85.33167, "Sa: Kwo Twa", "सः क्वों ट्व"),
        18: (27.65204, 85.29929, "Tallogau", "तल्लो गाउँ"),
        19: (27.67045, 85.32211, "Itapukhu", "इतापुखु"),
        20: (27.67487, 85.31839, "Gabahal", "गाबाहल"),
        21: (27.6432, 85.29372, "Sano Khokana", "सानो खोकना"),
        22: (27.61993, 85.30118, "Bungamati", "बुङ्गमती"),
        23: (27.643, 85.32975, "Hattiban", "हातिबन"),
        24: (27.62848, 85.33337, "Dhapakhel", "धापाखेल"),
        25: (27.64717, 85.30814, "Baniyagau", None),
        26: (27.63865, 85.31674, "Chibahal", None),
        27: (27.63147, 85.3169, "Sunakothi", "सुनाकोठी"),
        28: (27.64038, 85.3429, "Harisiddhi", "हरिसिद्धी"),
        29: (27.63623, 85.34423, "Safal Tol", "सफल टोल"),
    },
    "BKT": {
        1: (27.67253, 85.4123, "Sallaghari Chaur", "सल्लाघारी चौर"),
        2: (27.67541, 85.4195, "Itachhen", "इतछें"),
        3: (27.66927, 85.42286, "Ghalate", "घलाते"),
        4: (27.66809, 85.42695, "Kalighat", None),
        5: (27.66976, 85.43067, "Aadarsha", None),
        6: (27.68104, 85.43392, "Jhaukhel", "झौखेल"),
        7: (27.6702, 85.43466, "Jagati", "जगति"),
        8: (27.66868, 85.44163, "Libali", "लिवाली"),
        9: (27.67502, 85.44146, "Kamal Binayak", "कमल विनायक"),
        10: (27.68264, 85.44054, "Pipal Bot", None),
    },
    "BDN": {
        1: (27.78604, 85.37572, "Nagigumba", "नागी गुम्बा"),
        2: (27.77175, 85.37223, "Bista Tole", "बिस्ट टोल"),
        3: (27.78899, 85.37055, "Muhan Pokhari", "मुहान पोखरी"),
        4: (27.7704, 85.34962, "Khadka Bhadrakali", "खड्का भद्रकाली"),
        5: (27.79278, 85.35533, "Dandagaun", "डाँडागाउँ"),
        6: (27.76024, 85.3428, "Tokha Saraswati", "टोखा सरस्वती"),
        7: (27.75464, 85.34478, "Dharampur", "धरमपुर"),
        8: (27.75143, 85.35518, "Golphutar", "गोल्फुटार"),
        9: (27.72951, 85.34815, "Ananda Nagar", "आनन्द नगर"),
        10: (27.73491, 85.35366, "Aakashedhara", None),
        11: (27.74261, 85.3653, "Tinchuli", "तिन्चुली"),
        12: (27.73257, 85.36061, "Shanti Nagar", "शान्ति नगर"),
        13: (27.75879, 85.37051, "Chunikhel", "चुनिखेल"),
    },
    "KTP": {
        1: (27.68462, 85.27993, "Sa-lin-chhn", None),
        2: (27.68576, 85.27528, "Maitri Nagar", "मैत्री नगर"),
        3: (27.67929, 85.27166, "Si-dhwa-kha", None),
        4: (27.66329, 85.259, "Gamcha", "गाम्चा"),
        5: (27.66435, 85.27292, "Langocha", "लनगोचा"),
        6: (27.65847, 85.28228, "Chobhar", "चोभार"),
        7: (27.67013, 85.28339, "Itagol", "यरोचा"),
        8: (27.67142, 85.27846, "Pa-chhin-Dwopa", "पाछी द्वपा"),
        9: (27.67059, 85.27647, "Lachhi", "लाछी"),
        10: (27.68013, 85.28798, "Nayabazar", "नयाँ बजार"),
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
    """Expand a municipality seed into its ward rows.

    Real centres and names from REAL_WARDS; a municipality missing from it
    falls back to the generated spiral and "Ward N".
    """
    real = REAL_WARDS.get(municipality["code"], {})
    wards = []

    for number in range(1, municipality["ward_count"] + 1):
        if number in real:
            lat, lon, name_en, name_ne = real[number]
        else:
            lat, lon = ward_centroid(
                municipality["center_lat"],
                municipality["center_lon"],
                number,
                municipality["ward_count"],
                municipality["spread_km"],
            )
            name_en, name_ne = f"Ward {number}", None

        wards.append(
            {
                "number": number,
                "name_en": name_en,
                "name_ne": name_ne or f"वडा {number}",
                "centroid_lat": lat,
                "centroid_lon": lon,
            }
        )

    return wards
