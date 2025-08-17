import os
from typing import Dict, Any
from pydantic import ValidationError
from .schemas import ParsedOrder

SYSTEM = """You are an order extraction engine for a Malaysian medical equipment company.
Output ONLY valid JSON that matches the provided JSON schema.
Malay or English inputs. Map 'Sewa'->RENTAL, 'Beli'->OUTRIGHT, 'Ansuran' or 'Instalment'->INSTALMENT.
Infer quantities (default 1), prices (if shown), and fees.
"""

def client_or_none():
    try:
        from openai import OpenAI
        key = os.getenv("OPENAI_API_KEY")
        if not key: 
            return None
        return OpenAI(api_key=key)
    except Exception:
        return None

def parse_message_strict(client, text: str) -> Dict[str, Any]:
    if client is None:
        raise RuntimeError("No OpenAI client")
    completion = client.chat.completions.create(
        model="gpt-4o-mini",
        response_format={"type": "json_object"},
        messages=[
            {"role":"system","content":SYSTEM},
            {"role":"user","content":text}
        ],
        temperature=0
    )
    data = completion.choices[0].message.content
    obj = ParsedOrder.model_validate_json(data)  # raises ValidationError if invalid
    return obj.model_dump()
