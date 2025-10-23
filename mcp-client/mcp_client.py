import json, asyncio, httpx
from fastapi import FastAPI, HTTPException
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

app = FastAPI(title="MCP OPA Client")

# -------------------------------
# 1️⃣ MCP 클라이언트 초기화
# -------------------------------
async def init_client():
    model = AzureChatOpenAI(
        azure_endpoint="https://skcc-atl-master-openai-01.openai.azure.com/",
        api_key="",
        azure_deployment="gpt-4o",
        api_version="2024-02-15-preview"
    )

    client = MultiServerMCPClient({
        "opa_tools": {
            "url": "http://localhost:8001/mcp/",
            "transport": "streamable_http"
        }
    })

    tools = await client.get_tools()
    prompt = await client.get_prompt(server_name="opa_tools", prompt_name="base_prompt")
    return create_react_agent(model, tools, prompt=prompt[0].content)


# -------------------------------
# 2️⃣ OPA 정책 생성 및 검증 루프
# -------------------------------
async def generate_and_validate(agent, user_request: str, retry_limit: int = 3):
    """
    1. LLM이 정책 및 테스트 코드 생성
    2. MCP Server로 opa test 실행
    3. 실패 시 stderr를 LLM에게 전달 → 수정된 정책 재생성
    """
    async with httpx.AsyncClient() as client:
        policy_code, test_code = None, None

        for attempt in range(1, retry_limit + 1):
            print(f"\n[Attempt {attempt}/{retry_limit}] Generating policy...")

            # 1️⃣ 프롬프트 구성
            if attempt == 1:
                gen_prompt = f"""
                Generate a valid OPA Rego policy and a corresponding test file based on this request and validate it.
                "{user_request}"

                
                When testing the policy, use the rego policy code and test code as input 
                Expected Inputs (data: dict):
                {{
                    "rego_code": str,   # The main Rego policy code to be tested
                    "test_rego": str    # The test file written in Rego to validate the policy
                }}

                Return JSON with this format without any comments:
                {{
                    "policy": "<rego policy code>",
                    "test": "<rego test code>",
                    "validation": True/False,
                    "validataion_msg": "<messages from validation process>"
                }}
                """
            else:
                gen_prompt = f"""
                The previous OPA policy failed testing.
                Fix the following issues based on the error log below, and regenerate a corrected policy and test file.

                Error message:
                ```
                {last_error_log}
                ```

                Return JSON with this format without any comments:
                {{
                    "policy": "<fixed rego policy>",
                    "test": "<updated test policy>",
                    "validation": True/False,
                    "validataion_msg": "<messages from validation process>"
                }}
                """

            # 2️⃣ LLM으로 정책 생성 요청
            inputs = {"messages": gen_prompt}
            policy_json = ""

            async for chunk_msg, _ in agent.astream(inputs, stream_mode="messages"):
                if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
                    policy_json += chunk_msg.content

            print(policy_json)

            # 3️⃣ JSON 파싱
            try:
                parsed = json.loads(policy_json)
                policy_code = parsed["policy"]
                test_code = parsed["test"]
                validation = parsed["validation"]
                validation_msg = parsed["validation_msg"]
            except Exception as e:
                print(f"JSON parsing error: {e}")
                last_error_log = f"Invalid JSON response from LLM. {e}"
                continue

            if validation:
                print("✅ OPA test passed successfully!")
                return {
                    "success": True,
                    "attempts": attempt,
                    "policy": policy_code,
                    "test": test_code
                }

            # 5️⃣ 실패 시 로그를 LLM에 전달
            last_error_log = validation_msg
            print(f"❌ OPA test failed (Attempt {attempt})\n{last_error_log}")

        # 모든 시도 실패
        return {
            "success": False,
            "attempts": retry_limit,
            "error": "Failed to generate a valid OPA policy after multiple attempts.",
            "last_error_log": last_error_log if 'last_error_log' in locals() else "No log"
        }


# -------------------------------
# 3️⃣ FastAPI 엔드포인트
# -------------------------------
@app.post("/generate_policy")
async def generate_policy(request: dict):
    user_request = request.get("request")
    retry_limit = int(request.get("retry_limit", 3))

    if not user_request:
        raise HTTPException(status_code=400, detail="Missing 'request' field.")

    agent = await init_client()
    result = await generate_and_validate(agent, user_request, retry_limit)
    return result


# -------------------------------
# 4️⃣ 로컬 테스트 실행용
# -------------------------------
if __name__ == "__main__":
    import uvicorn

    async def local_test():
        agent = await init_client()
        result = await generate_and_validate(
            agent,
            user_request="Allow managers to approve leave requests but deny everyone else",
            retry_limit=1
        )
        print(json.dumps(result, indent=2))

    asyncio.run(local_test())
    # 또는 서버 실행 시:
    # uvicorn.run(app, host="0.0.0.0", port=8000)
