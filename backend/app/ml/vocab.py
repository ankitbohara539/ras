"""Phrase banks for the synthetic report generator.

Written by hand rather than sampled from a corpus, because no public corpus of
Nepali civic complaints exists. The aim is variation that a classifier has to
work for: the same issue described formally, casually, in Nepali, in English,
and in the Roman-Nepali mix people actually type on phones.
"""

PLACES_EN = [
    "near the bus stop",
    "in front of the school",
    "beside the temple",
    "at the main chowk",
    "on the way to the market",
    "next to the health post",
    "behind the community building",
    "near the petrol pump",
    "outside the ward office",
    "close to the bridge",
    "opposite the police post",
    "near the vegetable market",
    "by the river side",
    "at the corner of the gali",
    "near the college gate",
    "in front of the hospital",
]

PLACES_NE = [
    "बस स्टप नजिक",
    "स्कूलको अगाडि",
    "मन्दिर छेउमा",
    "मुख्य चोकमा",
    "बजार जाने बाटोमा",
    "स्वास्थ्य चौकी नजिकै",
    "सामुदायिक भवन पछाडि",
    "पेट्रोल पम्प नजिक",
    "वडा कार्यालय बाहिर",
    "पुल नजिकै",
    "प्रहरी चौकी अगाडि",
    "तरकारी बजार नजिक",
    "खोला किनारमा",
    "गल्लीको कुनामा",
    "कलेज गेट नजिक",
    "अस्पतालको अगाडि",
]

DURATION_EN = [
    "for the last three days",
    "since last week",
    "for over a month",
    "since yesterday",
    "for many months now",
    "since the last rain",
    "for two weeks",
    "since the festival",
]

DURATION_NE = [
    "तीन दिनदेखि",
    "गत हप्तादेखि",
    "एक महिनाभन्दा बढी",
    "हिजोदेखि",
    "धेरै महिनादेखि",
    "पानी परेदेखि",
    "दुई हप्तादेखि",
    "चाडपर्वदेखि",
]

COMPLAINT_OPENERS_EN = [
    "Please look into this.",
    "Kindly take action soon.",
    "This needs urgent attention.",
    "We have complained before but nothing happened.",
    "Requesting the ward office to fix this.",
    "",
    "",
]

COMPLAINT_OPENERS_NE = [
    "कृपया हेरिदिनुहोस्।",
    "छिट्टै कारबाही गरिदिनुहोस्।",
    "यसमा तत्काल ध्यान दिनुपर्‍यो।",
    "पहिले पनि गुनासो गरेका थियौं तर केही भएन।",
    "वडा कार्यालयलाई अनुरोध छ।",
    "",
    "",
]

# Realistic phone-typed Roman Nepali. Deliberately inconsistent spelling.
ROMAN_NEPALI_HINTS = {
    "pothole": ["khaldo", "sadak bigriyo", "bato ma khaldo cha"],
    "garbage": ["phohor", "phohar thupriyo", "kachra jammaa bhayo"],
    "street_light": ["batti balena", "sadak batti off cha"],
    "water_supply": ["pani aayena", "dhara sukyo"],
    "drainage": ["dhal bhariyo", "dhal jam bhayo"],
    "waterlogging": ["pani jamyo", "bato ma pani bhariyo"],
    "electricity": ["bijuli gayo", "tar jhundiyeko cha"],
    "stray_animals": ["kukur haru chan", "gai bato ma basyo"],
    "public_sanitation": ["sarsafai bhaena", "toilet fohor cha"],
    "illegal_construction": ["avaidh nirman", "bato mich era ghar banayo"],
    "pollution": ["dhulo dherai cha", "hallaa dherai bhayo"],
    "other": ["samasya cha", "problem cha yaha"],
}
