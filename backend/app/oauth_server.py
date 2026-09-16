import os
import json
import logging
import urllib.request
import urllib.error
import urllib.parse
import socket
from typing import Optional, Dict, Any, List
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
    AuthorizeError
)
from mcp.server.auth.settings import AuthSettings, ClientRegistrationOptions
from mcp.server.auth.routes import create_auth_routes
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

class ERATokenProvider(OAuthAuthorizationServerProvider[str, str, str]):
    def __init__(self, private_key: rsa.RSAPrivateKey, issuer_url: str, resource_url: str):
        self.private_key = private_key
        self.public_key = self.private_key.public_key()
        self.issuer_url = issuer_url
        self.resource_url = resource_url
        
        self.auth_codes = {}
        self.refresh_tokens = {}
        self.client_cache = {}

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

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        if not client_id.startswith("https://accountlinking.google.com/"):
            return None
        
        parsed = urllib.parse.urlparse(client_id)
        if parsed.hostname != "accountlinking.google.com":
            return None
            
        now = datetime.now(timezone.utc)
        if client_id in self.client_cache:
            cache_entry = self.client_cache[client_id]
            if cache_entry["expires_at"] > now:
                return cache_entry["client"]
        
        try:
            ip = socket.gethostbyname(parsed.hostname)
        except Exception:
            return None
            
        import ipaddress
        ip_obj = ipaddress.ip_address(ip)
        if ip_obj.is_loopback or ip_obj.is_private or ip_obj.is_multicast:
            return None
            
        class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
                
        opener = urllib.request.build_opener(NoRedirectHandler)
        req = urllib.request.Request(client_id, method="GET")
        
        try:
            with opener.open(req, timeout=5) as resp:
                if resp.status != 200:
                    return None
                data = resp.read(65536)
                meta = json.loads(data)
                redirect_uris = meta.get("redirect_uris", [])
                
                client_info = OAuthClientInformationFull(
                    client_id=client_id,
                    client_name=meta.get("client_name", "Unknown Client"),
                    redirect_uris=redirect_uris,
                    grant_types=["authorization_code", "refresh_token"],
                    response_types=["code"],
                    scope=" ".join(meta.get("scopes", []))
                )
                self.client_cache[client_id] = {
                    "client": client_info,
                    "expires_at": now + timedelta(minutes=5)
                }
                return client_info
        except Exception as e:
            logger.error(f"Failed to fetch CIMD: {e}")
            return None

    async def register_client(self, client_info: OAuthClientInformationFull) -> None:
        raise NotImplementedError("Dynamic client registration is not supported")

    async def authorize(self, client: OAuthClientInformationFull, params: AuthorizationParams) -> str:
        if not params.resource or self.resource_url not in params.resource:
            raise AuthorizeError(error="invalid_target", error_description="Invalid resource")
            
        if params.redirect_uri not in client.redirect_uris:
            raise AuthorizeError(error="invalid_request", error_description="Invalid redirect URI")
            
        if params.code_challenge_method != "S256":
            raise AuthorizeError(error="invalid_request", error_description="PKCE S256 required")

        import secrets
        session_id = secrets.token_urlsafe(32)
        
        self.auth_codes[f"pending-{session_id}"] = {
            "client_id": client.client_id,
            "client_name": client.client_name,
            "redirect_uri": params.redirect_uri,
            "code_challenge": params.code_challenge,
            "code_challenge_method": params.code_challenge_method,
            "scope": params.scopes,
            "resource": params.resource,
            "state": params.state,
            "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10)
        }
        
        return f"/consent?session_id={urllib.parse.quote(session_id)}"

    async def load_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> Optional[str]:
        code_data = self.auth_codes.get(authorization_code)
        if not code_data:
            return None
        if code_data["client_id"] != client.client_id:
            return None
        if code_data["expires_at"] < datetime.now(timezone.utc):
            del self.auth_codes[authorization_code]
            return None
        return authorization_code

    async def exchange_authorization_code(self, client: OAuthClientInformationFull, authorization_code: str) -> OAuthToken:
        code_data = self.auth_codes.pop(authorization_code, None)
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
        self.refresh_tokens[refresh_token] = {
            "client_id": client.client_id,
            "scope": code_data["scope"]
        }
        
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=refresh_token,
            scope=scope_str
        )

    async def load_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str) -> Optional[str]:
        token_data = self.refresh_tokens.get(refresh_token)
        if token_data and token_data["client_id"] == client.client_id:
            return refresh_token
        return None

    async def exchange_refresh_token(self, client: OAuthClientInformationFull, refresh_token: str, scopes: list[str]) -> OAuthToken:
        token_data = self.refresh_tokens.pop(refresh_token, None)
        if not token_data:
            raise TokenError(error="invalid_grant", error_description="Invalid refresh token")
            
        scope_str = " ".join(scopes if scopes else token_data["scope"])
        access_token = self._generate_jwt(
            aud=self.resource_url,
            client_id=client.client_id,
            scope=scope_str
        )
        
        import secrets
        new_refresh_token = secrets.token_urlsafe(64)
        self.refresh_tokens[new_refresh_token] = {
            "client_id": client.client_id,
            "scope": scopes if scopes else token_data["scope"]
        }
        
        return OAuthToken(
            access_token=access_token,
            token_type="Bearer",
            expires_in=3600,
            refresh_token=new_refresh_token,
            scope=scope_str
        )

    async def load_access_token(self, token: str) -> Optional[str]:
        return token

    async def revoke_token(self, token: str) -> None:
        if token in self.refresh_tokens:
            del self.refresh_tokens[token]

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
        client_registration_options=ClientRegistrationOptions(enabled=False)
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
            
        import secrets
        csrf = secrets.token_urlsafe(16)
        data["csrf"] = csrf
        
        client_name = data.get("client_name", "Unknown Client")
        scopes = ", ".join(data.get("scope", []))
        
        html = f"""
        <html>
        <head><title>Authorization Consent</title></head>
        <body>
            <h2>Authorize {client_name}</h2>
            <p>The application <b>{client_name}</b> is requesting access to your ERA MCP Server.</p>
            <p><b>Scopes:</b> {scopes}</p>
            <p><b>Resource:</b> {resource_url}</p>
            <form method="post" action="/consent">
                <input type="hidden" name="session_id" value="{session_id}">
                <input type="hidden" name="csrf" value="{csrf}">
                <button type="submit" name="action" value="approve">Approve</button>
                <button type="submit" name="action" value="deny">Deny</button>
            </form>
        </body>
        </html>
        """
        return HTMLResponse(html)
        
    async def consent_post(request: Request):
        form = await request.form()
        session_id = form.get("session_id")
        csrf = form.get("csrf")
        action = form.get("action")
        
        data = provider.auth_codes.pop(f"pending-{session_id}", None)
        if not data or data.get("csrf") != csrf:
            return HTMLResponse("Invalid session or CSRF token", status_code=400)
            
        redirect_uri = data["redirect_uri"]
        state = data.get("state")
        
        if action == "deny":
            url = f"{redirect_uri}?error=access_denied"
            if state:
                url += f"&state={urllib.parse.quote(state)}"
            return RedirectResponse(url, status_code=302)
            
        elif action == "approve":
            import secrets
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
            ClientRegistrationOptions(enabled=False),
            RevocationOptions(enabled=False),
            supports_identity_assertion=False
        )
        base_dict = base_meta.model_dump(exclude_none=True, mode="json")
        base_dict["client_id_metadata_document_supported"] = True
        base_dict["jwks_uri"] = f"{issuer_url.rstrip('/')}/.well-known/jwks.json"
        base_dict["code_challenge_methods_supported"] = ["S256"]
        return JSONResponse(base_dict)
        
    for i, r in enumerate(routes):
        if getattr(r, "path", None) == "/.well-known/oauth-authorization-server":
            routes[i] = Route("/.well-known/oauth-authorization-server", custom_metadata, methods=["GET"])

    routes.append(Route("/.well-known/jwks.json", jwks, methods=["GET"]))
    routes.append(Route("/consent", consent_get, methods=["GET"]))
    routes.append(Route("/consent", consent_post, methods=["POST"]))

    app = Starlette(routes=routes)
    return app
