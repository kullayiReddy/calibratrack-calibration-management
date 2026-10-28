# CalibraTrack

**Instrument calibration, maintenance, and compliance monitoring**

CalibraTrack is a decision-support web application for tracking industrial instruments, calibration results, certificates, production-use decisions, work orders, alerts, and audit events. It uses synthetic demonstration records and does not control plant equipment or provide an OT interlock.

## What is included

- FastAPI REST API with bearer-token authentication and backend role checks.
- SQLAlchemy models and Alembic migration for assets, plans, calibrations, certificates, production uses, work orders, alerts, exceptions, impact assessments, corrective actions, batches, suppliers, users, and audit records.
- Compliance service that derives calibration outcomes from measurements and evaluates production use against historical calibration state.
- React, TypeScript, Vite, and Recharts interface with a dashboard, site selector, and API-backed inventory, schedule, certificate, use, work-order, and alert views.
- Deterministic synthetic-data generator, separate anomaly ground truth, and export validator.
- Docker Compose configuration for PostgreSQL, API, and frontend.

The interface currently focuses on read and review workflows. Some create, approval, report, and audit workflows are available through the API but do not yet have dedicated UI screens.

## Technology

| Area | Stack |
|---|---|
| Frontend | React, TypeScript, Vite, Recharts |
| Backend | Python 3.12+, FastAPI, Pydantic |
| Database | SQLite for local quick start; PostgreSQL supported |
| Data layer | SQLAlchemy 2.x, Alembic |
| Validation | pytest; HTTPX dependency for API tests |
| Synthetic data | Python, Faker, NumPy, pandas |

All stored timestamps are intended to be UTC. Calibration intervals count calendar days. Plans use inclusive effective dates; plan changes are stored as new effective-dated rows.

## Run locally

Requirements: Python 3.12+, Node.js 20+, and pnpm. SQLite is used by default, so PostgreSQL is not required for the local demo.

From the repository root in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
alembic upgrade head
python -m generator.generate --profile starter --seed 20261022
python -m backend.seed --with-starter-data
uvicorn backend.main:app --reload
```

In a second terminal:

```powershell
cd frontend
pnpm install
pnpm dev
```

Open `http://127.0.0.1:5173/`. The API is at `http://127.0.0.1:8000/`; interactive documentation is at `http://127.0.0.1:8000/docs`.

The local seed creates `operator`, `maintenance`, `quality`, `planner`, and `admin` accounts. The demonstration password for each is `CalibraTrack-Demo-2026!`. Replace these accounts and configure a strong `SECRET_KEY` before any shared or production deployment.

### PostgreSQL or Docker

Set `DATABASE_URL` to a PostgreSQL SQLAlchemy URL before running Alembic or the API. For example:

```powershell
$env:DATABASE_URL = "postgresql+psycopg://calibra:calibra@localhost:5432/calibra"
```

The Compose file starts PostgreSQL, the API, and Vite with `docker compose up --build`. Apply migrations and seed data after the services start.

## Generate and validate data

The generator uses fixed seed `20261022` by default and writes CSV and JSON files under `data/generated/`.

```powershell
python -m generator.generate --profile starter --seed 20261022
python -m generator.validate --input-dir data/generated
python -m generator.generate --profile full --seed 20261022
```

The `starter` profile generates 40 assets, 100 calibrations, and 1,000 production uses. The `full` profile is configured for 2,000 assets, 5,000 calibrations, and 100,000 production uses. The generator injects four labeled anomaly scenarios and writes expected labels to separate `ground_truth.csv` and `ground_truth.json` files. The operational compliance logic does not read ground truth.

The full profile is available but is not part of the seeded local database by default. Generated files and the SQLite database are excluded from Git; regenerate them with the commands above.

## Tests

```powershell
python -m pytest
```

The current automated suite contains unit tests for calendar-day due dates and measurement-derived pass/fail outcomes. API integration, authorization-matrix, and end-to-end browser coverage remain future work.

## Security and known limitations

- Demo credentials and the development signing-key fallback are for local evaluation only.
- Certificate files use local private storage; production should use authenticated object storage and a retention policy.
- The site selector groups the synthetic `Plant A`, `Plant B`, and `Lab 1` locations under North Plant, South Plant, and Quality Lab. It is a demo mapping, not a real site hierarchy.
- Some dashboards and workflow screens are simplified; verify calculations and policies against site procedures before operational use.
- This system is monitoring and decision support only. It has no connection to production controls or instrument interlocks.

## AI use and review

AI assistance was used to scaffold and revise the application, generator, documentation, and interface. The prompt record and a candidate-editable disclosure are in [`docs/AI_USE_AND_PROMPT_HISTORY.md`](docs/AI_USE_AND_PROMPT_HISTORY.md). The candidate should complete the personal review section before submitting and be ready to explain and demonstrate the code.

