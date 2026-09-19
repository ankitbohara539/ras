# CivicGrid — Smart Communities & Inclusive Tech

CivicGrid is a production-oriented modular-monolith MVP for community issue reporting, civic-service discovery, emergency coordination, alerts, accessibility, and municipal operations.

The application uses Next.js 16, FastAPI, async SQLAlchemy, Alembic, MySQL 8.4, standards-based JWT authentication, Argon2id, Redis-compatible realtime events, OpenStreetMap, and IndexedDB offline queuing. There is no hosted database or third-party authentication dependency.

## Architecture

~~~text
Next.js Web/PWA
   │ HTTPS + authenticated WebSocket
FastAPI modular monolith
   ├── Auth + rotating sessions + RBAC
   ├── Users + accessibility
   ├── Issues + media + workflow
   ├── Civic services + MySQL GIS
   ├── SOS + alerts + notifications
   └── Administration + audit
       │
       ├── MySQL 8.4 (source of truth)
       ├── Redis Pub/Sub (optional; in-memory fallback)
       ├── SMTP (console-safe development fallback)
       └── Local/S3-compatible object storage port
~~~

Backend modules separate domain, application, infrastructure, and presentation responsibilities. FastAPI handlers validate and authorize requests, then delegate business rules to application services.

## Local setup

Prerequisites: Node.js 20+, Python 3.12+, and a locally installed MySQL 8.x server and client.

1. Copy environment templates:

~~~powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env.local
~~~

2. Create the local MySQL database and application user. The host, username,
   password, and database must match `DATABASE_URL` in `backend/.env`:

~~~powershell
mysql -u root -p -e "CREATE DATABASE IF NOT EXISTS civicgrid CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci; CREATE USER IF NOT EXISTS 'civicgrid'@'127.0.0.1' IDENTIFIED BY 'civicgrid'; GRANT ALL PRIVILEGES ON civicgrid.* TO 'civicgrid'@'127.0.0.1'; FLUSH PRIVILEGES;"
~~~

Redis is optional during local development. Leave `REDIS_URL` empty to use the
in-memory event and rate-limit adapters.

3. Install, migrate, and run the backend:

~~~powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
~~~

4. Create the first administrator:

~~~powershell
cd backend
.\.venv\Scripts\python.exe scripts/create_admin.py --email admin@example.com --name "Platform Admin"
~~~

The CLI creates or promotes a verified account and is intentionally not exposed as a public API.

For the complete local role and Kathmandu demonstration dataset, run:

~~~powershell
.\.venv\Scripts\python.exe scripts/seed_development_users.py
.\.venv\Scripts\python.exe scripts/seed_demo_data.py
~~~

The development seeder creates one login for every RBAC role. The demo-data
seeder is idempotent and creates 100 primary records distributed across issues,
civic services, alerts, SOS cases, and notifications, with related workflow rows.

5. Start the frontend:

~~~powershell
cd frontend
npm install
npm run dev
~~~

Open http://localhost:3000. API documentation is at http://localhost:8000/docs.

### SMTP email delivery

Password recovery uses SMTP when `SMTP_HOST` is set. New accounts are active
immediately and do not require email verification. Use
`SMTP_SECURITY=starttls` with the provider's STARTTLS port (commonly 587), or
`SMTP_SECURITY=tls` with its implicit-TLS port (commonly 465). The sender must be
authorized by the SMTP provider. When `SMTP_HOST` is empty, development uses a
non-delivering console sink and `/health/ready` reports `email: console_only`.

Never commit SMTP credentials. Put them only in `backend/.env`, restart the API,
and use the forgot-password endpoint to test delivery.

### OpenStreetMap and Nominatim

The browser uses the configurable OpenStreetMap tile URL and always displays
the required attribution. Backend geocoding is cached and serialized to at most
one public Nominatim request per second. Searches are country-filtered to Nepal,
biased and bounded to the configured Kathmandu viewbox, and are submitted only
when the user explicitly searches (never as autocomplete). Set `NOMINATIM_CONTACT` to a real public
email address or project URL so the service operator can identify the app. Do
not add autocomplete, bulk geocoding, or offline tile downloads when using the
public OSM services. For production traffic, configure an appropriate hosted or
self-managed tile/geocoding provider through the existing environment variables.

## Authentication and RBAC

Public registration always assigns CITIZEN. Privileged roles are assigned only through administrator APIs or the initial-admin CLI.

Access tokens are short-lived JWTs in HttpOnly cookies. Opaque refresh tokens are stored only as SHA-256 hashes, rotate on every refresh, and are grouped into families for reuse detection. Passwords use Argon2id. Password-reset tokens are random, hashed, expiring, and single-use.

| Capability | Citizen | Authority | Responder | Admin |
| --- | --- | --- | --- | --- |
| Report and confirm issues | Yes | View | View | Yes |
| Verify/update issue workflow | No | Yes | No | Yes |
| Trigger SOS | Yes | Yes | Yes | Yes |
| Operate SOS response | No | No | Yes | Yes |
| Publish alerts/manage services | No | Yes | No | Yes |
| Manage users, roles, areas | No | No | No | Yes |
| View audit records | No | No | No | Yes |

Frontend guards improve navigation only. Every protected operation is re-authorized by FastAPI.

Public landing and authentication pages provide a persistent EN/नेपाली switch.
Authenticated users additionally retain their reading language and accessibility
preferences through MySQL.

## Database and migrations

The initial Alembic migration creates the full schema, foreign keys, reference seeds, conventional indexes, POINT NOT NULL SRID 4326 columns, and spatial indexes. A subsequent reference migration seeds Kathmandu Metropolitan City and its 32 official ward records for ward-aware reporting. Location conversion is centralized and explicitly uses long-lat axis order.

Run migrations from the backend directory:

~~~powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic downgrade -1
~~~

## API surface

All business APIs use the /api/v1 prefix.

- /auth — register, verify, resend, login, refresh, logout, forgot/reset password, current user
- /users — profile and accessibility preferences
- /issues — reporting, listing, nearby search, confirmations, status workflow, history, media
- /civic-services — directory and nearby spatial search
- /emergencies — SOS creation and responder transitions
- /alerts — active alerts and authority publishing
- /notifications — persisted list, unread count, read state
- /geo — guarded reverse geocoding and place search
- /admin — users, roles, status, structural data, audit records
- /ws — authenticated, role-scoped realtime events
- /health/live and /health/ready — orchestration probes

## Offline and realtime behavior

Ordinary issue reports can be stored in IndexedDB with a client request UUID. MySQL enforces uniqueness, so reconnect retries are idempotent. Attached files remain device-local until sync.

SOS requests are never queued as successful. When offline the UI explicitly states that the emergency request has not reached the server.

WebSocket events are scoped to user and role channels. Persisted notifications provide missed-event reconciliation. Redis Pub/Sub is used when REDIS_URL is configured; development uses the same interface with an in-memory adapter.

## Verification

~~~powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\alembic.exe upgrade head --sql

cd ..\frontend
npm run lint
npm run typecheck
npm test
npm run build
npm run test:e2e
~~~

Live integration and credentialed E2E tests require MySQL, a running API, and test-account environment variables. No test result should be inferred merely from the commands above.

## Production checklist

- Replace development secrets with independent high-entropy values.
- Set COOKIE_SECURE=true and deploy web/API under the same site.
- Configure SMTP and an S3-compatible object-storage adapter.
- Configure Redis for multi-instance WebSocket delivery and rate limiting.
- Use a managed MySQL 8.4 service with backups, TLS, monitoring, and least-privilege credentials.
- Put Nominatim behind an appropriate provider or self-hosted service and retain attribution.
- Add malware scanning and image transformation to the media pipeline.
- Add distributed tracing, metrics, background jobs, and retention policies.
