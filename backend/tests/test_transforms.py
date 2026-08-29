import datetime as dt
from app.shared.utils import to_date, num, s

def test_to_date_yyyymmdd():
    assert to_date(20240930) == dt.date(2024, 9, 30)

def test_num_noise():
    assert num("#REF!") is None and num("1,5".replace(",", ".")) == 1.5

def test_s_blank():
    assert s("(en blanco)") is None
