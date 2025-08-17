from typing import List, Dict
from rapidfuzz import process, fuzz

# Minimal SKU catalog with Malay/English aliases
CATALOG = [
    {
        "sku": "BED-3FUNC-MAN",
        "name": "Katil 3 Function Manual",
        "aliases": ["Katil 3 Function Manual", "bed 3 function manual", "katil manual 3 fungsi", "3 fungsi manual"],
        "category": "BED",
    },
    {
        "sku": "MATT-CANVAS",
        "name": "Tilam Canvas",
        "aliases": ["tilam canvas", "canvas mattress", "tilam kalis air"],
        "category": "MATTRESS",
    },
    {
        "sku": "BED-2FUNC-MAN",
        "name": "Katil 2 Function Manual",
        "aliases": ["2 fungsi manual", "bed 2 function manual", "katil 2 fungsi"],
        "category": "BED",
    },
    {
        "sku": "WCHAIR-TRAVEL-ALU",
        "name": "Travel Wheelchair Aluminium",
        "aliases": ["travel wheelchair aluminium", "kerusi roda travel", "wheelchair aluminium", "travel chair aluminium"],
        "category": "WHEELCHAIR",
    },
    {
        "sku": "COMMODE-BASIC",
        "name": "Commode Biasa",
        "aliases": ["commode biasa", "basic commode"],
        "category": "COMMODE",
    },
    {
        "sku": "COMMODE-PADDED-WHITE",
        "name": "Commode White Padded",
        "aliases": ["commode white padded", "commode padded", "kerusi commode kusyen putih"],
        "category": "COMMODE",
    },
]

def map_product(text: str, score_cutoff: int = 75) -> Dict:
    choices = {c["name"]: c for c in CATALOG}
    # Build alias mapping
    alias_to_name = {}
    for c in CATALOG:
        for a in c["aliases"]:
            alias_to_name[a] = c["name"]

    # Fuzzy match against aliases + names
    key, score, _ = process.extractOne(
        text,
        list(alias_to_name.keys()) + list(choices.keys()),
        scorer=fuzz.WRatio
    ) if text else (None, 0, None)

    if key and score >= score_cutoff:
        name = alias_to_name.get(key, key)
        prod = choices[name]
        return {"sku": prod["sku"], "name": prod["name"], "category": prod["category"], "score": score}

    return {"sku": None, "name": text, "category": None, "score": score}
