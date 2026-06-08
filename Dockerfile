FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY kbdex/ kbdex/

VOLUME ["/app/data"]

ENV KBDEX_DATA_DIR=/app/data

EXPOSE 8000

CMD ["uvicorn", "kbdex.main:app", "--host", "0.0.0.0", "--port", "8000"]
