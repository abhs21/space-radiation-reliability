import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, localcontext
from fractions import Fraction

TIMESTAMP = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d+))?(Z|[+-]\d{2}:\d{2})?')
MINUTE_TIMESTAMP = re.compile(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2})(Z|[+-]\d{2}:\d{2})?')
EPOCH_DAY = date(1970, 1, 1)


def parse_timestamp(text, allow_minutes=False):
    if allow_minutes:
        if len(text) > 10 and text[10] == ' ':
            text = text[:10] + 'T' + text[11:]
        text = text.replace(',', '.')
        short_offset = re.search(r'([+-])(\d{2})(\d{2})?$', text)
        if short_offset:
            text = text[:short_offset.start()] + short_offset[1] + short_offset[2] + ':' + (short_offset[3] or '00')
    match = TIMESTAMP.fullmatch(text)
    if not match:
        minute_match = MINUTE_TIMESTAMP.fullmatch(text) if allow_minutes else None
        if not minute_match:
            raise ValueError('Expected ISO timestamp with seconds')
        base, offset = minute_match.groups()
        base, fractional = base + ':00', None
    else:
        base, fractional, offset = match.groups()
    if offset and offset != 'Z' and (int(offset[1:3]) > 23 or int(offset[4:6]) > 59):
        raise ValueError('Invalid timestamp offset')
    stamp = datetime.fromisoformat(base + (offset or '').replace('Z', '+00:00'))
    aware = offset is not None
    epoch = datetime(1970, 1, 1, tzinfo=timezone.utc) if aware else datetime(1970, 1, 1)
    delta = stamp - epoch
    seconds = Fraction(delta.days * 86400 + delta.seconds)
    if fractional:
        seconds += Fraction(int(fractional), 10 ** len(fractional))
    return seconds, aware


def decimal_text(value):
    if value is None:
        return None
    with localcontext() as context:
        context.prec = 50
        return str(Decimal(value.numerator) / Decimal(value.denominator))


def utc_day(seconds):
    return EPOCH_DAY + timedelta(days=seconds // 86400)


def midnight_seconds(day):
    return Fraction((day - EPOCH_DAY).days * 86400)


def format_timestamp(seconds, aware=False):
    whole = seconds // 1
    fraction = seconds - whole
    stamp = datetime(1970, 1, 1) + timedelta(seconds=whole)
    text = stamp.isoformat()
    if fraction:
        with localcontext() as context:
            context.prec = max(50, len(str(fraction.denominator)) + 5)
            digits = format(Decimal(fraction.numerator) / Decimal(fraction.denominator), 'f').split('.')[1]
        text += '.' + digits.rstrip('0').ljust(6, '0')
    return text + ('+00:00' if aware else '')
