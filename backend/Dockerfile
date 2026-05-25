FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends webp && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ app/
COPY static/ static/

RUN find static/images -name '*.png' -exec sh -c 'cwebp -q 95 -m 6 -quiet "$0" -o "${0%.png}.webp"' {} \;

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
