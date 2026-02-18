# Entra ID (Azure AD) App Registration Guide

This document explains how to register the QMS app in the Azure Portal for Microsoft Entra ID SSO.

## Prerequisites

- Azure AD tenant (any Microsoft 365 or Azure subscription)
- Permission to register applications (or request from IT admin)

## Step 1: Register the Application

1. Go to [Azure Portal](https://portal.azure.com) > **Microsoft Entra ID** > **App registrations**
2. Click **New registration**
3. Fill in:
   - **Name**: `QMS - Quality Management System`
   - **Supported account types**: "Accounts in this organizational directory only" (single tenant)
   - **Redirect URI**: Select **Web** and enter `http://localhost:5000/auth/callback`
4. Click **Register**

## Step 2: Note the IDs

After registration, you'll see the **Overview** page:

- **Application (client) ID** → Put in `config.yaml` as `auth.entra.client_id`
- **Directory (tenant) ID** → Put in `config.yaml` as `auth.entra.tenant_id`

## Step 3: Create a Client Secret

1. Go to **Certificates & secrets** > **Client secrets**
2. Click **New client secret**
3. Description: `QMS Auth`
4. Expiry: 24 months (set a calendar reminder to rotate)
5. Copy the **Value** (not the Secret ID) → Put in `config.yaml` as `auth.entra.client_secret`

> **Security**: In production, use the `QMS_SECRET_KEY` environment variable instead of storing secrets in config.yaml.

## Step 4: Configure Token Claims

1. Go to **Token configuration**
2. Click **Add optional claim**
3. Token type: **ID**
4. Select: `email`, `preferred_username`
5. Click **Add**

## Step 5: API Permissions

1. Go to **API permissions**
2. Verify `Microsoft Graph > User.Read` is listed (should be added by default)
3. If not, click **Add a permission** > **Microsoft Graph** > **Delegated** > `User.Read`
4. Click **Grant admin consent** (if you have admin rights)

## Step 6: Update QMS Config

Edit `config.yaml`:

```yaml
auth:
  provider: "entra_id"
  dev_bypass: false  # Disable for production
  secret_key: null   # Set QMS_SECRET_KEY env var instead
  session_lifetime_minutes: 480
  default_role: "user"
  entra:
    tenant_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    client_id: "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    client_secret: "your-client-secret-value"
```

## Step 7: Production Redirect URI

For production deployment, add the production URL as an additional redirect URI:

1. Go to **Authentication** > **Platform configurations** > **Web**
2. Add: `https://your-domain.com/auth/callback`

## Environment Variables (Recommended for Production)

Instead of storing secrets in config.yaml:

```bash
set QMS_SECRET_KEY=<random-32-byte-hex>
set QMS_ENTRA_TENANT_ID=<tenant-id>
set QMS_ENTRA_CLIENT_ID=<client-id>
set QMS_ENTRA_CLIENT_SECRET=<client-secret>
```

The app factory reads `QMS_SECRET_KEY` from environment. For Entra credentials, the config.yaml values are used directly (env var override can be added later if needed).

## Troubleshooting

| Issue | Fix |
|-------|-----|
| "AADSTS50011: Reply URL mismatch" | Ensure redirect URI in Azure exactly matches `http://localhost:5000/auth/callback` |
| "AADSTS7000218: Request body must contain client_assertion or client_secret" | Verify client_secret is correct in config.yaml |
| "403 Account deactivated" | An admin set `is_active=0` for this user in the users table |
| Users get "viewer" role | Change `auth.default_role` in config.yaml |

## Roles

QMS uses local roles stored in the `users` database table:

| Role | Access |
|------|--------|
| `admin` | Full access + user management |
| `user` | Full access to all modules |
| `viewer` | Read-only access (future enforcement) |

Roles are assigned locally and **not** synced from Entra ID groups. Admins can change roles via the `/auth/users` API endpoint.
