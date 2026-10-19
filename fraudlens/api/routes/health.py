import os

from fastapi import APIRouter, Request

from fraudlens.api.state import state

router = APIRouter(prefix="/health", tags=["health"])
# Kept off the authenticated /ops router so uptime checks need no token.
public_status_router = APIRouter(prefix="/ops", tags=["health"])


@router.get("")
def health() -> dict:
    return {"status": "ok"}


@public_status_router.get("/public-status")
def public_status() -> dict:
    return {"ready": state.started_at is not None, "mode": os.environ.get("FRAUDLENS_MODE", "demo"),
            "started_at": state.started_at}


# TEMPORARY (2026-10-19): which client-address headers reach the API behind the
# hosting edge. Values are salted hashes only; no addresses are returned.
_SALT = os.urandom(16)


@public_status_router.get("/client-key-check")
def client_key_check(request: Request) -> dict:
    import hashlib

    def digest(value):
        return hashlib.sha256(_SALT + value.strip().encode()).hexdigest()[:8] if value else None

    forwarded = [part.strip() for part in request.headers.get("x-forwarded-for", "").split(",") if part.strip()]
    return {"peer": digest(request.client.host if request.client else ""),
            "headers": sorted(h for h in request.headers.keys() if "ip" in h or "forward" in h or h.startswith("cf-") or "client" in h),
            "x_forwarded_for": [digest(part) for part in forwarded],
            "cf_connecting_ip": digest(request.headers.get("cf-connecting-ip", "")),
            "true_client_ip": digest(request.headers.get("true-client-ip", "")),
            "x_real_ip": digest(request.headers.get("x-real-ip", ""))}
