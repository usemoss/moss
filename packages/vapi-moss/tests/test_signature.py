"""Tests for VAPI webhook signature verification."""

import hashlib
import hmac

from vapi_moss.signature import verify_vapi_signature


def _sign(body: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


BODY = b'{"message": "hello"}'
SECRET = "test-secret"


def test_valid_signature():
    sig = _sign(BODY, SECRET)
    assert verify_vapi_signature(BODY, sig, SECRET) is True


def test_invalid_signature():
    assert verify_vapi_signature(BODY, "sha256=bad", SECRET) is False


def test_wrong_secret():
    sig = _sign(BODY, "wrong-secret")
    assert verify_vapi_signature(BODY, sig, SECRET) is False


def test_empty_signature():
    assert verify_vapi_signature(BODY, "", SECRET) is False


def test_uppercase_prefix():
    digest = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    sig = f"SHA256={digest}"
    assert verify_vapi_signature(BODY, sig, SECRET) is True


def test_whitespace_in_header():
    sig = _sign(BODY, SECRET)
    assert verify_vapi_signature(BODY, f"  {sig}  ", SECRET) is True


def test_bare_digest():
    digest = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    assert verify_vapi_signature(BODY, digest, SECRET) is True


def test_wrong_algorithm_prefix():
    digest = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    assert verify_vapi_signature(BODY, f"sha512={digest}", SECRET) is False
