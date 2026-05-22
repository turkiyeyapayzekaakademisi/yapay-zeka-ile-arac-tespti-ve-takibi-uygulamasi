# ==============================================

# Adımlar:
# 1. Base image seçimi
# 2. Sistem bağımlıklarının yüklenmesi
# 3. Çalışma dizininin ayarlanması
# 4. Python bağımlılıklarının yüklenmesi
# 5. Uygulama kodunun kopyalanması
# 6. Port'u dışa aç
# 7. Başlatma komutunun ayarlanması

# ==============================================

FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/list/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]