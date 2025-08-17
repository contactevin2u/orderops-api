import re, os
from typing import Dict, Any, Optional, List
from dateutil import parser as dateparser

try:
    import spacy
    from spacy.matcher import PhraseMatcher
except Exception:  # fail-safe if pip not ready
    spacy = None
    PhraseMatcher = None

# Fallbacks if spaCy model is not available during runtime
def _load_nlp():
    if spacy is None:
        return None, None
    try:
        import en_core_web_sm
        nlp = en_core_web_sm.load()
    except Exception:
        try:
            nlp = spacy.load(os.getenv("SPACY_MODEL","en_core_web_sm"))
        except Exception:
            nlp = spacy.blank("en")
    matcher = PhraseMatcher(nlp.vocab, attr="LOWER") if PhraseMatcher else None
    return nlp, matcher

nlp, phrase_matcher = _load_nlp()

# Product aliases for fast phrase matching (Malay + EN)
PRODUCT_ALIASES = {
    "hospital bed 2 function": ["katil 2 function manual","2 function manual bed","katil 2 fungsi manual"],
    "hospital bed 3 function": ["katil 3 fungsi manual","3 function manual bed","hospital bed 3 function manual"],
    "hospital bed 5 function": ["katil 5 fungsi","5 function bed"],
    "hospital bed 3 function auto": ["katil 3 fungsi auto","3 function auto bed","3 fungsi auto"],
    "wheelchair steel": ["auto travel steel wheelchair","steel wheelchair","kerusi roda besi","auto wheelchair steel"],
    "wheelchair aluminium": ["auto wheelchair aluminium","aluminium wheelchair","kerusi roda aluminium"],
    "wheelchair heavy duty": ["heavy duty wheelchair","kerusi roda heavy duty"],
    "oxygen concentrator 5l": ["oxygen concentrator 5l","oc 5l","oksigen 5l"],
    "oxygen concentrator 10l": ["oxygen concentrator 10l","oc 10l","oksigen 10l"],
    "oxygen tank": ["oxygen tank","tong oksigen","oxygen cylinder","cylinder oksigen"],
    "combo 5l oxygen concentrator & oxygen tank": ["combo 5l oxygen concentrator & oxygen tank","combo oc 5l + tank","combo oksigen 5l + tong"],
}

if phrase_matcher is not None:
    for canon, aliases in PRODUCT_ALIASES.items():
        for ph in [canon] + aliases:
            phrase_matcher.add(canon, [nlp.make_doc(ph)])  # type: ignore

ORDER_CODE_RE = re.compile(r'\b([A-Z]{2,3}-?\d{3,6})\b')
PHONE_RE = re.compile(r'(\+?\d[\d\s\-]{6,}\d)')

def norm_phone(s: str) -> Optional[str]:
    m = PHONE_RE.search(s)
    if not m: return None
    digits = re.sub(r'\D+', '', m.group(1))
    return digits if 7 <= len(digits) <= 15 else None

def extract_schedule(text: str) -> Dict[str,Optional[str]]:
    dt = None
    # dd/mm/yy or dd-mm-yy
    for tok in re.findall(r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', text):
        try:
            dt = dateparser.parse(tok, dayfirst=True)
            if dt: break
        except Exception: pass
    # time like 12:30 / 12.30 / 12pm
    tm = None
    m = re.search(r'(\d{1,2}[:.]\d{2}\s*(?:am|pm)?)', text, re.I)
    if m: tm = m.group(1)
    return {"date": dt.date().isoformat() if dt else None, "time": tm}

def parse_money_near(text: str, key: str) -> Optional[float]:
    for line in text.splitlines():
        if key.lower() in line.lower():
            mm = re.search(r'RM\s*([0-9]+(?:[.,][0-9]{1,2})?)', line, re.I)
            if mm:
                try: return float(mm.group(1).replace(',',''))
                except: pass
            mm = re.search(r'([0-9]+(?:[.,][0-9]{1,2})?)', line)
            if mm:
                try: return float(mm.group(1).replace(',',''))
                except: pass
    return None

def spacy_extract_hints(text: str, lang: str="en") -> Dict[str,Any]:
    name = None
    if nlp is not None:
        doc = nlp(text)
        for ent in doc.ents:
            if ent.label_ in ("PERSON",):
                name = ent.text.strip()
                break
        items = []
        if phrase_matcher is not None:
            for mid, start, end in phrase_matcher(doc):
                label = nlp.vocab.strings[mid]
                if not any(i["name"].lower()==label for i in items):
                    items.append({"name": label, "qty": 1})
    else:
        items, doc = [], None

    phone = norm_phone(text)
    up = text.upper()

    type_hint = "RENTAL" if ("SEWA" in up or "RENT" in up) else ("OUTRIGHT" if ("BELI" in up or "BUY" in up) else None)

    intent = None
    if any(k in up for k in ["INSTALMENT CANCEL","INSTALLMENT CANCEL","BATAL ANSURAN","CANCEL ANSURAN"]): intent="INSTALMENT_CANCEL"
    if any(k in up for k in ["BUYBACK","JUAL BALIK","SELL BACK"]): intent="BUYBACK"
    if any(k in up for k in ["RETURN","PULANG"]): intent="RETURN"
    if any(k in up for k in ["COLLECT","PICKUP","PICK UP","AMBIL"]): intent="COLLECT" if intent is None else intent

    schedule = extract_schedule(text)
    outbound = parse_money_near(text, "Penghantaran") or parse_money_near(text, "Delivery") or 0.0
    return_fee = parse_money_near(text, "Pickup") or parse_money_near(text, "Collect") or 0.0
    total = parse_money_near(text, "Total") or 0.0
    paid = parse_money_near(text, "Paid") or parse_money_near(text, "Deposit") or 0.0
    balance = parse_money_near(text, "Balance") or parse_money_near(text, "To collect") or 0.0

    mcode = ORDER_CODE_RE.search(text)
    order_code = mcode.group(1).replace(" ", "") if mcode else None

    return {
        "order_code": order_code,
        "customer_name": name,
        "phone": phone,
        "items": items,
        "type_hint": type_hint,
        "intent": intent,
        "delivery": {"outbound_fee": float(outbound), "return_fee": float(return_fee)},
        "totals": {"total": float(total), "paid": float(paid), "balance": float(balance)},
        "schedule": schedule
    }
