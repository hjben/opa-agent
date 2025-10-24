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
        self.prompts["rego_regen"] = (await self.mcp_client.get_prompt("opa_tools", "rego_regen_prompt"))[0].content
        self.prompts["opa_test"] = (await self.mcp_client.get_prompt("opa_tools", "opa_test_prompt"))[0].content

        self.agent = create_react_agent(model, tools, prompt=self.prompts["base"])
        print("✅ MCP Client initialized, prompts loaded")

    async def generate_and_validate(self, user_request: str, retry_limit: int = 3):
        """
        Generate OPA Rego policy and test code using LLM, validate via MCP Server.
        Retries up to `retry_limit` times if test fails.
        """

        print(f"Generating policy...")
        prompt_text = self.prompts["rego_gen"].format(user_request=user_request)

        # LLM 요청
        output_list = list()
        inputs = {"messages": prompt_text}
        async for chunk_msg, _ in self.agent.astream(inputs, stream_mode="messages"):
            if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
                output_list.append(chunk_msg.content)

        print(output_list)
        print("="*50)

        return {
                "success": True,
                "policy": output_list[-1]
            }


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

    result = await client_manager.generate_and_validate(user_request, retry_limit)
    return result

# ===============================
# Local Test
# ===============================
if __name__ == "__main__":
    async def local_test():
        await client_manager.initialize()
        result = await client_manager.generate_and_validate(
            "Allow managers to approve leave requests, deny everyone else",
            retry_limit=3
        )
        print(json.dumps(result, indent=2))

    asyncio.run(local_test())
