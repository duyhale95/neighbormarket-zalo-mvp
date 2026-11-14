"""Vietnamese VND parser adapted from VHR-07, MIT (THIRD_PARTY_NOTICES.md)."""
import re
import unicodedata
from decimal import Decimal, InvalidOperation


def fold(value: str) -> str:
    value = unicodedata.normalize('NFD', value.casefold().replace('đ','d'))
    return ''.join(c for c in value if unicodedata.category(c) != 'Mn')


_MILLION = r'tr|trieu|cu'
_THOUSAND = r'k|nghin|ngan'
_PRICE = re.compile(rf'(?P<num>\d+(?:[.,]\d+)*)\s*(?P<unit>{_MILLION}|{_THOUSAND})?\s*'
                    rf'(?P<rest>\d{{1,3}})?\s*(?P<rest_unit>{_THOUSAND})?\s*(?:d|vnd|dong)?')
_GROUPED = re.compile(r'\d{1,3}(?:([.,])\d{3})(?:\1\d{3})*')


def parse_vnd(text: str) -> int | None:
    """No units and <1000 is ambiguous; a duration is never a price."""
    match = _PRICE.fullmatch(' '.join(fold(text).split()))
    if match is None:
        return None
    token=match['num']
    if _GROUPED.fullmatch(token):
        number=Decimal(re.sub(r'[.,]','',token))
    else:
        if token.count('.')+token.count(',')>1: return None
        try: number=Decimal(token.replace(',','.'))
        except InvalidOperation: return None
    unit,rest,rest_unit=match['unit'],match['rest'],match['rest_unit']
    million=unit is not None and re.fullmatch(_MILLION,unit) is not None
    if rest is not None and not million: return None
    if rest_unit is not None and rest is None: return None
    if million:
        value=number*1_000_000
        if rest is not None:
            if number!=number.to_integral_value(): return None
            value+=int(rest)*1000 if rest_unit else int(rest)*10**(6-len(rest))
    elif unit is not None:
        value=number*1000
    else:
        if number<1000: return None
        value=number
    if value!=value.to_integral_value() or not 0<value<=1_000_000_000: return None
    return int(value)
