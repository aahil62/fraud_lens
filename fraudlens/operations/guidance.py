"""Source-linked design references, explicitly separate from certification."""

from .guidance_data import DISCLAIMER, REFERENCES, REQUIREMENTS


def guidance_response() -> dict:
    """Return the public guidance contract without implying legal compliance."""
    return {"references": REFERENCES, "requirements": REQUIREMENTS, "disclaimer": DISCLAIMER}
