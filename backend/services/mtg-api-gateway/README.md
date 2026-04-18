# MTG API Gateway (Spring Boot)

This service exposes backend compute workflows through a REST API.

## Endpoints

- `GET /api/v1/health`
- `POST /api/v1/compute/run`

## Example Request

```json
{
  "jobType": "arbitrage",
  "args": []
}
```

Supported `jobType` values:

- `arbitrage`
- `scanner`
- `analysis`
- `buylist`

## Run

```bash
mvn spring-boot:run
```

## Notes

- Python command defaults to `python` and can be changed with `backend.python.command`.
- Compute root defaults to `../compute` and can be changed with `backend.compute.root`.
