FROM python:3.11-slim

WORKDIR /app

COPY ./mcp-client/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./mcp-client .
COPY ./mariadb ./mariadb
COPY ./config ./config

CMD ["uvicorn", "mcp_client:app", "--host", "0.0.0.0", "--port", "8000"]
