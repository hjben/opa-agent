import json, asyncio
from contextlib import AsyncExitStack
from fastapi import FastAPI, HTTPException
from mcp.client.stdio import stdio_client
from mcp import ClientSession, StdioServerParameters

# -------------------------------
# FastAPI 앱 생성
# -------------------------------
app = FastAPI(title="MCP Client API (stdio-based)")

# -------------------------------
# 서버 연결 및 ClientSession 초기화
# -------------------------------
async def get_mcp_session():
    # MCP 서버 설정 파일
    with open("mcp_server_config.json") as f:
        config = json.load(f)["mcpServers"]["filesystem"]

    server_params = StdioServerParameters(
        command=config["command"],
        args=config["args"],
        env=None
    )

    stack = AsyncExitStack()
    async with stack:
        stdio, write = await stack.enter_async_context(stdio_client(server_params))
        session = await stack.enter_async_context(ClientSession(stdio, write))
        await session.initialize()
        yield session

# -------------------------------
# MCP Tool 호출 함수
# -------------------------------
async def fetch_user(emp_id: str):
    async for session in get_mcp_session():
        resp = await session.call_tool("user", {"emp_id": emp_id})
        return resp

async def fetch_qdrant(query_vector: list, collection_name="context", limit=5):
    async for session in get_mcp_session():
        resp = await session.call_tool("qdrant", {
            "query_vector": query_vector,
            "collection_name": collection_name,
            "limit": limit
        })
        return resp

async def validate_opa(rego_code: str):
    async for session in get_mcp_session():
        resp = await session.call_tool("opa", {"rego_code": rego_code})
        return resp

# -------------------------------
# FastAPI 엔드포인트
# -------------------------------
@app.post("/generate_policy")
async def generate_policy(request: dict):
    emp_id = request.get("emp_id")
    if not emp_id:
        raise HTTPException(status_code=400, detail="emp_id is missing")

    # 1. 사용자 정보 조회
    user_resp = await fetch_user(emp_id)
    user_data = user_resp.get("user_data")

    # 2. Qdrant 검색 (예시 벡터 사용)
    query_vector = [0.0] * 1536
    qdrant_resp = await fetch_qdrant(query_vector)
    context = qdrant_resp.get("context")

    # 3. Rego 코드 생성 및 OPA 검증
    sample_rego = f"""
package example.policy

default allow = false

allow {{
    input.user == "{user_data['emp_id']}"
}}
"""
    opa_resp = await validate_opa(sample_rego)
    validated_rego = opa_resp.get("validated_rego")

    # 최종 결과 반환
    return {
        "status": "success",
        "user_data": user_data,
        "context": context,
        "validated_rego": validated_rego
    }
