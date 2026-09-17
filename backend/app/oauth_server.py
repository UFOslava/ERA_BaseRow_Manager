import os
import json
import logging
import urllib.parse
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
    AuthorizeError,
    AuthorizationCode,
    RefreshToken,
    AccessToken
)
from pydantic import AnyHttpUrl
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
        
        # Static Client settings
        self.static_client_id = os.getenv("OAUTH_CLIENT_ID")
        self.static_client_secret = os.getenv("OAUTH_CLIENT_SECRET")
        uris_env = os.getenv("OAUTH_CLIENT_REDIRECT_URIS", "")
        self.static_client_redirect_uris = [AnyHttpUrl(u.strip()) for u in uris_env.split(",")] if uris_env else []

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

    async def get_client(self, client_id: str) -> Optional[OAuthClientInformationFull]:
        # Static confidential client (configured via .env) — rejects anything else.
        if self.static_client_id and client_id == self.static_client_id:
            return OAuthClientInformationFull(
                client_id=self.static_client_id,
                client_secret=self.static_client_secret,
                token_endpoint_auth_method="client_secret_basic",
                grant_types=["authorization_code", "refresh_token"],
                response_types=["code"],
                redirect_uris=self.static_client_redirect_uris,
            )
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
