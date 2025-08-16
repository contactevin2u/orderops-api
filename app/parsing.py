import re
import json
import openai
from .settings import settings

def parse_message(text: str, fast: bool = True, lenient: bool = True) -> dict:
    if settings.OPENAI_API_KEY and not fast:
        openai.api_key = settings.OPENAI_API_KEY
        prompt = f"Extract an order as JSON with keys: name, phone, order_id, type, due_date.\nText:\n{text}"
        # Simple call; in production use Chat Completions with response_format=json_object
        resp = openai.Completion.create(engine="text-davinci-003", prompt=prompt, max_tokens=256)
        try:
            parsed = json.loads(resp.choices[0].text.strip())
            return {"order": parsed}
        except Exception:
            if not lenient:
                return {}

    data = {"order": {}, "event": None}
    m = re.search(r"\b(01\d{8,9}|\+601\d{8,9})\b", text)
    if m:
        data["order"]["phone"] = m.group(1)
    m2 = re.search(r"\b(OUTRIGHT|RENTAL|INSTALMENT)\b", text, flags=re.I)
    if m2:
        data["order"]["type"] = m2.group(1).upper()
    return data
