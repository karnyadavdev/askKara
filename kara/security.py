from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

ALGORITHM = "HS256"
ISSUER = "askkara"


class TokenError(ValueError):
    pass


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(user_id: int, secret: str, ttl_seconds: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(seconds=ttl_seconds),
        "iss": ISSUER,
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str, secret: str) -> int:
    try:
        payload = jwt.decode(token, secret, algorithms=[ALGORITHM], issuer=ISSUER)
    except jwt.PyJWTError as exc:
        raise TokenError(str(exc)) from exc
    sub = str(payload.get("sub", ""))
    if not sub.isdigit():
        raise TokenError("invalid subject")
    return int(sub)
