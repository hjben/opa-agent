import ast
import json
import asyncio

from typing import Optional, Dict
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

        self.prompts_list = ["base", "rego_gen", "test_rego_gen", "opa_test", "opa_summary"]

    @staticmethod
    def extract_result(text: str) -> Optional[Dict]:
        """
        Scan `text`, find top-level {...} JSON blocks robustly (ignoring braces inside strings),
        parse them and return the last successfully parsed JSON-like object (as dict).
        If none parse, return None.
        """
        blocks = []
        brace_level = 0
        start_idx = None
        in_string = False
        string_char = None   # either '"' or "'"
        escape = False

        for i, ch in enumerate(text):
            # Handle string toggling and escapes
            if ch == '"' or ch == "'":
                if not escape:
                    if not in_string:
                        in_string = True
                        string_char = ch
                    elif string_char == ch:
                        in_string = False
                        string_char = None
                # else: quote escaped -> ignore
                escape = False
                # If inside string, chars don't affect brace_level
                if brace_level > 0:
                    continue
                else:
                    continue
            elif ch == "\\":
                # toggle escape for next char
                escape = not escape
                # continue loop (do not reset escape here, next iteration handles)
                continue
            else:
                # reset escape if previous char was backslash (and current not another backslash)
                escape = False

            # If not inside string, track braces
            if not in_string:
                if ch == "{":
                    if brace_level == 0:
                        start_idx = i
                    brace_level += 1
                elif ch == "}":
                    if brace_level > 0:
                        brace_level -= 1
                        if brace_level == 0 and start_idx is not None:
                            block = text[start_idx:i+1]
                            blocks.append(block)
                            start_idx = None
                    # else: unmatched closing brace — ignore
            # else: inside string, ignore braces

        if not blocks:
            print(text)
            return None

        # Try to parse blocks from last to first (so we can return the last valid)
        for raw in reversed(blocks):
            s = raw.strip()
            # quick cleanup: sometimes LLM injects weird backticks around blocks; remove leading/trailing backticks
            if s.startswith("```") and s.endswith("```"):
                # remove fencing, keep inner
                inner = s.strip("`")
                s = inner.strip()

            # Attempt JSON parsing
            try:
                parsed = json.loads(s)
                return parsed
            except json.JSONDecodeError:
                # Try python literal eval (accepts single quotes etc.)
                try:
                    parsed = ast.literal_eval(s)
                    # ensure it's a dict-like result
                    if isinstance(parsed, dict):
                        return parsed
                except Exception:
                    pass

                # Last resort: try heuristic fixes (replace single quotes -> double quotes, True/False -> true/false)
                try:
                    heur = s.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")
                    parsed = json.loads(heur)
                    return parsed
                except Exception:
                    # parsing failed for this block, continue to previous block
                    continue

        # No block parsed successfully
        print(text)
        return None
        
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

        for prompt in self.prompts_list:
            self.prompts[prompt] = (await self.mcp_client.get_prompt("opa_tools", f"{prompt}_prompt"))[0].content

        self.agent = create_react_agent(model, tools, prompt=self.prompts["base"])
        print("✅ MCP Client initialized, prompts loaded")

    async def llm_call(self, prompt: str):
        result = ""
        async for chunk_msg, _ in self.agent.astream({"messages": prompt}, stream_mode="messages"):
            if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
                result += chunk_msg.content

        return result

    async def generate_policy(self, user_request: str):
        """
        Generate OPA Rego policy and test code using LLM, validate via MCP Server.
        """
        llm_text = await self.llm_call(self.prompts["rego_gen"].format(user_request=user_request))
        result_json = self.extract_result(llm_text)

        return {
            "policy": result_json.get("rego_code"),
            "is_valid": result_json.get("is_valid"),
            "error_message": result_json.get("error_message")
            }
    
    async def generate_test_policy(self, rego_code: str):
        """
        Generate OPA Rego policy and test code using LLM, validate via MCP Server.
        """
        llm_text = await self.llm_call(self.prompts["test_rego_gen"].format(rego_code=rego_code))
        result_json = self.extract_result(llm_text)

        return {
            "policy": result_json.get("rego_code"),
            "is_valid": result_json.get("is_valid"),
            "error_message": result_json.get("error_message")
            }
    
    async def opa_test(self, policy_code: str, test_code: str):
        """
        Test OPA Rego policy with given policy code and test code.
        """
        llm_text = await self.llm_call(self.prompts["opa_test"].format(policy_code=policy_code, test_code=test_code))
        result_json = self.extract_result(llm_text)
        
        return {
            "validation": result_json.get("validation"),
            "validation_msg": result_json.get("validation_msg")
            }
    
    async def opa_summary(self, policy_code, test_code, validation_msg):
        """
        Generate final output to End User.
        """
        llm_text = await self.llm_call(self.prompts["opa_summary"].format(policy_code=policy_code, test_code=test_code, validation_result=validation_msg))

        return llm_text

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
    """
    Generate OPA policy, test policy, run OPA test, and produce summary output.
    """
    user_query = request.get("query")

    if not user_query:
        raise HTTPException(status_code=400, detail="Missing 'request' field.")

    # 1️⃣ OPA Policy 생성
    print(f"Generating policy...")
    gen_result = await client_manager.generate_policy(user_query)
    print(gen_result)

    rego_code = gen_result["policy"]

    # 2️⃣ OPA Test Policy 생성
    print(f"Generating test policy...")
    test_gen_result = await client_manager.generate_test_policy(rego_code)
    test_code = test_gen_result["policy"]

    # 3️⃣ OPA Test 실행
    test_result = await client_manager.opa_test(rego_code, test_code)

    # 4️⃣ LLM 호출로 요약 결과 생성
    final_result = await client_manager.llm_call(
        client_manager.prompts["opa_summary"].format(
            policy_code=rego_code,
            test_code=test_code,
            validation_result=test_result.get("validation_msg", "")
        )
    )

    # 5️⃣ 최종 응답
    return {
        "status": "success",
        "policy": rego_code,
        "test_policy": test_code,
        "opa_test_result": test_result,
        "summary": final_result
    }

@app.post()
async def generate_policy(request: dict):
    """
    Generate OPA policy, test policy, run OPA test, and produce summary output.
    """
    user_query = request.get("query")

    if not user_query:
        raise HTTPException(status_code=400, detail="Missing 'request' field.")

    # 1️⃣ OPA Policy 생성
    print(f"Generating policy...")
    gen_result = await client_manager.generate_policy(user_query)
    print(gen_result)

    rego_code = gen_result["policy"]

    # 2️⃣ OPA Test Policy 생성
    print(f"Generating test policy...")
    test_gen_result = await client_manager.generate_test_policy(rego_code)
    test_code = test_gen_result["policy"]

    # 3️⃣ OPA Test 실행
    test_result = await client_manager.opa_test(rego_code, test_code)

    # 4️⃣ LLM 호출로 요약 결과 생성
    final_result = await client_manager.llm_call(
        client_manager.prompts["opa_summary"].format(
            policy_code=rego_code,
            test_code=test_code,
            validation_result=test_result.get("validation_msg", "")
        )
    )

    # 5️⃣ 최종 응답
    return {
        "status": "success",
        "policy": rego_code,
        "test_policy": test_code,
        "opa_test_result": test_result,
        "summary": final_result
    }

# ===============================
# Local Test
# ===============================
if __name__ == "__main__":
    async def local_test():
        await client_manager.initialize()
        gen_result = await client_manager.generate_policy(
            "관리자는 언제든 접근 가능하고, 일반 사용자는 근무시간 중 자신의 리소스만 수정할 수 있는 정책을 만들어줘.",
        )
        print(f"Generating policy...")
        rego_code = gen_result["policy"]
        print(rego_code)

        print(f"Generating Test OPA policy...")
        test_gen_result = await client_manager.generate_test_policy(rego_code)
        test_code = test_gen_result["policy"]
        print(test_code)

        print(f"Testing OPA policy...")
        test_result = await client_manager.opa_test(rego_code, test_code)
        print(json.dumps(test_result, indent=2))

        print(f"Generating outputs...")
        final_result = await client_manager.llm_call(client_manager.prompts["opa_summary"].format(policy_code=rego_code, test_code=test_code, validation_result=test_result["validation_msg"]))

        print(final_result)

    asyncio.run(local_test())
