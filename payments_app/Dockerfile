FROM python:3.12.8-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . payments_app/

ENV BLAST_DB_PATH=/data/payments.db
EXPOSE 8000
CMD ["uvicorn", "payments_app.service.api:app", "--host", "0.0.0.0", "--port", "8000"]
