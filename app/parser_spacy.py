import os, re, json
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple

# Optional spaCy (fallbacks to heuristics if missing)
try:
    import spacy  # type: ignore
    try:
        _NLP = spacy.load("en_core_web_sm")
    except Exception:
        _NLP = None
except Exception:
    _NLP = None

# Basic Malay/English keywords -> intent
_EVENT_KEYWORDS = [
    (r'\b(return|pulangkan|pickup|collect|ambil|ambil\s+balik)\b', "RETURN"),   # we normalize pickup/collect under RETURN for rental pickup
    (r'\b(collect(ed)?|collection|collect back|ambil)\b', "COLLECT"),
    (r'\b(instal(l)?ment\s+cancel|ansuran\s+(batal|cancel|terminate)|terminate\s+instal(l)?ment)\b', "INSTALMENT_CANCEL"),
    (r'\b(buy\s*back|jual\s*balik|buyback|sell\s*back)\b', "BUYBACK"),
]

# Type hints from Malay/English
_TYPE_HINTS = [
    (r'\b(sewa|rental)\b', "RENTAL"),
    (r'\b(ansuran|instal(l)?ment)\b', "INSTALMENT"),
    (r'\b(beli|outright|purchase)\b', "OUTRIGHT"),
]

# Item synonym map -> canonical SKU & name
_ITEM_MAP = [
    (r'katil\s*2\s*function|2\s*fungsi\s*manual', ("BED-2F-MAN", "Hospital Bed 2-function Manual")),
    (r'katil\s*3\s*function|3\s*fungsi\s*manual', ("BED-3F-MAN", "Hospital Bed 3-function Manual")),
    (r'katil\s*5\s*function|5\s*fungsi',          ("BED-5F",     "Hospital Bed 5-function")),
    (r'katil\s*3\s*function.*auto',               ("BED-3F-AUTO","Hospital Bed 3-function Auto")),
    (r'auto\s*travel\s*steel\s*wheelchair',       ("WHL-TRAVEL-STEEL", "Auto Travel Steel Wheelchair")),
    (r'auto\s*wheelchair\s*alum(inium|inum)',     ("WHL-AUTO-ALU","Auto Wheelchair Aluminium")),
    (r'heavy\s*duty.*wheelchair',                 ("WHL-HEAVY",  "Heavy Duty Auto Wheelchair")),
    (r'wheelchair\s*(standard)?',                 ("WHL-STD",    "Wheelchair (Standard)")),
    (r'oxygen\s*concentrator\s*5l|5\s*l(itre)?',  ("O2-CONC5",   "Oxygen Concentrator 5L")),
    (r'oxygen\s*concentrator\s*10l|10\s*l(itre)?',("O2-CONC10",  "Oxygen Concentrator 10L")),
    (r'oxygen\s*tank|tong\s*oksigen',             ("O2-TANK",    "Oxygen Tank")),
    (r'tilam\s*canvas|canvas\s*mattress',         ("MAT-CANVAS", "Canvas Mattress")),
]

_MONEY = r'RM\s*([0-9]+(?:\.[0-9]{1,2})?)'
_DATE_DMY = r'(\b\d{1,2})/(\d{1,2})/(\d{2,4})'
_TIME_12H = r'\b(\d{1,2})(?::(\d{2}))?\s*(am|pm|ptg)?\b'

def _norm_phone(s: str) -> Optional[str]:
    s = re.sub(r'[^0-9+]', '', s)
    return s if len(s) >= 7 else None

def _find_first(regex: str, s: str, flags=0) -> Optional[re.Match]:
    m = re.search(regex, s, flags)
    return m

def _parse_date_time(text: str) -> Tuple[Optional[date], Optional[str]]:
    d = None; t = None
    m = _find_first(_DATE_DMY, text)
    if m:
        dd, mm, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if yy < 100: yy += 2000
        try:
            d = date(yy, mm, dd)
        except Exception:
            d = None
    m2 = _find_first(_TIME_12H, text, flags=re.IGNORECASE)
    if m2:
        hh = int(m2.group(1))
        mm = int(m2.group(2) or 0)
        ap = (m2.group(3) or "").lower()
        if ap in ("pm","ptg") and hh < 12: hh += 12
        t = f"{hh:02d}:{mm:02d}"
    return d, t

def _guess_intent(text_up: str) -> Optional[str]:
    for rx, val in _EVENT_KEYWORDS:
        if re.search(rx, text_up, flags=re.IGNORECASE):
            return val
    return None

def _guess_type(text_up: str) -> Optional[str]:
    for rx, val in _TYPE_HINTS:
        if re.search(rx, text_up, flags=re.IGNORECASE):
            return val
    return None

def _match_item(line: str) -> Optional[Tuple[str,str]]:
    lu = line.lower()
    for rx, (sku, name) in _ITEM_MAP:
        if re.search(rx, lu, flags=re.IGNORECASE):
            return sku, name
    return None

def _parse_items(lines: List[str]) -> List[Dict[str, Any]]:
    items: List[Dict[str,Any]] = []
    for ln in lines:
        syn = _match_item(ln)
        if not syn: continue
        sku, name = syn
        qty = 1
        mqty = re.search(r'(\d+)\s*[x×]', ln, flags=re.IGNORECASE)
        if mqty: qty = int(mqty.group(1))
        unit_price = None
        rent_monthly = None

        # monthly or outright?
        #  "...= RM320/month",  "RM250/bulan",  "RM199"
        mRM = re.search(_MONEY, ln, flags=re.IGNORECASE)
        if mRM:
            amt = float(mRM.group(1))
            if re.search(r'(bulan|month|/m)', ln, flags=re.IGNORECASE):
                rent_monthly = amt
            else:
                unit_price = amt

        items.append({"sku": sku, "name": name, "qty": qty, "unit_price": unit_price, "rent_monthly": rent_monthly, "buyback_rate": None})
    return items

def _ner_name_address_phone(text: str) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    # Heuristics first
    phone = None
    mphone = _find_first(r'(?:H/P|HP|Telefon|Tel|Phone|No(?:\s*telefon)?)[\s:]*([+0-9 ()-]{6,})', text, flags=re.IGNORECASE)
    if mphone: phone = _norm_phone(mphone.group(1))
    if not phone:
        m2 = _find_first(r'(\+?\d[\d ()-]{6,}\d)', text)
        if m2: phone = _norm_phone(m2.group(1))

    # Simple name/address heuristics around "Name|Nama|Patient|Alamat|Address"
    name = None
    addr = None
    mname = _find_first(r'(?:Name|Nama|Patient Name|Patient)\s*[:\-]\s*(.+)', text, flags=re.IGNORECASE)
    if mname:
        name = mname.group(1).strip()
    madd = _find_first(r'(?:Alamat|Address)\s*[:\-]\s*(.+)', text, flags=re.IGNORECASE)
    if madd:
        addr = madd.group(1).strip()

    # spaCy NER assist (english model; still helps on names/locations)
    if _NLP:
        doc = _NLP(text)
        # prefer PERSON for name; GPE/LOC for address-like hints
        if not name:
            person = [e.text.strip() for e in doc.ents if e.label_=="PERSON"]
            if person: name = person[0]
        if not addr:
            locs = [e.text.strip() for e in doc.ents if e.label_ in ("GPE","LOC","FAC")]
            if locs:
                # take the longest location-ish span as address hint
                addr = max(locs, key=len)

    return name, addr, phone

def parse_whatsapp(text: str, openai_client=None) -> Dict[str, Any]:
    """Return dict with keys: order_code, intent, type, schedule{date,time}, customer{name,phone,address}, items[], delivery{outbound_fee,return_fee}, totals{total,paid,balance}."""
    text_up = text.upper()

    # order code e.g. OC1980, KP1977, WC1979, OS-1234
    code = None
    mcode = _find_first(r'\b([A-Z]{2,4}-?\d{3,6})\b', text_up)
    if mcode:
        code = mcode.group(1)

    intent = _guess_intent(text_up)
    typ = _guess_type(text_up)

    sched_date, sched_time = _parse_date_time(text)

    name, addr, phone = _ner_name_address_phone(text)

    # scan lines for items + charges
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    items = _parse_items(lines)

    outbound = 0.0; retfee = 0.0
    # detect delivery charges
    for ln in lines:
        if re.search(r'(delivery|penghantaran|hantar|pasang)', ln, flags=re.IGNORECASE):
            m = re.search(_MONEY, ln, flags=re.IGNORECASE)
            if m: outbound += float(m.group(1))
        if re.search(r'(pickup|return|collect|ambil\s*balik)', ln, flags=re.IGNORECASE):
            m = re.search(_MONEY, ln, flags=re.IGNORECASE)
            if m: retfee += float(m.group(1))

    # totals (if provided in the text)
    total = None; paid = None; balance = None
    for ln in lines:
        if re.search(r'\b(total)\b', ln, flags=re.IGNORECASE):
            m = re.search(_MONEY, ln, flags=re.IGNORECASE)
            if m: total = float(m.group(1))
        if re.search(r'\b(paid|bayar|booking)\b', ln, flags=re.IGNORECASE):
            m = re.search(_MONEY, ln, flags=re.IGNORECASE)
            if m: paid = float(m.group(1))
        if re.search(r'\b(balance|baki|to\s*collect)\b', ln, flags=re.IGNORECASE):
            m = re.search(_MONEY, ln, flags=re.IGNORECASE)
            if m: balance = float(m.group(1))

    # If OpenAI is available, ask it to fill missing bits against a strict schema.
    if openai_client is not None:
        schema_prompt = {
            "role": "system",
            "content": (
                "You extract rental/sale orders from WhatsApp text as strict JSON.\n"
                "Schema keys (null if unknown):\n"
                "{"
                "\"order_code\": string|null,\n"
                "\"intent\": \"RETURN\"|\"COLLECT\"|\"INSTALMENT_CANCEL\"|\"BUYBACK\"|null,\n"
                "\"type\": \"RENTAL\"|\"INSTALMENT\"|\"OUTRIGHT\"|null,\n"
                "\"schedule\": {\"date\": string(YYYY-MM-DD)|null, \"time\": string(HH:MM)|null},\n"
                "\"customer\": {\"name\": string|null, \"phone\": string|null, \"address\": string|null},\n"
                "\"delivery\": {\"outbound_fee\": number, \"return_fee\": number},\n"
                "\"items\": [{\"name\": string, \"qty\": number, \"sku\": string|null, \"unit_price\": number|null, \"rent_monthly\": number|null, \"buyback_rate\": number|null}],\n"
                "\"totals\": {\"total\": number|null, \"paid\": number|null, \"balance\": number|null}\n"
                "}"
            )
        }
        user_prompt = {"role":"user","content": text}
        try:
            resp = openai_client.chat.completions.create(
                model=os.getenv("OPENAI_MODEL","gpt-4o-mini"),
                messages=[schema_prompt, user_prompt],
                response_format={"type":"json_object"},
                temperature=0
            )
            data = json.loads(resp.choices[0].message.content)

            # merge AI backfill with local guesses (local wins if already known)
            code = code or data.get("order_code")
            intent = intent or data.get("intent")
            typ = typ or data.get("type")
            if not sched_date or not sched_time:
                ai_sched = data.get("schedule") or {}
                if isinstance(ai_sched, dict):
                    if ai_sched.get("date"):
                        try:
                            y,m,d = [int(x) for x in ai_sched["date"].split("-")]
                            sched_date = date(y,m,d)
                        except Exception:
                            pass
                    if ai_sched.get("time"):
                        sched_time = ai_sched["time"]
            if not name:    name    = (data.get("customer") or {}).get("name")
            if not phone:   phone   = (data.get("customer") or {}).get("phone")
            if not addr:    addr    = (data.get("customer") or {}).get("address")
            di = data.get("delivery") or {}
            if isinstance(di, dict):
                outbound = float(di.get("outbound_fee") or outbound or 0)
                retfee   = float(di.get("return_fee")   or retfee   or 0)
            if not items and isinstance(data.get("items"), list):
                items = []
                for it in data["items"]:
                    nm = it.get("name") or "Item"
                    sku = it.get("sku")
                    if not sku:
                        msyn = _match_item(nm)
                        sku = msyn[0] if msyn else None
                    items.append({
                        "sku": sku,
                        "name": nm,
                        "qty": int(it.get("qty") or 1),
                        "unit_price": it.get("unit_price"),
                        "rent_monthly": it.get("rent_monthly"),
                        "buyback_rate": it.get("buyback_rate"),
                    })
            ti = data.get("totals") or {}
            total   = total   if total   is not None else (ti.get("total"))
            paid    = paid    if paid    is not None else (ti.get("paid"))
            balance = balance if balance is not None else (ti.get("balance"))
        except Exception:
            pass

    parsed = {
        "order_code": code,
        "intent": intent,
        "type": typ,
        "schedule": {"date": (sched_date.isoformat() if sched_date else None), "time": sched_time},
        "customer": {"name": name, "phone": phone, "address": addr},
        "delivery": {"outbound_fee": float(outbound or 0), "return_fee": float(retfee or 0)},
        "items": items,
        "totals": {"total": total, "paid": paid, "balance": balance},
    }
    # keep compatibility fields used by your UI
    match = {"order_code": code, "reason": "nlp+ai" if openai_client else "nlp"} if code else None
    return {"parsed": parsed, "match": match, "intent": intent}