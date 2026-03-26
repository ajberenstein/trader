"""
Simple OAuth 2.0 Authorization Server for the Trader MCP server.

Validates a single static token (MCP_ACCESS_TOKEN from .env).
Implements the authorization code + PKCE flow that Claude.ai expects.
"""

import hashlib
import secrets
import time
import base64
import urllib.parse
from dataclasses import dataclass

from mcp.server.auth.provider import (
    OAuthAuthorizationServerProvider,
    AccessToken,
    AuthorizationCode,
    AuthorizationParams,
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.shared.auth import OAuthClientInformationFull, OAuthToken


@dataclass
class StoredCode:
    code: str
    client_id: str
    redirect_uri: str
    code_challenge: str
    code_challenge_method: str
    expires_at: float


LOGIN_HTML = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Trader MCP — Access</title>
  <style>
    body {{ font-family: system-ui, sans-serif; max-width: 420px; margin: 80px auto; padding: 0 20px; }}
    h2 {{ margin-bottom: 4px; }}
    p {{ color: #666; font-size: 14px; margin-bottom: 24px; }}
    input[type=password] {{ width: 100%; padding: 10px; font-size: 15px; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; }}
    button {{ margin-top: 12px; width: 100%; padding: 10px; font-size: 15px; background: #1a1a1a; color: white; border: none; border-radius: 6px; cursor: pointer; }}
    button:hover {{ background: #333; }}
    .error {{ color: #c00; font-size: 14px; margin-top: 10px; }}
  </style>
</head>
<body>
  <h2>Trader MCP</h2>
  <p>Enter your access token to connect.</p>
  <form method="post">
    <input type="hidden" name="client_id" value="{client_id}">
    <input type="hidden" name="redirect_uri" value="{redirect_uri}">
    <input type="hidden" name="state" value="{state}">
    <input type="hidden" name="code_challenge" value="{code_challenge}">
    <input type="hidden" name="code_challenge_method" value="{code_challenge_method}">
    <input type="password" name="token" placeholder="Access token" autofocus>
    {error}
    <button type="submit">Connect</button>
  </form>
</body>
</html>"""


class SimpleTokenOAuthProvider(OAuthAuthorizationServerProvider):
    """
    OAuth AS backed by a single static token.
    Clients authenticate by entering the token in a login form.
    """

    def __init__(self, valid_token: str, server_url: str):
        self.valid_token = valid_token
        self.server_url = server_url.rstrip("/")
        self._clients: dict[str, OAuthClientInformationFull] = {}
        self._codes: dict[str, StoredCode] = {}
        self._tokens: dict[str, AccessToken] = {}

    # --- Client registration (dynamic — accept any client) ---

    async def get_client(self, client_id: str) -> OAuthClientInformationFull | None:
        return self._clients.get(client_id)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        self._clients[client_info.client_id] = client_info

    # --- Authorization code flow ---

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        """Redirect to the login form, carrying OAuth params as query string."""
        qs = urllib.parse.urlencode({
            "client_id": client.client_id,
            "redirect_uri": str(params.redirect_uri),
            "state": params.state or "",
            "code_challenge": params.code_challenge or "",
            "code_challenge_method": "S256",
        })
        return f"{self.server_url}/login?{qs}"

    def _create_code(self, client_id: str, redirect_uri: str,
                     code_challenge: str, code_challenge_method: str) -> str:
        code = secrets.token_urlsafe(32)
        self._codes[code] = StoredCode(
            code=code,
            client_id=client_id,
            redirect_uri=redirect_uri,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            expires_at=time.time() + 600,  # 10 min
        )
        return code

    async def load_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: str
    ) -> AuthorizationCode | None:
        stored = self._codes.get(authorization_code)
        if not stored or stored.expires_at < time.time():
            return None
        from pydantic import AnyUrl
        return AuthorizationCode(
            code=stored.code,
            scopes=[],
            expires_at=stored.expires_at,
            client_id=stored.client_id,
            code_challenge=stored.code_challenge,
            redirect_uri=AnyUrl(stored.redirect_uri),
            redirect_uri_provided_explicitly=True,
        )

    async def exchange_authorization_code(
        self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode
    ) -> OAuthToken:
        del self._codes[authorization_code.code]
        token = secrets.token_urlsafe(32)
        self._tokens[token] = AccessToken(
            token=token,
            client_id=client.client_id,
            scopes=[],
            expires_at=int(time.time()) + 86400 * 30,  # 30 days
        )
        return OAuthToken(
            access_token=token,
            token_type="Bearer",
            expires_in=86400 * 30,
        )

    # --- Token validation ---

    async def load_access_token(self, token: str) -> AccessToken | None:
        return self._tokens.get(token)

    async def revoke_token(self, token) -> None:
        t = getattr(token, "token", None)
        if t:
            self._tokens.pop(t, None)

    # --- Refresh tokens (not supported) ---

    async def load_refresh_token(self, client, refresh_token: str):
        return None

    async def exchange_refresh_token(self, client, refresh_token, scopes) -> OAuthToken:
        raise NotImplementedError("Refresh tokens not supported")

    # --- Login form helpers ---

    def login_form(self, params: dict, error: str = "") -> str:
        error_html = f'<p class="error">{error}</p>' if error else ""
        return LOGIN_HTML.format(
            client_id=params.get("client_id", ""),
            redirect_uri=params.get("redirect_uri", ""),
            state=params.get("state", ""),
            code_challenge=params.get("code_challenge", ""),
            code_challenge_method=params.get("code_challenge_method", "S256"),
            error=error_html,
        )

    def validate_and_create_code(self, form: dict) -> tuple[str | None, str | None]:
        """Returns (redirect_url, error_message)."""
        token = form.get("token", "")
        if token != self.valid_token:
            return None, "Invalid token. Try again."

        code = self._create_code(
            client_id=form.get("client_id", ""),
            redirect_uri=form.get("redirect_uri", ""),
            code_challenge=form.get("code_challenge", ""),
            code_challenge_method=form.get("code_challenge_method", "S256"),
        )
        redirect_uri = form.get("redirect_uri", "")
        state = form.get("state", "")
        sep = "&" if "?" in redirect_uri else "?"
        redirect = f"{redirect_uri}{sep}code={code}"
        if state:
            redirect += f"&state={state}"
        return redirect, None


def make_auth_settings(server_url: str) -> AuthSettings:
    return AuthSettings(
        issuer_url=server_url,
        resource_server_url=f"{server_url}/mcp",
        client_registration_options=ClientRegistrationOptions(enabled=True),
    )
