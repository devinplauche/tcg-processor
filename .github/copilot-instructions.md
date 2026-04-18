# Copilot Instructions for Full-Stack App (Flask + Spring Boot)

## Project Overview
This project is a full-stack web application with:
- Frontend: Flask (Python)
- Backend API: Spring Boot (Java)
- Communication: RESTful APIs (JSON over HTTP)
- Architecture: Decoupled frontend and backend

Copilot should prioritize clean separation of concerns, readability, and production-ready patterns.

---

## General Guidelines
- Write clear, maintainable, and well-documented code.
- Prefer simplicity over cleverness.
- Follow best practices for both Python (Flask) and Java (Spring Boot).
- Use consistent naming conventions across frontend and backend.
- Avoid unnecessary dependencies.
- Include comments where logic is non-trivial.

---

## Folder Structure (Expected)

/frontend-flask
  /app
    __init__.py
    routes.py
    templates/
    static/
  run.py
  requirements.txt

/backend-springboot
  /src/main/java/com/example/app
    controller/
    service/
    repository/
    model/
  /src/main/resources
    application.yml
  pom.xml

/.github
  copilot-instructions.md

---

## Flask Frontend Guidelines

### General
- Use Flask primarily as a UI layer, not for business logic.
- Keep logic minimal; delegate to backend APIs.
- Use Jinja2 templates for rendering views.
- Organize routes using Blueprints if the app grows.

### API Communication
- Use the `requests` library to call Spring Boot APIs.
- Store backend base URL in environment variables.
- Handle API failures gracefully.

### Example Pattern
```python
import os
import logging
import requests
from flask import Blueprint, render_template

bp = Blueprint('main', __name__)
logger = logging.getLogger(__name__)

@bp.route('/')
def index():
  api_base_url = os.environ.get('API_BASE_URL')
  if not api_base_url:
    raise RuntimeError('API_BASE_URL environment variable is required')

  tasks = []
  try:
    response = requests.get(f"{api_base_url}/tasks", timeout=10)
    tasks = response.json() if response.ok else []
  except requests.exceptions.RequestException as exc:
    logger.warning('Failed to fetch tasks from backend API: %s', exc)
    return render_template('index.html', tasks=tasks)