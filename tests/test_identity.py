"""Tests for the multi-identity registry: parsing, validation, lookup, config wiring.

Covers the acceptance criteria for the multi-identity feature:

- registry parsing from env vars and from file, file wins over env
- startup abort on duplicate mcp_token, too-short token, mcp_token == snipeit_token
- OAuth vars and identities at the same time -> ConfigError
- MULTI_IDENTITY + stdio -> ConfigError
- fallback: only SNIPEIT_TOKEN set -> API_KEY, behaviour as before

The HTTP-layer and concurrency tests live in :mod:`tests.test_identity_http`.
"""

from __future__ import annotations

import json
import os

import pytest

from snipeit_mcp.config import (
    AuthMode,
    ConfigError,
    SnipeITAuthConfig,
    TransportConfig,
    TransportType,
)
from snipeit_mcp.identity import (
    Identity,
    IdentityRegistry,
    load_identity_registry,
)

TOKEN_A = "a" * 40  # 40 chars, well above the 32-char minimum
TOKEN_B = "b" * 40
TOKEN_C = "c" * 40
SNIPEIT_TOKEN_A = "snipeit-pat-alice-00000000000000000000"
SNIPEIT_TOKEN_B = "snipeit-pat-bob-0000000000000000000000"
SNIPEIT_TOKEN_C = "snipeit-pat-carol-00000000000000000000"


def identity_env(key: str, mcp_token: str, snipeit_token: str, **extra) -> dict[str, str]:
    env = {
        f"SNIPEIT_IDENTITY_{key}_MCP_TOKEN": mcp_token,
        f"SNIPEIT_IDENTITY_{key}_SNIPEIT_TOKEN": snipeit_token,
    }
    env.update(extra)
    return env


# ----- Registry parsing: env vars -------------------------------------------


class TestEnvParsing:
    def test_parses_two_identities(self):
        env = {
            **identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A),
            **identity_env("BOB", TOKEN_B, SNIPEIT_TOKEN_B),
        }
        registry = load_identity_registry(env)
        assert registry is not None
        assert len(registry) == 2
        assert registry.keys == ["ALICE", "BOB"]
        assert registry.identities[0].snipeit_token == SNIPEIT_TOKEN_A
        assert registry.identities[1].snipeit_token == SNIPEIT_TOKEN_B

    def test_optional_fields(self):
        env = identity_env(
            "ALICE",
            TOKEN_A,
            SNIPEIT_TOKEN_A,
            **{
                "SNIPEIT_IDENTITY_ALICE_DISPLAY_NAME": "Alice Anderson",
                "SNIPEIT_IDENTITY_ALICE_ALLOWED_TOOLS": "manage_assets, system_info",
                "SNIPEIT_IDENTITY_ALICE_READ_ONLY": "true",
            },
        )
        registry = load_identity_registry(env)
        identity = registry.identities[0]
        assert identity.display_name == "Alice Anderson"
        assert identity.allowed_tools == frozenset({"manage_assets", "system_info"})
        assert identity.read_only is True
        assert identity.log_name == "Alice Anderson"

    def test_read_only_false_and_defaults(self):
        env = identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A,
                           **{"SNIPEIT_IDENTITY_ALICE_READ_ONLY": "no"})
        identity = load_identity_registry(env).identities[0]
        assert identity.read_only is False
        assert identity.allowed_tools is None
        assert identity.display_name is None
        assert identity.log_name == "ALICE"

    def test_invalid_read_only_value_fails(self):
        env = identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A,
                           **{"SNIPEIT_IDENTITY_ALICE_READ_ONLY": "maybe"})
        with pytest.raises(ConfigError, match="READ_ONLY must be a boolean"):
            load_identity_registry(env)

    def test_key_with_underscores(self):
        env = identity_env("TEAM_A_1", TOKEN_A, SNIPEIT_TOKEN_A)
        registry = load_identity_registry(env)
        assert registry.keys == ["TEAM_A_1"]

    def test_no_identities_returns_none(self):
        assert load_identity_registry({"SNIPEIT_URL": "https://x"}) is None

    def test_missing_snipeit_token_fails(self):
        env = {f"SNIPEIT_IDENTITY_ALICE_MCP_TOKEN": TOKEN_A}
        with pytest.raises(ConfigError, match="snipeit_token is required"):
            load_identity_registry(env)

    def test_missing_mcp_token_fails(self):
        env = {f"SNIPEIT_IDENTITY_ALICE_SNIPEIT_TOKEN": SNIPEIT_TOKEN_A}
        with pytest.raises(ConfigError, match="mcp_token is required"):
            load_identity_registry(env)


# ----- Registry parsing: file ------------------------------------------------


class TestFileParsing:
    def test_parses_file(self, tmp_path):
        path = tmp_path / "identities.json"
        path.write_text(json.dumps([
            {
                "key": "ALICE",
                "mcp_token": TOKEN_A,
                "snipeit_token": SNIPEIT_TOKEN_A,
                "display_name": "Alice Anderson",
                "allowed_tools": ["manage_assets"],
                "read_only": False,
            },
            {"key": "BOB", "mcp_token": TOKEN_B, "snipeit_token": SNIPEIT_TOKEN_B},
        ]))
        registry = load_identity_registry({"SNIPEIT_IDENTITIES_FILE": str(path)})
        assert registry is not None
        assert registry.keys == ["ALICE", "BOB"]
        assert registry.identities[0].allowed_tools == frozenset({"manage_assets"})
        assert registry.identities[0].read_only is False
        assert registry.identities[1].read_only is False

    def test_file_wins_over_env(self, tmp_path):
        path = tmp_path / "identities.json"
        path.write_text(json.dumps([
            {"key": "ALICE", "mcp_token": TOKEN_A, "snipeit_token": SNIPEIT_TOKEN_A},
        ]))
        env = {
            "SNIPEIT_IDENTITIES_FILE": str(path),
            **identity_env("BOB", TOKEN_B, SNIPEIT_TOKEN_B),
        }
        registry = load_identity_registry(env)
        # Only the file's identity is present — env vars were ignored.
        assert registry.keys == ["ALICE"]

    def test_file_missing_fails(self):
        with pytest.raises(ConfigError, match="unreadable file"):
            load_identity_registry({"SNIPEIT_IDENTITIES_FILE": "/nonexistent/identities.json"})

    def test_file_invalid_json_fails(self, tmp_path):
        path = tmp_path / "identities.json"
        path.write_text("{not json")
        with pytest.raises(ConfigError, match="not valid JSON"):
            load_identity_registry({"SNIPEIT_IDENTITIES_FILE": str(path)})

    def test_file_not_a_list_fails(self, tmp_path):
        path = tmp_path / "identities.json"
        path.write_text(json.dumps({"key": "ALICE"}))
        with pytest.raises(ConfigError, match="JSON list"):
            load_identity_registry({"SNIPEIT_IDENTITIES_FILE": str(path)})

    def test_file_bad_key_fails(self, tmp_path):
        path = tmp_path / "identities.json"
        path.write_text(json.dumps([
            {"key": "lower-case", "mcp_token": TOKEN_A, "snipeit_token": SNIPEIT_TOKEN_A},
        ]))
        with pytest.raises(ConfigError, match="invalid 'key'"):
            load_identity_registry({"SNIPEIT_IDENTITIES_FILE": str(path)})

    def test_file_allowed_tools_as_csv_string(self, tmp_path):
        path = tmp_path / "identities.json"
        path.write_text(json.dumps([
            {"key": "ALICE", "mcp_token": TOKEN_A, "snipeit_token": SNIPEIT_TOKEN_A,
             "allowed_tools": "manage_assets,system_info"},
        ]))
        registry = load_identity_registry({"SNIPEIT_IDENTITIES_FILE": str(path)})
        assert registry.identities[0].allowed_tools == frozenset({"manage_assets", "system_info"})


# ----- Validation -------------------------------------------------------------


class TestValidation:
    def test_duplicate_mcp_token_fails(self):
        env = {
            **identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A),
            **identity_env("BOB", TOKEN_A, SNIPEIT_TOKEN_B),
        }
        with pytest.raises(ConfigError, match="shared by identities 'ALICE' and 'BOB'"):
            load_identity_registry(env)

    def test_short_mcp_token_fails(self):
        env = identity_env("ALICE", "a" * 31, SNIPEIT_TOKEN_A)
        with pytest.raises(ConfigError, match="at least 32 characters"):
            load_identity_registry(env)

    def test_mcp_token_equal_to_snipeit_token_fails(self):
        token = "d" * 40
        env = identity_env("ALICE", token, token)
        with pytest.raises(ConfigError, match="must differ"):
            load_identity_registry(env)

    def test_error_messages_never_leak_tokens(self):
        env = identity_env("ALICE", "a" * 31, SNIPEIT_TOKEN_A)
        with pytest.raises(ConfigError) as excinfo:
            load_identity_registry(env)
        assert "a" * 31 not in str(excinfo.value)
        assert SNIPEIT_TOKEN_A not in str(excinfo.value)


# ----- Lookup -----------------------------------------------------------------


class TestLookup:
    @pytest.fixture
    def registry(self) -> IdentityRegistry:
        return IdentityRegistry(
            identities=(
                Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A),
                Identity(key="BOB", mcp_token=TOKEN_B, snipeit_token=SNIPEIT_TOKEN_B),
            )
        )

    def test_finds_matching_identity(self, registry):
        assert registry.lookup(TOKEN_B).key == "BOB"
        assert registry.lookup(TOKEN_A).key == "ALICE"

    def test_unknown_token_returns_none(self, registry):
        assert registry.lookup("unknown-token") is None

    def test_none_and_empty_return_none(self, registry):
        assert registry.lookup(None) is None
        assert registry.lookup("") is None

    def test_prefix_of_token_does_not_match(self, registry):
        assert registry.lookup(TOKEN_A[:20]) is None


# ----- Config wiring ----------------------------------------------------------


class TestAuthModeResolution:
    def _clean(self):
        keys = [
            "SNIPEIT_URL",
            "SNIPEIT_TOKEN",
            "SNIPEIT_OAUTH_CLIENT_ID",
            "SNIPEIT_OAUTH_CLIENT_SECRET",
            "SNIPEIT_MCP_BASE_URL",
            "SNIPEIT_IDENTITIES_FILE",
        ]
        keys += [k for k in os.environ if k.startswith("SNIPEIT_IDENTITY_")]
        for key in keys:
            os.environ.pop(key, None)

    def test_multi_identity_mode_when_identities_configured(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        os.environ.update(identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A))
        cfg = SnipeITAuthConfig.from_env()
        assert cfg.mode == AuthMode.MULTI_IDENTITY

    def test_multi_identity_takes_precedence_over_api_key(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        os.environ["SNIPEIT_TOKEN"] = "static-token"
        os.environ.update(identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A))
        cfg = SnipeITAuthConfig.from_env()
        assert cfg.mode == AuthMode.MULTI_IDENTITY

    def test_oauth_plus_identities_conflicts(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        os.environ["SNIPEIT_OAUTH_CLIENT_ID"] = "cid"
        os.environ["SNIPEIT_OAUTH_CLIENT_SECRET"] = "csecret"  # noqa: S105
        os.environ["SNIPEIT_MCP_BASE_URL"] = "https://mcp.example.com"
        os.environ.update(identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A))
        with pytest.raises(ConfigError, match="mutually exclusive"):
            SnipeITAuthConfig.from_env()

    def test_multi_identity_rejects_stdio_transport(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        os.environ.update(identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A))
        cfg = SnipeITAuthConfig.from_env()
        transport = TransportConfig(transport=TransportType.STDIO)
        with pytest.raises(ConfigError, match="Multi-identity mode requires HTTP transport"):
            cfg.validate_with_transport(transport)

    def test_multi_identity_accepts_http_transport(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        os.environ.update(identity_env("ALICE", TOKEN_A, SNIPEIT_TOKEN_A))
        cfg = SnipeITAuthConfig.from_env()
        transport = TransportConfig(
            transport=TransportType.HTTP, host="127.0.0.1", port=8000
        )
        cfg.validate_with_transport(transport)  # must not raise

    def test_no_credentials_error_mentions_multi_identity(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        with pytest.raises(ConfigError, match="No Snipe-IT credentials"):
            SnipeITAuthConfig.from_env()
        # The error message should now mention all three options.
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        with pytest.raises(ConfigError, match="SNIPEIT_IDENTITY_"):
            SnipeITAuthConfig.from_env()

    def test_fallback_api_key_when_only_token(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        os.environ["SNIPEIT_TOKEN"] = "static-token"
        cfg = SnipeITAuthConfig.from_env()
        assert cfg.mode == AuthMode.API_KEY
        assert cfg.token == "static-token"

    def test_oauth_still_resolved_without_identities(self):
        self._clean()
        os.environ["SNIPEIT_URL"] = "https://snipeit.example.com"
        os.environ["SNIPEIT_OAUTH_CLIENT_ID"] = "cid"
        os.environ["SNIPEIT_OAUTH_CLIENT_SECRET"] = "csecret"  # noqa: S105
        os.environ["SNIPEIT_MCP_BASE_URL"] = "https://mcp.example.com"
        cfg = SnipeITAuthConfig.from_env()
        assert cfg.mode == AuthMode.OAUTH


class TestIdentityContextVar:
    def test_default_is_none(self):
        from snipeit_mcp.identity import current_identity

        assert current_identity.get() is None

    def test_set_and_reset(self):
        from snipeit_mcp.identity import Identity, current_identity

        identity = Identity(key="ALICE", mcp_token=TOKEN_A, snipeit_token=SNIPEIT_TOKEN_A)
        token = current_identity.set(identity)
        try:
            assert current_identity.get() is identity
        finally:
            current_identity.reset(token)
        assert current_identity.get() is None