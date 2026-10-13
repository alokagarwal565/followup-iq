def phone_digits(phone: str) -> str:
    """Digits-only form used for duplicate detection, so formatting differences still collide."""
    return "".join(ch for ch in phone if ch.isdigit())
