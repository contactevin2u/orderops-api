from typing import Any, Dict, List, Optional, Tuple
from rapidfuzz import process, fuzz
import json

from .catalog import CATALOG

# Optional import: date parsing without regex using dateutil
try:
    from dateutil import parser as dparser
except Exception:
    dparser = None  # handled below

INTENT_MAP = {
    "RETURN": ["return","pulangkan","dipulangkan","pulang","return rental"],
    "COLLECT": ["collect","pickup","pick up","ambil balik","kutip","ambil"],
    "INSTALMENT_CANCEL": ["batal ansuran","batal installment","cancel instalment","cancel installment","instalment cancel","installment cancel"],
    "BUYBACK": ["buyback","jual balik","sell back","sellback"],
}

def _lines(text: str) -> List[str]:
    return [ln.strip() for ln in text.replace("\r","").split("\n") if ln.strip()]

def _tokens(text: str) -> List[str]:
    sep = ",;:()[]{}|/\\-_•·—–\t"
    t = text
    for ch in sep:
        t = t.replace(ch, " ")
    return [tok for tok in t.split() if tok]

def guess_codes(text: str) -> List[str]:
    # No regex: pick tokens with >=2 letters & >=3 digits, 4<=len<=12
    seen, out = set(), []
    for tok in _tokens(text):
        letters = sum(1 for c in tok if c.isalpha())
        digits  = sum(1 for c in tok if c.isdigit())
        if letters >= 2 and digits >= 3 and 4 <= len(tok) <= 12:
            cand = tok.upper()
            if cand not in seen:
                seen.add(cand); out.append(cand)
    return out

def fuzzy_intent(text: str, threshold: int = 85) -> Optional[str]:
    t = text.lower()
    best: Tuple[Optional[str], int] = (None, -1)
    for label, phrases in INTENT_MAP.items():
        for ph in phrases:
            score = fuzz.token_set_ratio(t, ph)
            if score > best[1]:
                best = (label, score)
    return best[0] if best[1] >= threshold else None

def fuzzy_items(text: str, topn_per_line: int = 1, threshold: int = 80) -> List[Dict[str, Any]]:
    lines = _lines(text)
    catalog_targets = []
    for row in CATALOG:
        all_names = [row["name"]] + [a for a in (row.get("aliases") or [])]
        for n in all_names:
            catalog_targets.append((row, n.lower()))
    picked: List[Dict[str, Any]] = []
    for ln in lines:
        cand = process.extract(ln.lower(), [n for _,n in catalog_targets], scorer=fuzz.token_set_ratio, limit=topn_per_line)
        for (match_txt, score, idx) in cand:
            if score >= threshold:
                row = catalog_targets[idx][0]
                rent = True if any(k in ln.lower() for k in ["sewa","bulan","/bulan","rent","monthly","per month"]) else False
                picked.append({
                    "sku": row["sku"],
                    "name": row["name"],
                    "qty": 1,
                    "unit_price": None if rent else (row.get("sale_price") or None),
                    "rent_monthly": (row.get("rent_monthly") or None) if rent else None,
                    "buyback_rate": row.get("buyback_rate"),
                })
                break
    # dedupe
    seen = set(); uniq = []
    for it in picked:
        key = (it["sku"], bool(it["rent_monthly"]))
        if key not in seen:
            seen.add(key); uniq.append(it)
    return uniq

def parse_numbers_near_keywords(text: str) -> Dict[str, Optional[float]]:
    toks = _tokens(text.lower())
    def to_amount(tok: str) -> Optional[float]:
        s = tok.replace("rm","").replace("myr","").replace(",","").strip()
        try: return float(s)
        except: return None
    def find_amount_for(keys: List[str]) -> Optional[float]:
        for i, tok in enumerate(toks):
            if tok in keys:
                window = toks[i+1:i+5]
                for a in window:
                    v = to_amount(a)
                    if v is not None: return v
        return None
    return {
        "outbound_fee": find_amount_for(["penghantaran","delivery","pasang","install","installation"]),
        "return_fee":   find_amount_for(["return","collect","pickup","ambilan","ambil","kutip"]),
        "total":        find_amount_for(["total","jumlah"]),
        "paid":         find_amount_for(["paid","bayar","dibayar"]),
        "balance":      find_amount_for(["balance","baki"]),
    }

def extract_schedule(text: str) -> Dict[str, Optional[str]]:
    """Try to get delivery date/time without regex using dateutil.parse (fuzzy, dayfirst)."""
    if dparser is None:
        return {"date": None, "time": None}
    lines = _lines(text)
    keys = ["deliver","penghantaran","hantar","pasang","install","installation","delivery"]
    dt = None
    for ln in lines:
        if any(k in ln.lower() for k in keys):
            try:
                dt = dparser.parse(ln, fuzzy=True, dayfirst=True)
                break
            except Exception:
                continue
    if dt is None:
        try:
            dt = dparser.parse(text, fuzzy=True, dayfirst=True)
        except Exception:
            pass
    if dt is None:
        return {"date": None, "time": None}
    time_str = dt.strftime("%H:%M") if (dt.hour or dt.minute) else None
    return {"date": dt.date().isoformat(), "time": time_str}

def extract_plan(text: str) -> Dict[str, Optional[Any]]:
    """Get instalment/rental plan months and potential start date."""
    months = None
    toks = _tokens(text.lower())
    month_words = {"month","months","bulan","bln"}
    for i, tok in enumerate(toks):
        if tok.isdigit() and i+1 < len(toks) and toks[i+1] in month_words:
            try:
                months = int(tok)
                break
            except:
                pass
    start_date = None
    if dparser is not None:
        for ln in _lines(text):
            if any(k in ln.lower() for k in ["start","mula","bermula","mulai","start date","mula sewa","tarikh mula"]):
                try:
                    dt = dparser.parse(ln, fuzzy=True, dayfirst=True)
                    start_date = dt.date().isoformat()
                    break
                except Exception:
                    continue
    return {"months": months, "start_date": start_date}

SCHEMA = {
    "name": "order_parse",
    "schema": {
        "type": "object",
        "properties": {
            "order_code": {"type":"string","nullable": True},
            "customer_name": {"type":"string","nullable": True},
            "phone": {"type":"string","nullable": True},
            "address": {"type":"string","nullable": True},
            "items": {
                "type":"array",
                "items": {
                    "type":"object",
                    "properties": {
                        "sku":{"type":"string","nullable": True},
                        "name":{"type":"string"},
                        "qty":{"type":"integer","minimum":1},
                        "unit_price":{"type":"number","nullable": True},
                        "rent_monthly":{"type":"number","nullable": True},
                        "buyback_rate":{"type":"number","nullable": True}
                    },
                    "required":["name","qty"]
                }
            },
            "delivery":{"type":"object","properties":{
                "outbound_fee":{"type":"number","nullable": True},
                "return_fee":{"type":"number","nullable": True}
            }},
            "totals":{"type":"object","properties":{
                "total":{"type":"number","nullable": True},
                "paid":{"type":"number","nullable": True},
                "balance":{"type":"number","nullable": True}
            }},
            "schedule":{"type":"object","properties":{
                "date":{"type":"string","nullable": True},     # ISO yyyy-mm-dd
                "time":{"type":"string","nullable": True}      # HH:MM 24h
            }},
            "plan":{"type":"object","properties":{
                "months":{"type":"integer","nullable": True},
                "start_date":{"type":"string","nullable": True} # ISO yyyy-mm-dd
            }},
            "intent":{"type":"string","enum":["RETURN","COLLECT","INSTALMENT_CANCEL","BUYBACK",None]},
            "type_hint":{"type":"string","enum":["RENTAL","OUTRIGHT",None]}
        },
        "required":[]
    }
}

def ai_parse_text(openai_client, text: str, lang: str = "ms") -> Dict[str, Any]:
    """RapidFuzz builds hints; OpenAI returns schema JSON; merge with hints; no regex."""
    hints_items   = fuzzy_items(text)
    hints_intent  = fuzzy_intent(text)
    code_cands    = guess_codes(text)
    fee_hints     = parse_numbers_near_keywords(text)
    schedule_hint = extract_schedule(text)
    plan_hint     = extract_plan(text)
    type_hint     = "RENTAL" if any(w in text.lower() for w in ["sewa","rent","monthly","/bulan","bulan"]) else ("OUTRIGHT" if "beli" in text.lower() or "outright" in text.lower() else None)

    hints = {
        "intent": hints_intent,
        "code_candidates": code_cands,
        "items": hints_items,
        "fees": fee_hints,
        "schedule": schedule_hint,
        "plan": plan_hint,
        "type_hint": type_hint,
    }

    result: Dict[str, Any] = {"parsed": {}, "match": None, "intent": hints_intent, "hints": hints}

    if openai_client is None:
        order_code = code_cands[0] if code_cands else None
        result["parsed"] = {"hints": hints}
        result["match"]  = {"order_code": order_code, "reason":"fuzzy-hint"} if order_code else None
        return result

    sysmsg = "You are a structured data extractor. Return ONLY JSON that matches the provided schema. If a field is unknown, use null."
    usermsg = (
        "Extract order details from the text.\n\n"
        "Business rules:\n"
        "- 'Sewa' = RENTAL monthly; 'Beli' = OUTRIGHT.\n"
        "- Delivery/install are outbound fees; pickup/collect are return fees.\n"
        "- Items may be from catalog or new. If unsure of price, use null.\n"
        "- intent ∈ {RETURN, COLLECT, INSTALMENT_CANCEL, BUYBACK} or null.\n"
        "- schedule.date is yyyy-mm-dd; schedule.time is HH:MM 24h if specified.\n"
        "- plan.months is total months; plan.start_date is yyyy-mm-dd if specified.\n"
        f"Hints (fuzzy): {json.dumps(hints, ensure_ascii=False)}\n\n"
        f"Text:\n{text}"
    )

    ai_obj: Optional[Dict[str, Any]] = None
    try:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"system","content":sysmsg},{"role":"user","content":usermsg}],
            response_format={"type":"json_schema","json_schema":SCHEMA}
        )
        ai_obj = json.loads(resp.choices[0].message.content)
    except Exception:
        try:
            resp = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role":"system","content":sysmsg},{"role":"user","content":usermsg}],
                response_format={"type":"json_object"}
            )
            ai_obj = json.loads(resp.choices[0].message.content)
        except Exception:
            ai_obj = None

    order_code = (ai_obj or {}).get("order_code") or (code_cands[0] if code_cands else None)
    items      = (ai_obj or {}).get("items") or hints_items or []
    delivery   = (ai_obj or {}).get("delivery") or {"outbound_fee": fee_hints.get("outbound_fee"), "return_fee": fee_hints.get("return_fee")}
    totals     = (ai_obj or {}).get("totals") or {"total": fee_hints.get("total"), "paid": fee_hints.get("paid"), "balance": fee_hints.get("balance")}
    intent     = (ai_obj or {}).get("intent") or hints_intent
    type_hint2 = (ai_obj or {}).get("type_hint") or type_hint
    schedule   = (ai_obj or {}).get("schedule") or schedule_hint
    plan       = (ai_obj or {}).get("plan") or plan_hint

    parsed = {
        "order_code": order_code,
        "customer_name": (ai_obj or {}).get("customer_name"),
        "phone": (ai_obj or {}).get("phone"),
        "address": (ai_obj or {}).get("address"),
        "items": items,
        "delivery": delivery,
        "totals": totals,
        "schedule": schedule,
        "plan": plan,
        "type_hint": type_hint2,
    }
    return {
        "parsed": parsed,
        "match": {"order_code": order_code, "reason":"ai+fuzzy"} if order_code else None,
        "intent": intent,
        "hints": hints
    }
