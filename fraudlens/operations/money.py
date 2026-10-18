"""INR display without converting integer paise to floating point."""


def inr(amount_minor):
    rupees, paise = divmod(amount_minor, 100)
    digits = str(rupees)
    groups = [digits[-3:]]
    digits = digits[:-3]
    while digits:
        groups.insert(0, digits[-2:])
        digits = digits[:-2]
    return f"₹{','.join(groups)}.{paise:02d}"
