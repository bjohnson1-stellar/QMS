"""
QMS Authentication Module — local email + password with session-based authorization.
"""

from qms.auth.decorators import login_required, role_required

__all__ = ["login_required", "role_required"]
