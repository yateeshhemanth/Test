# InCred NeoBank Lending Platform (Advanced Edition)

A production-oriented lending application with banking-style UX, client/admin/super-admin roles, automated support workflows, and traffic analytics.

## What’s Included

### Public Banking Website
- Hero with live application success metrics
- About, Products, Partners, Customer Reviews, FAQ, Contact
- Advanced interactive UI (3D tilt cards + hover transitions)

### Core Lending Workflows
- Client registration/login
- Admin + Super Admin login
- EMI calculator
- Loan application + required document uploads
- Admin status actions: approve/reject/request additional documents
- Client additional document upload flow

### Ticket Management System
- Client ticket creation with priority (`low|medium|high`)
- Auto-assignment to least-loaded admin user
- Ticket lifecycle states (`open`, `in_progress`, `resolved`)
- Admin ticket controls and visibility
- Client can track assigned admin + ticket status in dashboard

### Super Admin Controls
- Dedicated super admin role
- API traffic analytics endpoint
- Ticket flow snapshots (open / in-progress / resolved)
- Role-based traffic breakdown + top API path visibility

## Tech Stack
- **Backend:** FastAPI, SQLAlchemy, JWT auth, SQLite (starter)
- **Frontend:** Vanilla JS + modern CSS (hover + 3D card interactions)

## Local Development

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Open: `http://localhost:8000`

### Seeded Users
- Admin: `admin@incred.local` / `admin123`
- Super Admin: `superadmin@incred.local` / `superadmin123`

---

## Production Deployment Guide

### 1) Infrastructure
- Use a VM/container platform (AWS ECS, GCP Cloud Run, Azure App Service, Render, Railway, etc.).
- Place the app behind a reverse proxy (Nginx/Caddy/Cloudflare) with TLS.
- Configure domain + HTTPS certificates.

### 2) Application Configuration
- Set strong environment values:
  - `SECRET_KEY=<long-random-secret>`
  - `ACCESS_TOKEN_EXPIRE_MINUTES=<policy-driven value>`
- Restrict CORS to trusted frontend domains (avoid `*` in production).

### 3) Database
- Replace SQLite with PostgreSQL for production reliability.
- Use Alembic migrations for schema evolution.
- Enable periodic backups + PITR strategy.

### 4) File Storage
- Replace local `uploads/` with object storage (S3/GCS/Azure Blob).
- Add antivirus/malware scanning and MIME validation.
- Use signed URLs for secure file retrieval.

### 5) Security Hardening
- Enforce rate limits (per IP/per user).
- Add MFA for admin/super-admin roles.
- Add audit logging for admin actions.
- Rotate secrets and maintain a secrets manager.

### 6) Observability
- Add structured logs (JSON), request tracing, and metrics dashboards.
- Alert on error spikes, auth failures, and queue/ticket SLA breaches.

### 7) CI/CD
- Add pipeline checks:
  - lint
  - tests
  - dependency scanning
  - container scan
- Deploy using blue/green or rolling strategy with health checks.

## Suggested Next Enhancements
- Notification center (email/SMS/WhatsApp) for status/ticket changes.
- SLA engine and escalation rules for tickets.
- Credit decisioning integration with bureau/underwriting models.
- Admin workload dashboard with assignment balancing heuristics.
