from typing import Dict, Any, List
from .config import get_settings
from openai import OpenAI
import json

settings = get_settings()

# JSON Schema for strict extraction
OMS_SCHEMA = {
    "name": "oms_schema",
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "order_code": {"type": ["string", "null"]},
            "event_type": {"type": "string", "enum": ["DELIVERY", "RETURN", "INSTALMENT_CANCEL", "BUYBACK", "ADJUSTMENT"]},
            "delivery_date": {"type": ["string", "null"], "description": "ISO datetime if present"},
            "return_date": {"type": ["string", "null"]},
            "customer_name": {"type": ["string", "null"]},
            "phone": {"type": ["string", "null"]},
            "address": {"type": ["string", "null"]},
            "location_url": {"type": ["string", "null"]},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "text": {"type": "string"},
                        "item_type": {"type": "string", "enum": ["OUTRIGHT", "RENTAL", "INSTALMENT"]},
                        "sku": {"type": ["string", "null"]},
                        "name": {"type": ["string", "null"]},
                        "qty": {"type": ["number", "null"]},
                        "unit_price": {"type": ["number", "null"]},
                        "line_total": {"type": ["number", "null"]},
                        "months": {"type": ["integer", "null"]},
                        "monthly_amount": {"type": ["number", "null"]}
                    },
                    "required": ["text", "item_type"]
                }
            },
            "subtotal": {"type": ["number", "null"]},
            "discount": {"type": ["number", "null"]},
            "delivery_fee": {"type": ["number", "null"]},
            "return_delivery_fee": {"type": ["number", "null"]},
            "penalty_amount": {"type": ["number", "null"]},
            "buyback_amount": {"type": ["number", "null"]},
            "total": {"type": ["number", "null"]},
            "paid": {"type": ["number", "null"]},
            "to_collect": {"type": ["number", "null"]},
            "notes": {"type": ["string", "null"]}
        },
        "required": ["event_type", "items"]
    }
}

SYSTEM_PROMPT = """You are an order-intake extraction assistant for a Malaysian medical equipment company.
Parse noisy WhatsApp messages (often mixing English & Malay) into a strict JSON object that matches the provided JSON schema.
Rules:
- Detect order code when present, e.g., 'KP1989', include as order_code.
- event_type: DELIVERY (default), RETURN (for pickup/return), INSTALMENT_CANCEL (for cancelling instalments), BUYBACK (if patient passed away and company buys back).
- Items: For each line describing a product or service, extract item_type:
  * RENTAL lines usually contain '(Sewa)' and monthly texts like 'RM 250/bulanan'.
  * OUTRIGHT lines include '(Beli)' or 'BELI'.
  * INSTALMENT lines mention months and monthly payments.
- Extract prices (unit_price) and totals when specified. If a line says 'Total After discount - RM1900', put 1900 in total and set discount if mentioned.
- delivery_fee: from 'Penghantaran & Pemasangan' or 'Hantar dan pemasangan' lines (one way). If return collection fee mentioned, set return_delivery_fee.
- paid and to_collect from 'Paid - RMx' and 'To collect - RMy'.
- Preserve free-text notes in 'notes' (e.g., 'bawa dua jenis untuk customer try dulu').
- If exact SKU is unknown, set sku null and keep the text in 'text' and 'name'.
- Use numbers only (no 'RM' string)."""

def parse_message(text: str) -> Dict[str, Any]:
    client = OpenAI(api_key=settings.openai_api_key)
    model = settings.openai_model or "gpt-4o-mini"

    prompt = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": text
        }
    ]

    try:
        # Prefer Responses API with JSON Schema if available
        response = None
        try:
            response = client.responses.create(
                model=model,
                input=prompt,
                response_format={
                    "type": "json_schema",
                    "json_schema": OMS_SCHEMA
                }
            )
            content = response.output[0].content[0].text  # type: ignore
        except Exception:
            # Fallback to chat.completions with "JSON" mode (best-effort)
            chat = client.chat.completions.create(
                model=model,
                messages=prompt,
                response_format={"type": "json_object"}
            )
            content = chat.choices[0].message.content  # type: ignore

        data = json.loads(content)
        return data
    except Exception as e:
        # Return a best-effort minimal object
        return {"event_type": "DELIVERY", "items": [], "notes": f"parse_error: {e}"}
