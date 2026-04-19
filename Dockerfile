FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=10000

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY frontend/mtg-inventory/requirements.txt ./frontend/mtg-inventory/requirements.txt

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY app_loader.py index.py wsgi.py vercel.json ./
COPY frontend/mtg-inventory ./frontend/mtg-inventory

EXPOSE 10000

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --threads 4 wsgi:app"]
