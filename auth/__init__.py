"""
QMS Authentication Module — local email + password with session-based authorization.

Provides global roles (admin/user/viewer) and per-module access control
(projects, welding, pipeline, automation) with module-level roles
(admin/editor/viewer). Global admins bypass module checks.
"""

from qms.auth.decorators import login_required, module_required, role_required

__all__ = ["login_required", "module_required", "role_required"]
