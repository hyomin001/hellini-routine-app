# -*- coding: utf-8 -*-
"""
비밀번호 해싱 (PBKDF2-HMAC-SHA256, 표준 라이브러리만 사용).
bcrypt 등 외부 C 확장 의존성 없이 Streamlit Cloud에 바로 배포 가능하게 하기 위함.
"""
import hashlib
import os
import binascii
from typing import Optional, Tuple

_ITERATIONS = 200_000


def hash_password(password: str, salt_hex: Optional[str] = None) -> Tuple[str, str]:
    """returns (salt_hex, hash_hex)"""
    salt = binascii.unhexlify(salt_hex) if salt_hex else os.urandom(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _ITERATIONS)
    return binascii.hexlify(salt).decode(), binascii.hexlify(dk).decode()


def verify_password(password: str, salt_hex: str, hash_hex: str) -> bool:
    """입력한 비밀번호가 저장된 salt/hash와 일치하는지 검증한다."""
    _, dk_hex = hash_password(password, salt_hex)
    return dk_hex == hash_hex
