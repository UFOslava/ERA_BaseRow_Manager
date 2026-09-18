import html
import os
import json
import logging
import secrets
import asyncio
import socket
import ipaddress
import time
import requests
import urllib.parse
from typing import Optional, Dict, Any, List, Tuple, Iterable
from datetime import datetime, timezone, timedelta
import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from mcp.server.auth.provider import (
    OAuthAuthorizationServerProvider,
    OAuthClientInformationFull,
    AuthorizationParams,
    OAuthToken,
    TokenError,
    AuthorizeError,
    AuthorizationCode,
    RefreshToken,
    AccessToken,
    RegistrationError,
)
from pydantic import AnyHttpUrl
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.auth.routes import create_auth_routes
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

def is_safe_address(addr: str) -> bool:
    """Return False if addr is loopback, private, link-local, reserved, multicast, or unspecified."""
    try:
        ip = ipaddress.ip_address(addr)
    except ValueError:
        return False
    if getattr(ip, "ipv4_mapped", None):
        mapped = ip.ipv4_mapped
        if (
            mapped.is_loopback
            or mapped.is_private
            or mapped.is_link_local
            or mapped.is_reserved
            or mapped.is_multicast
            or mapped.is_unspecified
        ):
            return False
    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        return False
    return True

def is_cimd_client_id(client_id: str) -> bool:
    """Detect CIMD client ID: parses as URL, scheme is https, pathname is not '/'."""
    try:
        parsed = urllib.parse.urlparse(client_id)
        if parsed.scheme != "https":
            return False
        if not parsed.netloc:
            return False
        pathname = parsed.path or "/"
        return pathname != "/"
    except Exception:
        return False

class CIMDHelper:
    """Helper for fetching, validating, and caching Client ID Metadata Documents (CIMD)."""

    def __init__(self, allowed_hosts: Optional[Iterable[str]] = None):
        self._cache: Dict[str, Tuple[OAuthClientInformationFull, float]] = {}
        self.last_error: Optional[str] = None
        if allowed_hosts is not None:
            self.allowed_hosts = {h.strip().lower() for h in allowed_hosts if h.strip()}
        else:
            env_val = os.getenv("OAUTH_CIMD_ALLOWED_HOSTS")
            if env_val is not None:
                if not env_val.strip():
                    self.allowed_hosts = set()
                else:
                    self.allowed_hosts = {h.strip().lower() for h in env_val.split(",") if h.strip()}
            else:
                # Default when helper is constructed directly without env var: accountlinking.google.com
                self.allowed_hosts = {"accountlinking.google.com"}

    def is_cimd_id(self, client_id: str) -> bool:
        return is_cimd_client_id(client_id)

    def validate_url(self, client_id: str) -> Tuple[bool, str]:
        """Validate URL scheme, hostname against allowlist, and resolved IP addresses against SSRF."""
        try:
            parsed = urllib.parse.urlparse(client_id)
        except Exception as e:
            self.last_error = f"URL parse failed: {e}"
            return False, self.last_error

        # Scheme check: HTTPS only
        if parsed.scheme != "https":
            self.last_error = f"not HTTPS (scheme is '{parsed.scheme}')"
            return False, self.last_error

        pathname = parsed.path or "/"
        if pathname == "/":
            self.last_error = "invalid CIMD URL: pathname must not be empty or '/'"
            return False, self.last_error

        hostname = (parsed.hostname or "").lower()
        if not hostname or hostname not in self.allowed_hosts:
            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_loopback or ip.is_private:
                    self.last_error = f"not allowlisted / loopback ({hostname})"
                    return False, self.last_error
            except ValueError:
                pass
            self.last_error = f"host not allowlisted ({hostname})"
            return False, self.last_error

        # Resolve with socket.getaddrinfo and reject private targets
        port = parsed.port or 443
        try:
            addrinfo = socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM)
        except Exception as e:
            self.last_error = f"DNS resolution failed for {hostname}: {e}"
            return False, self.last_error

        if not addrinfo:
            self.last_error = f"no DNS records found for {hostname}"
            return False, self.last_error

        for entry in addrinfo:
            sockaddr = entry[4]
            ip_str = sockaddr[0]
            if not is_safe_address(ip_str):
                self.last_error = f"resolved to private IP ({ip_str})"
                return False, self.last_error

        self.last_error = None
        return True, "OK"

    def fetch_and_validate(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        """Fetch, validate and return OAuthClientInformationFull, or None on any failure."""
        try:
            # Check cache first (cached documents are valid for 300 seconds)
            cached = self._cache.get(client_id)
            if cached:
                client_obj, expiry = cached
                if time.time() < expiry:
                    return client_obj
                else:
                    self._cache.pop(client_id, None)

            # SSRF validation before any network call
            valid, reason = self.validate_url(client_id)
            if not valid:
                return None

            # Bounded network call via requests
            try:
                resp = requests.get(
                    client_id,
                    allow_redirects=False,
                    timeout=5.0,
                    headers={"Accept": "application/json", "User-Agent": "ERA-OAuth-Server/1.0"},
                    stream=True,
                )
            except Exception as e:
                self.last_error = f"HTTP request failed: {e}"
                return None

            # No redirects: treat any non-200 (including 3xx) as failure
            if resp.is_redirect or (300 <= resp.status_code < 400):
                self.last_error = f"redirects not permitted (HTTP {resp.status_code})"
                return None

            if resp.status_code != 200:
                self.last_error = f"HTTP error {resp.status_code}"
                return None

            # Bounded body: max 65536 bytes
            cl_header = resp.headers.get("Content-Length")
            if cl_header:
                try:
                    if int(cl_header) > 65536:
                        self.last_error = "Content-Length exceeds 65536 bytes"
                        return None
                except ValueError:
                    pass

            body = bytearray()
            for chunk in resp.iter_content(chunk_size=4096):
                body.extend(chunk)
                if len(body) > 65536:
                    self.last_error = "body size exceeds 65536 bytes"
                    return None

            # JSON parse only (never log body, metadata, or secrets)
            try:
                doc = json.loads(body.decode("utf-8"))
            except Exception as e:
                self.last_error = f"JSON parse error: {e}"
                return None

            if not isinstance(doc, dict):
                self.last_error = "metadata document must be a JSON object"
                return None

            # Required fields: client_id, client_name, redirect_uris
            if "client_id" not in doc or "client_name" not in doc or "redirect_uris" not in doc:
                self.last_error = "missing required fields (client_id, client_name, redirect_uris)"
                return None

            # client_id must equal request URL exactly
            if doc["client_id"] != client_id:
                self.last_error = "client_id in document does not match request URL"
                return None

            client_name = doc["client_name"]
            if not isinstance(client_name, str) or not client_name.strip():
                self.last_error = "client_name must be a non-empty string"
                return None

            # redirect_uris: non-empty list of strings, each parsing as http/https URL
            redirect_uris = doc["redirect_uris"]
            if not isinstance(redirect_uris, list) or len(redirect_uris) == 0:
                self.last_error = "redirect_uris must be a non-empty list"
                return None

            for u in redirect_uris:
                if not isinstance(u, str) or not u.strip():
                    self.last_error = "redirect_uri must be a non-empty string"
                    return None
                try:
                    parsed_uri = urllib.parse.urlparse(u)
                    if parsed_uri.scheme not in ("http", "https") or not parsed_uri.netloc:
                        self.last_error = f"redirect_uri has invalid scheme or missing host: {u}"
                        return None
                except Exception as e:
                    self.last_error = f"invalid redirect_uri: {e}"
                    return None

            # Build client
            token_endpoint_auth_method = doc.get("token_endpoint_auth_method", "none")
            grant_types = doc.get("grant_types", ["authorization_code", "refresh_token"])
            response_types = doc.get("response_types", ["code"])
            scope = doc.get("scope", "default")

            client = OAuthClientInformationFull(
                client_id=client_id,
                client_secret=None,
                token_endpoint_auth_method=token_endpoint_auth_method,
                grant_types=grant_types,
                response_types=response_types,
                redirect_uris=redirect_uris,
                client_name=client_name,
                scope=scope,
            )

            # Cache validated documents for 300 seconds
            self._cache[client_id] = (client, time.time() + 300.0)
            self.last_error = None
            return client

        except Exception as e:
            self.last_error = f"unexpected error: {e}"
            return None

    # Convenient alias
    get_client = fetch_and_validate

def fetch_and_validate_cimd_client(client_id: str, allowed_hosts: Optional[Iterable[str]] = None) -> Optional[OAuthClientInformationFull]:
    """Standalone helper function to fetch and validate a CIMD client."""
    helper = CIMDHelper(allowed_hosts=allowed_hosts)
    return helper.fetch_and_validate(client_id)

class ERATokenProvider(OAuthAuthorizationServerProvider[str, str, str]):
    def __init__(self, private_key: rsa.RSAPrivateKey, issuer_url: str, resource_url: str,
                 cimd_allowed_hosts: Optional[Iterable[str]] = None):
        self.private_key = private_key
        self.public_key = self.private_key.public_key()
        self.issuer_url = issuer_url
        self.resource_url = resource_url
        
        self.auth_codes = {}
        self.client_cache = {}

        # Dynamic client registration (DCR) store. Spark self-registers a client_id here.
        # Gate: register_client refuses any client whose redirect_uris are not ALL in the
        # configured approved set, so POST /register cannot onboard arbitrary clients.
        self.clients_file = os.getenv("OAUTH_CLIENTS_FILE", "/app/data/oauth_clients.json")
        self.registered_clients: Dict[str, dict] = {}
        if os.path.exists(self.clients_file):
            try:
                with open(self.clients_file) as f:
                    self.registered_clients = json.load(f)
            except Exception as e:
                logger.error("Failed to load registered clients: %s", e)
                self.registered_clients = {}
        
        # Static Client settings
        self.static_client_id = os.getenv("OAUTH_CLIENT_ID")
        self.static_client_secret = os.getenv("OAUTH_CLIENT_SECRET")
        uris_env = os.getenv("OAUTH_CLIENT_REDIRECT_URIS", "")
        # Store redirect URIs as plain strings: OAuthClientInformationFull coerces them to AnyUrl,
        # which matches how AuthorizationRequest parses the incoming redirect_uri. Wrapping in
        # AnyHttpUrl here caused a type mismatch (AnyUrl != AnyHttpUrl in Pydantic) that rejected
        # Spark's otherwise-valid redirect URI at /authorize.
        self.static_client_redirect_uris = [u.strip() for u in uris_env.split(",")] if uris_env else []
        self.static_client_auth_method = os.getenv("OAUTH_CLIENT_AUTH_METHOD", "client_secret_basic").strip()
        if self.static_client_auth_method not in ("client_secret_basic", "client_secret_post"):
            raise ValueError("OAUTH_CLIENT_AUTH_METHOD must be client_secret_basic or client_secret_post")

        # CIMD settings
        if cimd_allowed_hosts is not None:
            self.cimd_allowed_hosts = {h.strip().lower() for h in cimd_allowed_hosts if h.strip()}
        else:
            cimd_env = os.getenv("OAUTH_CIMD_ALLOWED_HOSTS")
            if not cimd_env or not cimd_env.strip():
                # If env var is empty or unset -> CIMD disabled entirely
                self.cimd_allowed_hosts = set()
            else:
                self.cimd_allowed_hosts = {h.strip().lower() for h in cimd_env.split(",") if h.strip()}
        self.cimd_helper = CIMDHelper(allowed_hosts=self.cimd_allowed_hosts)

        # Refresh Tokens Store
        self.tokens_file = os.getenv("OAUTH_REFRESH_TOKENS_FILE", "/app/data/oauth_refresh_tokens.json")
        self.refresh_tokens: Dict[str, dict] = {}
        if os.path.exists(self.tokens_file):
            with open(self.tokens_file) as f:
                self.refresh_tokens = json.load(f)

    def _save_refresh_tokens(self):
        os.makedirs(os.path.dirname(self.tokens_file), exist_ok=True)
        tmp = self.tokens_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.refresh_tokens, f)
        os.replace(tmp, self.tokens_file)

    def _generate_jwt(self, aud: str, client_id: str, scope: str, expires_in: int = 3600) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "iss": self.issuer_url,
            "aud": aud,
            "sub": client_id,
            "scope": scope,
            "iat": now.timestamp(),
            "exp": (now + timedelta(seconds=expires_in)).timestamp(),
            "jti": f"jwt-{now.timestamp()}"
        }
        kid = "era-key-1"
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": kid})

    def _save_clients(self):
        os.makedirs(os.path.dirname(self.clients_file), exist_ok=True)
        tmp = self.clients_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self.registered_clients, f)
        os.replace(tmp, self.clients_file)

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        """Dynamic client registration (RFC 7591), gated on the approved redirect_uri set.

        Spark self-registers, so this must be reachable. The gate is deliberately fail-closed:
        every redirect_uri the client asks for must already be in OAUTH_CLIENT_REDIRECT_URIS
        (the trusted Spark callback). An empty allowlist, or a client that asks for a redirect_uri
        outside it, is refused, so an attacker cannot register a client that redirects to itself.
        """
        approved = {u.strip() for u in self.static_client_redirect_uris if u.strip()}
        if not approved:
            raise RegistrationError(
                error="invalid_client_metadata",
                error_description="dynamic client registration is not configured",
            )
        requested = [str(u) for u in client_info.redirect_uris]
        if not requested or not all(u in approved for u in requested):
            raise RegistrationError(
                error="invalid_client_metadata",
                error_description="redirect_uri is not an approved client",
            )
        self.registered_clients[client_info.client_id] = client_info.model_dump(mode="json")
        self._save_clients()
        logger.info("Registered dynamic client %s", client_info.client_id)

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        # Static confidential client (configured via .env) — rejects anything else.
        if self.static_client_id and client_id == self.static_client_id:
            return OAuthClientInformationFull(
                client_id=self.static_client_id,
                client_secret=self.static_client_secret,
                # MCP SDK reads client_id from the form body first and then branches only on
                # the registered method, so this value must match how the client authenticates.
                token_endpoint_auth_method=self.static_client_auth_method,
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                redirect_uris=self.static_client_redirect_uris,
                scope="default",
            )

        # Dynamically registered (DCR) clients, e.g. Gemini Spark self-registering.
        stored = self.registered_clients.get(client_id)
        if stored:
            return OAuthClientInformationFull.model_validate(stored)

        # CIMD client path
        if is_cimd_client_id(client_id):
            return await asyncio.to_thread(self.cimd_helper.fetch_and_validate, client_id)

        return None

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if params.resource and self.resource_url not in params.resource:
            raise AuthorizeError(error="invalid_target", error_description="Invalid resource")
            
        if params.redirect_uri not in client.redirect_uris:
            raise AuthorizeError(error="invalid_request", error_description="Invalid redirect URI")
            
        import secrets
        session_id = secrets.token_urlsafe(32)
        
        self.auth_codes[f"pending-{session_id}"] = {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "redirect_uri": params.redirect_uri,
            "code_challenge": params.code_challenge,
            "code_challenge_method": "S256",
            "scope": params.scopes or [],
            "resource": params.resource,
            "state": params.state,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10)
        }
        
        return f"/consent?session_id={urllib.parse.quote(session_id)}"

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> Optional[AuthorizationCode]:
        code_data = self.auth_codes.get(authorization_code)
        if not code_data:
            return None
        if code_data["client_id"] != client.client_id:
            return None
        if code_data["expires_at"] < datetime.now(timezone.utc):
            del self.auth_codes[authorization_code]
            return None
            
        return AuthorizationCode(
            code=authorization_code,
            client_id=code_data["client_id"],
            scopes=code_data.get("scope") or [],
            expires_at=code_data["expires_at"].timestamp(),
            code_challenge=code_data["code_challenge"],
            redirect_uri=AnyHttpUrl(code_data["redirect_uri"]),
            redirect_uri_provided_explicitly=True,
            resource=code_data.get("resource"),
        )

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: AuthorizationCode) -> OAuthToken:
        code_data = self.auth_codes.pop(authorization_code.code, None)
        if not code_data:
            raise TokenError(error="invalid_grant", error_description="Invalid or expired authorization code")
            
        scope_str = " ".join(code_data["scope"])
        access_token = self._generate_jwt(
            aud=self.resource_url,
            client_id=client.client_id,
            scope=scope_str
        )
        
        import secrets
        refresh_token = secrets.token_urlsafe(64)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).timestamp()
        self.refresh_tokens[refresh_token] = {
            "client_id": client.client_id,
            "scopes": code_data.get("scope") or [],
            "expires_at": expires_at,
            "resource": code_data.get("resource")
        }
        self._save_refresh_tokens()
        
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=refresh_token,
            scope=scope_str
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> Optional[RefreshToken]:
        token_data = self.refresh_tokens.get(refresh_token)
        if token_data and token_data["client_id"] == client.client_id:
            return RefreshToken(
                token=refresh_token,
                client_id=token_data["client_id"],
                scopes=token_data.get("scopes") or [],
                expires_at=int(token_data["expires_at"]) if token_data.get("expires_at") is not None else None,
                resource=token_data.get("resource"),
            )
        return None

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: RefreshToken, scopes: list[str]) -> OAuthToken:
        token_data = self.refresh_tokens.pop(refresh_token.token, None)
        if not token_data:
            raise TokenError(error="invalid_grant", error_description="Invalid refresh token")
            
        scope_str = " ".join(scopes if scopes else (token_data.get("scopes") or []))
        access_token = self._generate_jwt(
            aud=self.resource_url,
            client_id=client.client_id,
            scope=scope_str
        )
        
        import secrets
        new_refresh_token = secrets.token_urlsafe(64)
        expires_at = (datetime.now(timezone.utc) + timedelta(days=30)).timestamp()
        self.refresh_tokens[new_refresh_token] = {
            "client_id": client.client_id,
            "scopes": scopes if scopes else (token_data.get("scopes") or []),
            "expires_at": expires_at,
            "resource": token_data.get("resource")
        }
        self._save_refresh_tokens()
        
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=new_refresh_token,
            scope=scope_str
        )


    async def load_access_token(self, token: str) -> Optional[AccessToken]:
        try:
            payload = jwt.decode(
                token,
                self.public_key,
                algorithms=["RS256"],
                audience=self.resource_url,
                options={"verify_exp": True, "verify_iss": False, "verify_aud": True}
            )
            return AccessToken(
                token=token,
                client_id=payload.get("sub", ""),
                scopes=payload.get("scope", "").split(" ") if payload.get("scope") else [],
                resource=self.resource_url,
                expires_at=int(payload["exp"]) if payload.get("exp") is not None else None,
                subject=payload.get("sub")
            )
        except Exception:
            return None

    async def revoke_token(self, token: str) -> None:
        if token in self.refresh_tokens:
            del self.refresh_tokens[token]
            self._save_refresh_tokens()

def create_oauth_server(issuer_url: str, resource_url: str, key_path: str = "oauth_key.pem") -> Starlette:
    if os.path.exists(key_path):
        with open(key_path, "rb") as f:
            private_key = serialization.load_pem_private_key(f.read(), password=None)
    else:
        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with open(key_path, "wb") as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))

    provider = ERATokenProvider(private_key, issuer_url, resource_url)

    from pydantic import TypeAdapter, AnyHttpUrl
    parsed_issuer = TypeAdapter(AnyHttpUrl).validate_python(issuer_url)
    
    routes = create_auth_routes(
        provider=provider,
        issuer_url=parsed_issuer,
        client_registration_options=ClientRegistrationOptions(
            enabled=True,
            default_scopes=["default"],
        )
    )
    
    async def jwks(request: Request):
        jwk_str = jwt.algorithms.RSAAlgorithm.to_jwk(provider.public_key)
        jwk = json.loads(jwk_str)
        jwk["kid"] = "era-key-1"
        jwk["use"] = "sig"
        return JSONResponse({"keys": [jwk]})

    async def consent_get(request: Request):
        session_id = request.query_params.get("session_id")
        if not session_id:
            return HTMLResponse("Missing session ID", status_code=400)
            
        data = provider.auth_codes.get(f"pending-{session_id}")
        if not data:
            return HTMLResponse("Invalid or expired session", status_code=400)
            
        csrf = secrets.token_urlsafe(16)
        data["csrf"] = csrf
        
        client_name = data.get("client_name") or "Unknown Client"
        scopes = ", ".join(data.get("scope", []))
        
        client = await provider.get_client(data["client_id"])
        secret_field = ""
        if client and client.client_secret:
            secret_field = """
                <p>
                    <label>Client secret: <input type="password" name="password" autocomplete="off" required></label>
                </p>"""

        page_html = f"""
        <html>
        <head><title>Authorization Consent</title></head>
        <body>
            <h2>Authorize {html.escape(client_name)}</h2>
            <p>The application <b>{html.escape(client_name)}</b> is requesting access to your ERA MCP Server.</p>
            <p><b>Scopes:</b> {scopes}</p>
            <p><b>Resource:</b> {resource_url}</p>
            <form method="post" action="/consent">
                <input type="hidden" name="session_id" value="{session_id}">
                <input type="hidden" name="csrf" value="{csrf}">
{secret_field}
                <button type="submit" name="action" value="approve">Approve</button>
                <button type="submit" name="action" value="deny">Deny</button>
            </form>
        </body>
        </html>
        """
        return HTMLResponse(page_html)
        
    async def consent_post(request: Request):
        form = await request.form()
        session_id = form.get("session_id")
        csrf = form.get("csrf")
        action = form.get("action")
        submitted = form.get("password")
        
        session_key = f"pending-{session_id}"
        data = provider.auth_codes.get(session_key)
        if not data or data.get("csrf") != csrf:
            return HTMLResponse("Invalid session or CSRF token", status_code=400)
            
        self = provider
        client = await self.get_client(data["client_id"])
        if not client or client.client_secret:
            expected = client.client_secret if client else None
            if not submitted or not isinstance(submitted, str) or not expected or not secrets.compare_digest(submitted, expected):
                return HTMLResponse("Invalid client secret", status_code=401)
            
        provider.auth_codes.pop(session_key, None)
            
        redirect_uri = data["redirect_uri"]
        state = data.get("state")
        
        if action == "deny":
            url = f"{redirect_uri}?error=access_denied"
            if state:
                url += f"&state={urllib.parse.quote(state)}"
            return RedirectResponse(url, status_code=302)
            
        elif action == "approve":
            code = secrets.token_urlsafe(32)
            provider.auth_codes[code] = data
            
            url = f"{redirect_uri}?code={urllib.parse.quote(code)}"
            if state:
                url += f"&state={urllib.parse.quote(state)}"
            return RedirectResponse(url, status_code=302)
            
        return HTMLResponse("Invalid action", status_code=400)

    async def custom_metadata(request: Request):
        from mcp.server.auth.routes import build_metadata
        from mcp.server.auth.settings import RevocationOptions
        base_meta = build_metadata(
            issuer_url,
            None,
            ClientRegistrationOptions(enabled=True, default_scopes=["default"]),
            RevocationOptions(enabled=False),
            supports_identity_assertion=False
        )
        base_dict = base_meta.model_dump(exclude_none=True, mode="json")
        base_dict["client_id_metadata_document_supported"] = True
        # Spark is a PUBLIC client (PKCE, no secret): advertise 'none' as an accepted
        # token-endpoint auth method, otherwise it refuses the server as incompatible.
        if "token_endpoint_auth_methods_supported" not in base_dict:
            base_dict["token_endpoint_auth_methods_supported"] = []
        if "none" not in base_dict["token_endpoint_auth_methods_supported"]:
            base_dict["token_endpoint_auth_methods_supported"].append("none")
        base_dict["jwks_uri"] = f"{issuer_url.rstrip('/')}/.well-known/jwks.json"
        base_dict["code_challenge_methods_supported"] = ["S256"]
        base_dict["scopes_supported"] = ["default"]
        base_dict["response_modes_supported"] = ["query"]
        return JSONResponse(base_dict)
        
    for i, r in enumerate(routes):
        if getattr(r, "path", None) == "/.well-known/oauth-authorization-server":
            routes[i] = Route("/.well-known/oauth-authorization-server", custom_metadata, methods=["GET"])

    routes.append(Route("/.well-known/jwks.json", jwks, methods=["GET"]))
    routes.append(Route("/consent", consent_get, methods=["GET"]))
    routes.append(Route("/consent", consent_post, methods=["POST"]))

    app = Starlette(routes=routes)
    
    from starlette.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=".*",
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["WWW-Authenticate", "Content-Type"],
        max_age=86400,
    )
    
    return app
