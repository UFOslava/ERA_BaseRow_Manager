FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

ENV FLASK_APP=run.py
ENV PYTHONUNBUFFERED=1
ENV DATABASE_URL=/app/data/parts.db

RUN mkdir -p /app/data

CMD ["python", "run.py"]
