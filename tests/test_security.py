import pytest

from kara.security import TokenError, create_access_token, decode_access_token, hash_password, verify_password


def test_hash_password_roundtrip():
    hashed = hash_password("secret-pass-123")
    assert hashed != "secret-pass-123"
    assert verify_password("secret-pass-123", hashed)


def test_verify_rejects_wrong_password():
    hashed = hash_password("secret-pass-123")
    assert not verify_password("wrong-pass", hashed)


def test_verify_rejects_garbage_hash():
    assert not verify_password("whatever", "not-a-hash")


SECRET = "test-secret-key-at-least-32-bytes-long"


def test_token_roundtrip():
    token = create_access_token(7, SECRET, 60)
    assert decode_access_token(token, SECRET) == 7


def test_token_rejects_wrong_secret():
    token = create_access_token(7, SECRET, 60)
    with pytest.raises(TokenError):
        decode_access_token(token, "other-secret")


def test_token_rejects_expired_token():
    token = create_access_token(7, SECRET, -10)
    with pytest.raises(TokenError):
        decode_access_token(token, SECRET)
