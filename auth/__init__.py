"""
QMS Authentication Module — Microsoft Entra ID SSO with local role management.
"""

from qms.auth.decorators import login_required, role_required

__all__ = ["login_required", "role_required"]
