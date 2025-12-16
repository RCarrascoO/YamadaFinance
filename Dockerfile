FROM python:3.11-slim

# Instalar dependencias del sistema (Poppler para PDF y tzdata para zona horaria)
RUN apt-get update && apt-get install -y \
    poppler-utils \
    gcc \
    libpq-dev \
    tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "src/main.py"]
