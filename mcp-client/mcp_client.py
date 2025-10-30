import re
import json
import asyncio
from fastapi import FastAPI, HTTPException
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

app = FastAPI(title="MCP OPA Client")

# ===============================
# MCP Client Manager Class
# ===============================
class MCPClientManager:
    def __init__(self, mcp_url: str, azure_endpoint: str, api_key: str, azure_deployment: str):
        self.mcp_url = mcp_url
        self.azure_endpoint = azure_endpoint
        self.api_key = api_key
        self.azure_deployment = azure_deployment
        self.api_version = "2024-02-15-preview"

        self.agent = None
        self.prompts = {}
        self.mcp_client = None

    @staticmethod
    def extract_rego_or_last_json(text: str):
        # "rego_code"로 시작해서 마지막 "}"까지 매칭하는 정규식
        # 중간의 중괄호나 개행, 따옴표 등은 모두 허용
        pattern = r'\{\s*"rego_code".*?"error_message"\s*:\s*".*?"\s*\}'
        
        matches = re.findall(pattern, text, flags=re.DOTALL)
        
        if not matches:
            return None

        last_json_str = matches[-1]

        try:
            # JSON 문자열의 내부에 이스케이프된 따옴표나 개행이 있을 수 있으므로
            # 불필요한 문자들을 안전하게 정리
            parsed_json = json.loads(last_json_str)
        except json.JSONDecodeError as e:
            print(f"[JSON 파싱 오류] {e}")
            return None

        # 필드 추출 (없을 경우 None)
        rego_code = parsed_json.get("rego_code")
        is_valid = parsed_json.get("is_valid")
        error_message = parsed_json.get("error_message")

        return {
            "rego_code": rego_code,
            "is_valid": is_valid,
            "error_message": error_message
        }
        
    async def initialize(self):
        """Initialize MCP client, load tools, prompts, and LLM agent."""
        model = AzureChatOpenAI(
            azure_endpoint=self.azure_endpoint,
            api_key=self.api_key,
            azure_deployment=self.azure_deployment,
            api_version=self.api_version
        )

        self.mcp_client = MultiServerMCPClient({
            "opa_tools": {
                "url": self.mcp_url,
                "transport": "streamable_http"
            }
        })

        tools = await self.mcp_client.get_tools()
        self.prompts["base"] = (await self.mcp_client.get_prompt("opa_tools", "base_prompt"))[0].content
        self.prompts["rego_gen"] = (await self.mcp_client.get_prompt("opa_tools", "rego_gen_prompt"))[0].content
        self.prompts["test_rego_gen"] = (await self.mcp_client.get_prompt("opa_tools", "test_rego_gen_prompt"))[0].content
        self.prompts["opa_test"] = (await self.mcp_client.get_prompt("opa_tools", "opa_test_prompt"))[0].content

        self.agent = create_react_agent(model, tools, prompt=self.prompts["base"])
        print("✅ MCP Client initialized, prompts loaded")

    async def generate_policy(self, user_request: str):
        """
        Generate OPA Rego policy and test code using LLM, validate via MCP Server.
        """

        print(f"Generating policy...")
        prompt_text = self.prompts["rego_gen"].format(user_request=user_request)

        # LLM 요청
        policy_json = ""
        inputs = {"messages": prompt_text}
        async for chunk_msg, _ in self.agent.astream(inputs, stream_mode="messages"):
            if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
                policy_json += chunk_msg.content

        print(policy_json)
        result = self.extract_rego_or_last_json(policy_json)
        print("="*50)

        return {
                "success": result["is_valid"],
                "policy": result["rego_code"],
                "error_message": result["error_message"]
            }
    
    async def test_policy(self, rego_code: str):
        """
        Generate OPA Rego policy and test code using LLM, validate via MCP Server.
        """

        print(f"Generating Test OPA policy...")
        prompt_text = self.prompts["test_rego_gen"].format(rego_code=rego_code)

        # LLM 요청
        policy_json = ""
        inputs = {"messages": prompt_text}
        async for chunk_msg, _ in self.agent.astream(inputs, stream_mode="messages"):
            if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
                policy_json += chunk_msg.content

        result = self.extract_rego_or_last_json(policy_json)
        print("="*50)
        print(result)


# ===============================
# FastAPI Startup
# ===============================
client_manager = MCPClientManager(
    mcp_url="http://localhost:8001/mcp/",
    azure_endpoint="https://skcc-atl-master-openai-01.openai.azure.com/",
    api_key="FpWkoIu3ZsP9VTrYqmxF8wEUzmAAXrqkTh28HxyX0JdyniQzsJRgJQQJ99BEACYeBjFXJ3w3AAABACOGGWOw",
    azure_deployment="gpt-4o"
)

@app.on_event("startup")
async def startup_event():
    await client_manager.initialize()

# ===============================
# FastAPI Endpoint
# ===============================
@app.post("/generate_policy")
async def generate_policy(request: dict):
    user_request = request.get("request")
    retry_limit = int(request.get("retry_limit", 3))

    if not user_request:
        raise HTTPException(status_code=400, detail="Missing 'request' field.")

    result = await client_manager.generate_policy(user_request, retry_limit)

    return result

# ===============================
# Local Test
# ===============================
if __name__ == "__main__":
    async def local_test():
        await client_manager.initialize()
        gen_result = await client_manager.generate_policy(
            "관리자는 언제든 접근 가능하고, 일반 사용자는 근무시간 중 자신의 리소스만 수정할 수 있는 정책을 만들어줘.",
        )

        rego_code = gen_result["policy"]
        
        test_result = await client_manager.test_policy(
            rego_code
        )
        
        print(json.dumps(test_result, indent=2))

    asyncio.run(local_test())
