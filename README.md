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

## Running the Spring Boot API Gateway

From `backend/services/mtg-api-gateway`:

```
mvn spring-boot:run
```

Then test:

```
curl http://localhost:8080/api/v1/health
```