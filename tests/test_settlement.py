from app.util import norm_phone

def test_norm_phone():
    assert norm_phone("+6012-3456789") == "123456789"
