FROM python:3.11-slim

WORKDIR /app

COPY ./mcp-server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ./mcp-server /app
COPY ../data/opa/ /data/opa/

RUN chmod +x /app/setup_opa.sh

# Run OPA setup
RUN bash /app/setup_opa.sh

EXPOSE 8001
CMD ["python", "mcp_server.py"]