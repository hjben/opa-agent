from fastapi import FastAPI, HTTPException
from mcp_client import handle_request

app = FastAPI(title="MCP Client API")

@app.post("/generate_policy")
async def generate_policy(request: dict):
    query = request.get("query")
    emp_id = request.get("emp_id")
    if not query:
        raise HTTPException(status_code=400, detail="Query is missing")
    try:
        result = await handle_request(query, emp_id=emp_id)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
