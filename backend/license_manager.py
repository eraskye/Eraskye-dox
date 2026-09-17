import os
import secrets
import string
from datetime import datetime, timedelta, timezone

from database import db

ALPHABET = string.ascii_uppercase + string.digits
VALID_DURATIONS = (1, 3, 7, 30)


# ---------- helpers ----------

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _parse_iso(s: str) -> datetime:
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _gen_key() -> str:
    # CLV-XXXXX-XXXXX-XXXXX-XXXXX
    groups = ["".join(secrets.choice(ALPHABET) for _ in range(5)) for _ in range(4)]
    return "CLV-" + "-".join(groups)


# ---------- public API ----------

def create_license(days: int) -> dict:
    if days not in VALID_DURATIONS:
        raise ValueError("INVALID_DURATION")

    now = _now()
    with db() as conn:
        key = _gen_key()
        while conn.execute("SELECT 1 FROM licenses WHERE key=?", (key,)).fetchone():
            key = _gen_key()
        conn.execute(
            """INSERT INTO licenses
               (key, created_at, expires_at, duration, device_id, status, activated_at)
               VALUES (?,?,?,?,?,?,?)""",
            (key, _iso(now), None, days, None, "unused", None),
        )

    return {
        "key": key,
        "duration": days,
        "created_at": _iso(now),
        "expires_at": None,
        "status": "unused",
    }


def check_and_activate(key: str, device_id: str) -> dict:
    """
    Server-side source of truth.
    Returns dict with keys: ok, status, error?, expires_at?, remaining_seconds?, duration?
    Status: ACTIVE | EXPIRED | INVALID | DEVICE_MISMATCH
    """
    if not key or not device_id:
        return {"ok": False, "status": "INVALID", "error": "MISSING_FIELDS"}

    with db() as conn:
        row = conn.execute("SELECT * FROM licenses WHERE key=?", (key,)).fetchone()
        if not row:
            return {"ok": False, "status": "INVALID", "error": "INVALID_LICENSE"}

        row = dict(row)

        if row["status"] == "revoked":
            return {"ok": False, "status": "INVALID", "error": "REVOKED_LICENSE"}

        now = _now()

        # ---------- unbound: activate & bind ----------
        if not row["device_id"]:
            expires = now + timedelta(days=row["duration"])
            conn.execute(
                """UPDATE licenses
                   SET device_id=?, activated_at=?, expires_at=?, status='active'
                   WHERE key=?""",
                (device_id, _iso(now), _iso(expires), key),
            )
            return {
                "ok": True,
                "status": "ACTIVE",
                "expires_at": _iso(expires),
                "duration": row["duration"],
                "remaining_seconds": int((expires - now).total_seconds()),
                "device_status": "BOUND",
            }

        # ---------- device mismatch ----------
        if row["device_id"] != device_id:
            return {
                "ok": False,
                "status": "DEVICE_MISMATCH",
                "error": "DEVICE_MISMATCH",
            }

        # ---------- expiry ----------
        if not row["expires_at"]:
            return {"ok": False, "status": "EXPIRED", "error": "EXPIRED_LICENSE"}

        expires = _parse_iso(row["expires_at"])
        if expires <= now:
            conn.execute(
                "UPDATE licenses SET status='expired' WHERE key=?", (key,)
            )
            return {"ok": False, "status": "EXPIRED", "error": "EXPIRED_LICENSE"}

        remaining = int((expires - now).total_seconds())
        return {
            "ok": True,
            "status": "ACTIVE",
            "expires_at": row["expires_at"],
            "duration": row["duration"],
            "remaining_seconds": remaining,
            "device_status": "BOUND",
        }


def list_licenses() -> list:
    with db() as conn:
        rows = conn.execute(
            """SELECT key, created_at, expires_at, duration, device_id, status, activated_at
               FROM licenses ORDER BY created_at DESC"""
        ).fetchall()

    now = _now()
    out = []
    for r in rows:
        r = dict(r)
        r["bound"] = bool(r["device_id"])
        # mask device_id for privacy in admin list
        if r["device_id"]:
            r["device_id_short"] = r["device_id"][:8] + "…"
        else:
            r["device_id_short"] = None
        if r["expires_at"]:
            try:
                exp = _parse_iso(r["expires_at"])
                delta = int((exp - now).total_seconds())
                r["remaining_seconds"] = max(delta, 0)
                r["expired"] = delta <= 0
            except Exception:
                r["remaining_seconds"] = 0
                r["expired"] = True
        else:
            r["remaining_seconds"] = None
            r["expired"] = False
        out.append(r)
    return out


def revoke_license(key: str) -> bool:
    with db() as conn:
        cur = conn.execute(
            "UPDATE licenses SET status='revoked' WHERE key=?", (key,)
        )
        return cur.rowcount > 0


def delete_license(key: str) -> bool:
    with db() as conn:
        cur = conn.execute("DELETE FROM licenses WHERE key=?", (key,))
        return cur.rowcount > 0
