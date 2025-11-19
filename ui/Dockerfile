FROM python:3.11-slim

WORKDIR /app

COPY ./ui/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY ../config ./config

CMD ["streamlit", "run", "/app/ui/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
