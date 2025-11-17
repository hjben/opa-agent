import ast
import json
import re

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

        self.prompts_list = ["base", "analyze_request", "get_policy_info", "rego_gen"]

    @staticmethod
    def parse_result(text: str):
        """
        Safely extract content from a single ```json or ```markdown block.
        Handles cases where ``` may appear inside the block.
        The trailing ``` is removed.

        Args:
            text (str): Input string containing either a JSON or Markdown code block.

        Returns:
            dict:
                - If ```json: parsed JSON object
                - If ```markdown: {"content": <text>}
            None if no matching block found.
        """
        # 우선 블록 시작 위치 찾기
        json_start = text.find("```json")
        md_start = text.find("```markdown")

        if json_start != -1:
            # 마지막 ``` 위치 찾기
            end_pos = text.rfind("```")
            if end_pos <= json_start:
                return None
            json_text = text[json_start + len("```json"):end_pos].strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                print(e)
                return None

        if md_start != -1:
            end_pos = text.rfind("```")
            if end_pos <= md_start:
                return None
            md_text = text[md_start + len("```markdown"):end_pos].strip()
            return {"content": md_text}

        return None

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
@app.post("/user_request")
async def process_user_request(request: dict):
    """
    Analyze user request and choose the proper API
    """
    user_query = request.get("query")

    if not user_query:
        raise HTTPException(status_code=400, detail="Missing 'request' field.")

    result = await client_manager.llm_call(client_manager.prompts["request_analyze"])

    # TODO: 분류 결과 별 API 호출
    res = result

    return {
        "status": "success",
        "response": res
    }

@app.post("/get_policy_info")
async def get_policy(request: dict):
    """
    Get current policie(s) information in OPA system.
    """
    user_query = request.get("query")

    llm_text = await client_manager.llm_call(
        client_manager.prompts["get_policy_info"].format(user_query=user_query)
    )
    res_json = client_manager.parse_result(llm_text)
    print(res_json)

    return {
        "status": "success",
        "response": res_json
    }

@app.post("/generate_policy")
async def generate_policy(request: dict):
    """
    Generate OPA policy, test policy, run OPA test, and produce summary output.
    """
    user_query = request.get("query")

    print(f"Generating policy...")
    result = await client_manager.llm_call(client_manager.prompts["rego_gen"].format(user_query=user_query))
    print(result)
    parsed_result = client_manager.parse_result(result)
    print(parsed_result)

    return parsed_result

