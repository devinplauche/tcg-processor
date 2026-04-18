# SortSwift-Style Full Stack MTG Application

This repository is organized as a full stack Magic: The Gathering platform with a clear separation between frontend and backend domains.

## Architecture

### Frontend

The user-facing application, browser assets, and architecture visualizations are under `frontend/`.

```
frontend/
├── mtg-inventory/      # Existing Flask-based UI and web app resources
└── architecture/       # Frontend diagrams and HTML architecture artifacts
```

### Backend

The backend hosts heavy compute modules (scanner, arbitrage, buylist, MTGJSON analysis) and exposes them through a Spring Boot API gateway.

```
backend/
├── services/
│   └── mtg-api-gateway/    # Spring Boot API layer for compute jobs
├── compute/
│   ├── arbitrage-engine/
│   ├── Ollama-scanner/
│   ├── MTGJSON-analysis/
│   ├── buylist-updater/
│   └── langchain/
├── contracts/              # API contract documents
├── docs/                   # Backend implementation docs
└── data/
	└── test_data/          # Heavy test data and image resources
```

## Backend API Gateway

The Spring Boot service at `backend/services/mtg-api-gateway` provides:

- Health endpoint for operational checks
- Compute execution endpoint to run Python-based backend jobs
- Consistent JSON response envelope for future frontend integration

### Endpoints

- `GET /api/v1/health`
- `POST /api/v1/compute/run`

## Development Guidance

- Put browser/UI-specific changes under `frontend/`
- Put CPU-heavy processing, scanner/image workflows, and data pipelines under `backend/compute/`
- Expose backend compute features via `backend/services/mtg-api-gateway`
- Keep interface changes documented under `backend/contracts/` and `backend/docs/`

## Local Developer Setup

Run the bootstrap script once after cloning:

```bash
python scripts/setup_dev_environment.py
```

This does two things:

- Creates `frontend/mtg-inventory/.env.local` from `.env.example` if you do not already have one
- Configures git to use the repo-managed `.githooks/pre-commit` hook, which blocks commits containing common secret patterns

Pull requests also run the non-live `frontend/mtg-inventory/test_secret_management.py` suite in CI as a backstop.

## Running the Spring Boot API Gateway

From `backend/services/mtg-api-gateway`:

```
mvn spring-boot:run
```

Then test:

```
curl http://localhost:8080/api/v1/health
```
