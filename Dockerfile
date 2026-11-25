FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Tesseract + dicionário de português para o OCR de imagens e PDFs digitalizados.
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-por \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 1000 appuser

WORKDIR /app

# Lock com hashes: pip recusa qualquer artefato diferente do registrado.
COPY requirements.lock.txt .
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.lock.txt

COPY *.py ./

RUN chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/saude')"

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
