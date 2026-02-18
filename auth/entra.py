"""
Microsoft Entra ID (Azure AD) MSAL integration.

Pure functions — no Flask imports. Takes config dicts and plain strings.
"""

from __future__ import annotations

import msal


AUTHORITY_TEMPLATE = "https://login.microsoftonline.com/{tenant_id}"
SCOPES = ["User.Read"]  # Minimal — just need profile info from ID token


def _build_authority(tenant_id: str) -> str:
    return AUTHORITY_TEMPLATE.format(tenant_id=tenant_id)


def _get_msal_app(entra_config: dict) -> msal.ConfidentialClientApplication:
    """Build an MSAL ConfidentialClientApplication from config."""
    return msal.ConfidentialClientApplication(
        client_id=entra_config["client_id"],
        client_credential=entra_config["client_secret"],
        authority=_build_authority(entra_config["tenant_id"]),
    )


def build_auth_url(entra_config: dict, redirect_uri: str, state: str | None = None) -> str:
    """
    Build the Entra ID authorization URL for the login redirect.

    Returns a URL the browser should be redirected to.
    """
    app = _get_msal_app(entra_config)
    flow = app.initiate_auth_code_flow(
        scopes=SCOPES,
        redirect_uri=redirect_uri,
        state=state,
    )
    # The flow dict contains the auth_uri and must be cached for callback
    return flow


def complete_auth_flow(
    entra_config: dict, auth_flow: dict, auth_response: dict
) -> dict | None:
    """
    Exchange the authorization code for tokens and extract user claims.

    Args:
        entra_config: Entra ID configuration from config.yaml
        auth_flow: The flow dict returned by build_auth_url
        auth_response: The query parameters from the callback URL

    Returns:
        Dict with id_token_claims on success, None on failure.
    """
    app = _get_msal_app(entra_config)
    result = app.acquire_token_by_auth_code_flow(
        auth_code_flow=auth_flow,
        auth_response=auth_response,
    )

    if "error" in result:
        return None

    return result


def extract_claims(token_result: dict) -> dict:
    """
    Pull the fields we care about from the MSAL token result.

    Returns dict with: oid, email, display_name
    """
    claims = token_result.get("id_token_claims", {})
    return {
        "oid": claims.get("oid", ""),
        "email": claims.get("preferred_username", claims.get("email", "")),
        "display_name": claims.get("name", "Unknown"),
    }


def build_logout_url(tenant_id: str, post_logout_redirect_uri: str) -> str:
    """Build the Entra ID logout URL."""
    authority = _build_authority(tenant_id)
    return (
        f"{authority}/oauth2/v2.0/logout"
        f"?post_logout_redirect_uri={post_logout_redirect_uri}"
    )
