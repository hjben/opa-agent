import json, asyncio

from fastapi import FastAPI, HTTPException
from langchain_openai import AzureChatOpenAI
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

# -------------------------------
# FastAPI 앱 생성
# -------------------------------
app = FastAPI(title="MCP Client API")


async def init_client():
    model = AzureChatOpenAI(
        azure_endpoint="https://skcc-atl-master-openai-01.openai.azure.com/",
        api_key="dummy_key",
        azure_deployment="gpt-4o",
        api_version='2024-02-15-preview'
    )

    client = MultiServerMCPClient({
        "opa_tools": {
            "url": "http://localhost:8001/mcp/",
            "transport": "streamable_http"
        }
    })

    tools = await client.get_tools()
    print("Available Tools")
    print(tools)

    prompt = await client.get_prompt(server_name="opa_tools", prompt_name="agent_prompt")
    print("Client Prompt")
    print(prompt[0].content)

    return create_react_agent(model, tools, prompt=prompt[0].content)

async def test_agent():
    agent = await init_client()

    user_request = "Test input"
    inputs = {"messages": user_request}
    print(inputs)
    async for chunk_msg, metadata in agent.astream(inputs, stream_mode="messages"):
        if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
            print(chunk_msg.content, end="", flush=True)

        else:
            print(chunk_msg, end="", flush=True)


# -------------------------------
# FastAPI 엔드포인트
# -------------------------------
@app.post("/generate_policy")
async def generate_policy(request: dict):
    user_request = request.get("request")
    if not user_request:
        raise HTTPException(status_code=400, detail="Missing 'request' field (natural language request)")

    # 1️⃣ 자연어 요청 → 구성요소 추출
    structured_req = dict()

    # 2️⃣ MCP 서버 연결
    agent = init_client()

    inputs = {"messages": user_request}
    async for chunk_msg, metadata in agent.astream(inputs, stream_mode="messages"):
        if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
            print(chunk_msg.content, end="", flush=True)

        else:
            print(chunk_msg, end="", flush=True)

if __name__=="__main__":
    asyncio.run(test_agent())