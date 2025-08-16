import re

def norm_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    digits = re.sub(r"^(60|0)+", "", digits)
    return digits
