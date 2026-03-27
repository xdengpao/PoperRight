"""
安全模块 — Security

实现需求 19：
- 19.1 传输安全：SSL/TLS 配置生成（NginxSSLConfig）
- 19.2 存储安全：数据加密存储（AES-256 XOR stub）+ 密码哈希（bcrypt stub）
- 19.3 访问安全：JWT 身份认证 + TOTP 二次验证 + API 频率限制
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Any


# ---------------------------------------------------------------------------
# 11.1 — NginxSSLConfig（传输安全）
# ---------------------------------------------------------------------------


class NginxSSLConfig:
    """生成 Nginx SSL/TLS 配置片段。

    不实际部署 Nginx，仅生成配置字符串供运维使用。
    """

    def __init__(
        self,
        server_name: str = "localhost",
        cert_path: str = "/etc/nginx/ssl/cert.pem",
        key_path: str = "/etc/nginx/ssl/key.pem",
        listen_port: int = 443,
        redirect_http: bool = True,
    ) -> None:
        self.server_name = server_name
        self.cert_path = cert_path
        self.key_path = key_path
        self.listen_port = listen_port
        self.redirect_http = redirect_http

    def generate(self) -> str:
        """生成完整的 Nginx SSL server 配置片段。"""
        parts: list[str] = []

        # HTTP → HTTPS redirect block
        if self.redirect_http:
            parts.append(
                "server {\n"
                "    listen 80;\n"
                f"    server_name {self.server_name};\n"
                "    return 301 https://$host$request_uri;\n"
                "}"
            )

        # HTTPS server block
        parts.append(
            "server {\n"
            f"    listen {self.listen_port} ssl;\n"
            f"    server_name {self.server_name};\n"
            "\n"
            f"    ssl_certificate {self.cert_path};\n"
            f"    ssl_certificate_key {self.key_path};\n"
            "    ssl_protocols TLSv1.2 TLSv1.3;\n"
            "    ssl_ciphers HIGH:!aNULL:!MD5;\n"
            "    ssl_prefer_server_ciphers on;\n"
            "\n"
            "    location / {\n"
            "        proxy_pass http://127.0.0.1:8000;\n"
            "        proxy_set_header Host $host;\n"
            "        proxy_set_header X-Real-IP $remote_addr;\n"
            "        proxy_set_header X-Forwarded-Proto $scheme;\n"
            "    }\n"
            "}"
        )

        return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# 11.2 — DataEncryptor（存储安全 — AES-256 XOR stub）
# ---------------------------------------------------------------------------


class DataEncryptor:
    """对称加密/解密（XOR-based stub 模拟 AES-256）。

    使用 key 的 SHA-256 摘要作为密钥流，对明文进行 XOR 加密。
    输出为 base64 编码字符串，便于存储。
    """

    @staticmethod
    def _derive_keystream(key: bytes, length: int) -> bytes:
        """从 key 派生足够长度的密钥流。"""
        stream = b""
        counter = 0
        while len(stream) < length:
            block = hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
            stream += block
            counter += 1
        return stream[:length]

    @staticmethod
    def encrypt(plaintext: str, key: bytes) -> str:
        """加密明文，返回 base64 编码的密文。"""
        data = plaintext.encode("utf-8")
        keystream = DataEncryptor._derive_keystream(key, len(data))
        encrypted = bytes(a ^ b for a, b in zip(data, keystream))
        return base64.b64encode(encrypted).decode("ascii")

    @staticmethod
    def decrypt(ciphertext: str, key: bytes) -> str:
        """解密 base64 编码的密文，返回明文。"""
        encrypted = base64.b64decode(ciphertext)
        keystream = DataEncryptor._derive_keystream(key, len(encrypted))
        decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
        return decrypted.decode("utf-8")


# ---------------------------------------------------------------------------
# 11.2 — PasswordHasher（存储安全 — bcrypt stub）
# ---------------------------------------------------------------------------


class PasswordHasher:
    """密码哈希与验证（基于 hashlib 的 bcrypt stub）。

    使用 SHA-256 + 随机 salt 模拟 bcrypt 行为。
    存储格式：``$stub$<hex_salt>$<hex_hash>``
    """

    SALT_LENGTH = 16

    @staticmethod
    def hash_password(password: str) -> str:
        """对密码进行哈希，返回含 salt 的哈希字符串。"""
        salt = os.urandom(PasswordHasher.SALT_LENGTH)
        digest = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
        return f"$stub${salt.hex()}${digest}"

    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """验证密码是否与哈希匹配。"""
        parts = hashed.split("$")
        # 格式: ['', 'stub', hex_salt, hex_hash]
        if len(parts) != 4 or parts[1] != "stub":
            return False
        salt = bytes.fromhex(parts[2])
        expected = parts[3]
        actual = hashlib.sha256(salt + password.encode("utf-8")).hexdigest()
        return hmac.compare_digest(actual, expected)


# ---------------------------------------------------------------------------
# 11.3 — JWTManager（访问安全 — JWT 身份认证）
# ---------------------------------------------------------------------------


class JWTManager:
    """轻量 JWT 实现（仅依赖 stdlib）。

    Token 格式：base64(header).base64(payload).base64(signature)
    签名算法：HMAC-SHA256
    """

    @staticmethod
    def _b64url_encode(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")

    @staticmethod
    def _b64url_decode(s: str) -> bytes:
        padding = 4 - len(s) % 4
        if padding != 4:
            s += "=" * padding
        return base64.urlsafe_b64decode(s)

    @staticmethod
    def create_token(
        user_id: str,
        role: str,
        secret: str,
        expires_minutes: int = 60,
    ) -> str:
        """创建 JWT token。"""
        header = {"alg": "HS256", "typ": "JWT"}
        now = time.time()
        payload = {
            "sub": user_id,
            "role": role,
            "iat": now,
            "exp": now + expires_minutes * 60,
        }
        h = JWTManager._b64url_encode(json.dumps(header).encode())
        p = JWTManager._b64url_encode(json.dumps(payload).encode())
        signing_input = f"{h}.{p}"
        sig = hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        s = JWTManager._b64url_encode(sig)
        return f"{h}.{p}.{s}"

    @staticmethod
    def verify_token(token: str, secret: str) -> dict | None:
        """验证 JWT token，成功返回 payload dict，失败返回 None。"""
        parts = token.split(".")
        if len(parts) != 3:
            return None
        h, p, s = parts
        # 验证签名
        signing_input = f"{h}.{p}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_sig = JWTManager._b64url_decode(s)
        if not hmac.compare_digest(expected_sig, actual_sig):
            return None
        # 解析 payload
        try:
            payload = json.loads(JWTManager._b64url_decode(p))
        except (json.JSONDecodeError, Exception):
            return None
        # 检查过期
        if payload.get("exp", 0) < time.time():
            return None
        return payload


# ---------------------------------------------------------------------------
# 11.3 — TOTPVerifier（访问安全 — 二次身份验证 stub）
# ---------------------------------------------------------------------------


class TOTPVerifier:
    """TOTP 二次验证（简化 stub）。

    使用 HMAC-SHA1 + 30 秒时间窗口生成 6 位数字验证码。
    """

    PERIOD = 30  # 时间窗口（秒）
    DIGITS = 6

    @staticmethod
    def generate_secret() -> str:
        """生成随机 TOTP secret（base32 编码）。"""
        return base64.b32encode(os.urandom(20)).decode("ascii")

    @staticmethod
    def _compute_code(secret: str, counter: int) -> str:
        """根据 secret 和 counter 计算 TOTP 码。"""
        key = base64.b32decode(secret)
        msg = counter.to_bytes(8, "big")
        h = hmac.new(key, msg, hashlib.sha1).digest()
        offset = h[-1] & 0x0F
        truncated = int.from_bytes(h[offset : offset + 4], "big") & 0x7FFFFFFF
        code = truncated % (10 ** TOTPVerifier.DIGITS)
        return str(code).zfill(TOTPVerifier.DIGITS)

    @staticmethod
    def get_current_code(secret: str) -> str:
        """获取当前时间窗口的 TOTP 码（测试辅助）。"""
        counter = int(time.time()) // TOTPVerifier.PERIOD
        return TOTPVerifier._compute_code(secret, counter)

    @staticmethod
    def verify_code(secret: str, code: str) -> bool:
        """验证 TOTP 码，允许前后各 1 个时间窗口的偏移。"""
        counter = int(time.time()) // TOTPVerifier.PERIOD
        for offset in (-1, 0, 1):
            expected = TOTPVerifier._compute_code(secret, counter + offset)
            if hmac.compare_digest(expected, code):
                return True
        return False


# ---------------------------------------------------------------------------
# 11.3 — RateLimiter（访问安全 — API 频率限制）
# ---------------------------------------------------------------------------


class RateLimiter:
    """内存滑动窗口频率限制器。

    对每个 key（如 IP 或 user_id）维护请求时间戳列表，
    在 window_seconds 内超过 max_requests 则拒绝。
    """

    def __init__(self) -> None:
        self._requests: dict[str, list[float]] = {}

    def check(
        self,
        key: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> bool:
        """检查是否允许请求。返回 True 表示允许，False 表示被限流。"""
        now = time.time()
        cutoff = now - window_seconds

        if key not in self._requests:
            self._requests[key] = []

        # 清理过期记录
        self._requests[key] = [
            t for t in self._requests[key] if t > cutoff
        ]

        if len(self._requests[key]) >= max_requests:
            return False

        self._requests[key].append(now)
        return True

    def reset(self, key: str) -> None:
        """重置指定 key 的请求记录。"""
        self._requests.pop(key, None)

    def get_remaining(
        self,
        key: str,
        max_requests: int = 10,
        window_seconds: int = 60,
    ) -> int:
        """获取指定 key 在当前窗口内的剩余请求次数。"""
        now = time.time()
        cutoff = now - window_seconds
        timestamps = self._requests.get(key, [])
        active = [t for t in timestamps if t > cutoff]
        return max(0, max_requests - len(active))
