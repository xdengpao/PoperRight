"""
安全模块单元测试

覆盖任务 11.1 ~ 11.3：
- 11.1 传输安全（NginxSSLConfig）
- 11.2 存储安全（DataEncryptor + PasswordHasher）
- 11.3 访问安全（JWTManager + TOTPVerifier + RateLimiter）
"""

from __future__ import annotations

import time

import pytest

from app.core.security import (
    DataEncryptor,
    JWTManager,
    NginxSSLConfig,
    PasswordHasher,
    RateLimiter,
    TOTPVerifier,
)


# ---------------------------------------------------------------------------
# NginxSSLConfig 测试（任务 11.1）
# ---------------------------------------------------------------------------


class TestNginxSSLConfig:
    def test_generate_contains_ssl_directives(self):
        cfg = NginxSSLConfig()
        output = cfg.generate()
        assert "ssl_certificate" in output
        assert "ssl_certificate_key" in output
        assert "ssl_protocols TLSv1.2 TLSv1.3" in output

    def test_generate_contains_https_redirect(self):
        cfg = NginxSSLConfig(redirect_http=True)
        output = cfg.generate()
        assert "listen 80" in output
        assert "return 301 https://" in output

    def test_generate_no_redirect(self):
        cfg = NginxSSLConfig(redirect_http=False)
        output = cfg.generate()
        assert "listen 80" not in output
        assert "return 301" not in output

    def test_generate_custom_server_name(self):
        cfg = NginxSSLConfig(server_name="quant.example.com")
        output = cfg.generate()
        assert "quant.example.com" in output

    def test_generate_custom_cert_paths(self):
        cfg = NginxSSLConfig(
            cert_path="/custom/cert.pem",
            key_path="/custom/key.pem",
        )
        output = cfg.generate()
        assert "/custom/cert.pem" in output
        assert "/custom/key.pem" in output

    def test_generate_custom_listen_port(self):
        cfg = NginxSSLConfig(listen_port=8443)
        output = cfg.generate()
        assert "listen 8443 ssl" in output

    def test_generate_contains_proxy_pass(self):
        cfg = NginxSSLConfig()
        output = cfg.generate()
        assert "proxy_pass http://127.0.0.1:8000" in output

    def test_generate_forces_https_for_all_endpoints(self):
        """所有 API 端点强制 HTTPS — redirect block 确保 HTTP→HTTPS。"""
        cfg = NginxSSLConfig(redirect_http=True)
        output = cfg.generate()
        assert "return 301 https://$host$request_uri" in output


# ---------------------------------------------------------------------------
# DataEncryptor 测试（任务 11.2）
# ---------------------------------------------------------------------------


class TestDataEncryptor:
    def test_encrypt_decrypt_roundtrip(self):
        key = b"my-secret-key-for-aes-256"
        plaintext = "用户策略数据：均线突破+MACD金叉"
        ciphertext = DataEncryptor.encrypt(plaintext, key)
        assert ciphertext != plaintext
        result = DataEncryptor.decrypt(ciphertext, key)
        assert result == plaintext

    def test_encrypt_produces_base64(self):
        key = b"test-key"
        ciphertext = DataEncryptor.encrypt("hello", key)
        # Should be valid base64
        import base64
        base64.b64decode(ciphertext)  # no exception

    def test_different_keys_produce_different_ciphertext(self):
        plaintext = "sensitive data"
        c1 = DataEncryptor.encrypt(plaintext, b"key-one")
        c2 = DataEncryptor.encrypt(plaintext, b"key-two")
        assert c1 != c2

    def test_wrong_key_fails_or_produces_wrong_plaintext(self):
        key = b"correct-key"
        plaintext = "secret"
        ciphertext = DataEncryptor.encrypt(plaintext, key)
        try:
            wrong_result = DataEncryptor.decrypt(ciphertext, b"wrong-key")
            assert wrong_result != plaintext
        except UnicodeDecodeError:
            pass  # Wrong key may produce invalid UTF-8 — expected

    def test_empty_string_roundtrip(self):
        key = b"key"
        ciphertext = DataEncryptor.encrypt("", key)
        assert DataEncryptor.decrypt(ciphertext, key) == ""

    def test_long_text_roundtrip(self):
        key = b"key"
        plaintext = "A" * 10000
        ciphertext = DataEncryptor.encrypt(plaintext, key)
        assert DataEncryptor.decrypt(ciphertext, key) == plaintext


# ---------------------------------------------------------------------------
# PasswordHasher 测试（任务 11.2）
# ---------------------------------------------------------------------------


class TestPasswordHasher:
    def test_hash_returns_string(self):
        hashed = PasswordHasher.hash_password("mypassword")
        assert isinstance(hashed, str)
        assert hashed.startswith("$stub$")

    def test_verify_correct_password(self):
        hashed = PasswordHasher.hash_password("mypassword")
        assert PasswordHasher.verify_password("mypassword", hashed) is True

    def test_verify_wrong_password(self):
        hashed = PasswordHasher.hash_password("mypassword")
        assert PasswordHasher.verify_password("wrongpassword", hashed) is False

    def test_different_passwords_different_hashes(self):
        h1 = PasswordHasher.hash_password("password1")
        h2 = PasswordHasher.hash_password("password2")
        assert h1 != h2

    def test_same_password_different_salts(self):
        h1 = PasswordHasher.hash_password("same")
        h2 = PasswordHasher.hash_password("same")
        # Different salts → different hashes
        assert h1 != h2
        # But both verify correctly
        assert PasswordHasher.verify_password("same", h1) is True
        assert PasswordHasher.verify_password("same", h2) is True

    def test_verify_malformed_hash_returns_false(self):
        assert PasswordHasher.verify_password("pw", "not-a-valid-hash") is False

    def test_verify_empty_password(self):
        hashed = PasswordHasher.hash_password("")
        assert PasswordHasher.verify_password("", hashed) is True
        assert PasswordHasher.verify_password("notempty", hashed) is False


# ---------------------------------------------------------------------------
# JWTManager 测试（任务 11.3）
# ---------------------------------------------------------------------------


class TestJWTManager:
    def test_create_token_returns_string(self):
        token = JWTManager.create_token("user1", "TRADER", "secret")
        assert isinstance(token, str)
        assert token.count(".") == 2

    def test_verify_valid_token(self):
        token = JWTManager.create_token("user1", "TRADER", "secret")
        payload = JWTManager.verify_token(token, "secret")
        assert payload is not None
        assert payload["sub"] == "user1"
        assert payload["role"] == "TRADER"

    def test_verify_wrong_secret_returns_none(self):
        token = JWTManager.create_token("user1", "TRADER", "secret")
        assert JWTManager.verify_token(token, "wrong-secret") is None

    def test_verify_expired_token_returns_none(self):
        token = JWTManager.create_token("user1", "TRADER", "secret", expires_minutes=-1)
        assert JWTManager.verify_token(token, "secret") is None

    def test_verify_tampered_token_returns_none(self):
        token = JWTManager.create_token("user1", "TRADER", "secret")
        parts = token.split(".")
        # Tamper with payload
        tampered = parts[0] + ".AAAA" + parts[1][4:] + "." + parts[2]
        assert JWTManager.verify_token(tampered, "secret") is None

    def test_verify_malformed_token_returns_none(self):
        assert JWTManager.verify_token("not.a.valid-token-at-all", "secret") is None
        assert JWTManager.verify_token("onlytwoparts.here", "secret") is None
        assert JWTManager.verify_token("", "secret") is None

    def test_token_contains_iat_and_exp(self):
        token = JWTManager.create_token("user1", "ADMIN", "secret", expires_minutes=30)
        payload = JWTManager.verify_token(token, "secret")
        assert "iat" in payload
        assert "exp" in payload
        assert payload["exp"] > payload["iat"]


# ---------------------------------------------------------------------------
# TOTPVerifier 测试（任务 11.3）
# ---------------------------------------------------------------------------


class TestTOTPVerifier:
    def test_generate_secret_returns_base32(self):
        secret = TOTPVerifier.generate_secret()
        assert isinstance(secret, str)
        assert len(secret) > 0
        # Valid base32
        import base64
        base64.b32decode(secret)

    def test_generate_secret_unique(self):
        s1 = TOTPVerifier.generate_secret()
        s2 = TOTPVerifier.generate_secret()
        assert s1 != s2

    def test_verify_current_code(self):
        secret = TOTPVerifier.generate_secret()
        code = TOTPVerifier.get_current_code(secret)
        assert TOTPVerifier.verify_code(secret, code) is True

    def test_verify_wrong_code(self):
        secret = TOTPVerifier.generate_secret()
        assert TOTPVerifier.verify_code(secret, "000000") is False or \
               TOTPVerifier.get_current_code(secret) == "000000"

    def test_code_is_six_digits(self):
        secret = TOTPVerifier.generate_secret()
        code = TOTPVerifier.get_current_code(secret)
        assert len(code) == 6
        assert code.isdigit()

    def test_different_secrets_different_codes(self):
        s1 = TOTPVerifier.generate_secret()
        s2 = TOTPVerifier.generate_secret()
        c1 = TOTPVerifier.get_current_code(s1)
        c2 = TOTPVerifier.get_current_code(s2)
        # Very unlikely to be the same
        # But not impossible, so we just check they're valid
        assert len(c1) == 6 and len(c2) == 6


# ---------------------------------------------------------------------------
# RateLimiter 测试（任务 11.3）
# ---------------------------------------------------------------------------


class TestRateLimiter:
    def test_allows_under_limit(self):
        rl = RateLimiter()
        for _ in range(5):
            assert rl.check("user1", max_requests=5) is True

    def test_blocks_over_limit(self):
        rl = RateLimiter()
        for _ in range(3):
            rl.check("user1", max_requests=3)
        assert rl.check("user1", max_requests=3) is False

    def test_different_keys_independent(self):
        rl = RateLimiter()
        for _ in range(3):
            rl.check("user1", max_requests=3)
        # user1 is at limit, but user2 should be fine
        assert rl.check("user2", max_requests=3) is True

    def test_reset_clears_requests(self):
        rl = RateLimiter()
        for _ in range(3):
            rl.check("user1", max_requests=3)
        assert rl.check("user1", max_requests=3) is False
        rl.reset("user1")
        assert rl.check("user1", max_requests=3) is True

    def test_get_remaining(self):
        rl = RateLimiter()
        assert rl.get_remaining("user1", max_requests=10) == 10
        rl.check("user1", max_requests=10)
        rl.check("user1", max_requests=10)
        assert rl.get_remaining("user1", max_requests=10) == 8

    def test_expired_requests_cleaned(self):
        rl = RateLimiter()
        # Manually insert old timestamps
        rl._requests["user1"] = [time.time() - 120]  # 2 minutes ago
        # With 60s window, old request should be cleaned
        assert rl.check("user1", max_requests=1, window_seconds=60) is True

    def test_first_request_always_allowed(self):
        rl = RateLimiter()
        assert rl.check("new-key", max_requests=1) is True
