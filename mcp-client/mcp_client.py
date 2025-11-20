import ast
import json
import requests
import os

from typing import Optional, Dict
from fastapi import FastAPI, HTTPException, Body
from langchain_openai import AzureChatOpenAI
from langgraph.prebuilt import create_react_agent
from langchain_mcp_adapters.client import MultiServerMCPClient

from mariadb.db_connection import db_cursor
from config.url_config import OPA_DATA_URL, OPA_POLICY_URL
from config.base_config import context_window

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

        self.prompts_list = ["base", "opa_orchestrator", "get_policy", "rego_gen", "rego_update"]

    @staticmethod
    def parse_result(text: str):
        json_start = text.find("```json")
        md_start = text.find("```markdown")

        if json_start != -1:
            end_pos = text.rfind("```")
            if end_pos <= json_start:
                print("parse_result: invalid json block position")
                return None
            json_text = text[json_start + len("```json"):end_pos].strip()
            try:
                return json.loads(json_text)
            except json.JSONDecodeError as e:
                print("parse_result: JSON decode error:", e)
                return None

        if md_start != -1:
            end_pos = text.rfind("```")
            if end_pos <= md_start:
                print("parse_result: invalid markdown block position")
                return None
            md_text = text[md_start + len("```markdown"):end_pos].strip()
            return {"content": md_text}

        print("parse_result: no json/markdown block found")
        return None

    @staticmethod
    def extract_last_json(text: str) -> Optional[Dict]:
        blocks = []
        brace_level = 0
        start_idx = None
        in_string = False
        string_char = None
        escape = False

        for i, ch in enumerate(text):
            if ch in ['"', "'"]:
                if not escape:
                    if not in_string:
                        in_string = True
                        string_char = ch
                    elif string_char == ch:
                        in_string = False
                        string_char = None
                escape = False
                continue
            elif ch == "\\":
                escape = not escape
                continue
            else:
                escape = False

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

        if not blocks:
            print("extract_last_json: no blocks found")
            return None

        for raw in reversed(blocks):
            s = raw.strip()
            try:
                return json.loads(s)
            except Exception:
                pass
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                pass
            try:
                heur = s.replace("'", '"').replace("True", "true").replace("False", "false").replace("None", "null")
                return json.loads(heur)
            except Exception:
                continue

        print("extract_last_json: failed to parse JSON")
        return None

    async def initialize(self):
        print("Initializing MCP Client...")

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

        print("Loading MCP tools...")
        tools = await self.mcp_client.get_tools()

        print("Loading prompts...")
        for prompt in self.prompts_list:
            self.prompts[prompt] = (await self.mcp_client.get_prompt("opa_tools", f"{prompt}_prompt"))[0].content
            print(f"Loaded prompt: {prompt}")

        print("Creating agent...")
        self.agent = create_react_agent(model, tools, prompt=self.prompts["base"])
        print("MCP Client initialized!")

    async def llm_call(self, prompt: str):
        print("\n================ LLM CALL START ================")
        print("Prompt sent to LLM:\n", prompt[:500], "...\n")

        result = ""

        async for chunk_msg, _ in self.agent.astream({"messages": prompt}, stream_mode="messages"):
            if hasattr(chunk_msg, "tool_calls") and chunk_msg.tool_calls:
                for call in chunk_msg.tool_calls:
                    print(f"LLM is calling Tool: {call.get('name')} with args {call.get('args')}")

            if hasattr(chunk_msg, "content") and isinstance(chunk_msg.content, str):
                result += chunk_msg.content

        print("LLM response collected (first 400 chars):")
        print(result[:400], "...\n")
        print("================ LLM CALL END ==================\n")

        return result

client_manager = MCPClientManager(
    mcp_url="http://mcp-server:8001/mcp/",
    azure_endpoint="https://skcc-atl-master-openai-01.openai.azure.com/",
    api_key="",
    azure_deployment="gpt-4o"
)

@app.on_event("startup")
async def startup_event():
    await client_manager.initialize()

@app.post("/chat")
async def opa_chat(request: dict = Body(...)):
    print("\n============== NEW REQUEST ==============")
    print("Incoming request:", request)

    messages = request.get("messages")
    if not messages or len(messages) == 0:
        raise HTTPException(status_code=400, detail="Missing 'messages' field.")

    recent_messages = messages[-context_window:]

    user_query = ""
    for msg in recent_messages:
        role = msg.get("role")
        content = msg.get("content", "")
        if content:
            user_query += f"{role.capitalize()}: {content}\n"

    print("Constructed user_query:\n", user_query)

    try:
        print("Calling Orchestrator...")
        clsf_result = await client_manager.llm_call(
            client_manager.prompts["opa_orchestrator"].format(user_query=user_query)
        )
        print("Orchestrator raw output:\n", clsf_result)

        clsf_json = client_manager.parse_result(clsf_result)
        if not clsf_json:
            print("parse_result failed, trying extract_last_json...")
            clsf_json = client_manager.extract_last_json(clsf_result)

        print("Parsed orchestrator JSON:", clsf_json)

        final_res = ""
        policy_code = ""

        for task in clsf_json.get("tasks", []):
            print(f"Executing Task: {task}")

            if task.get("target_prompt") is not None:
                target_prompt = client_manager.prompts[task["target_prompt"].replace("_prompt", "")]

                if len(policy_code) != 0:
                    task["params"]["policy_code"] = policy_code

                print(f"Sending task prompt: {task['target_prompt']}")
                llm_text = await client_manager.llm_call(target_prompt.format(**task["params"]))
                print("Task output:\n", llm_text)

                res_json = client_manager.parse_result(llm_text)
                if not res_json:
                    print("parse_result failed for task, trying extract_last_json...")
                    res_json = client_manager.extract_last_json(llm_text)

                print("Parsed task JSON:", res_json)

                if task.get("category") == "B":
                    policy_code = res_json.get("policy_code", "")
                else:
                    policy_code = ""

                final_res += res_json.get("content", "") + '\n'

        if len(final_res) == 0:
            final_res = clsf_json.get("notes", "No content generated.")

        print("Final response sent to client:\n", final_res)

        return {
            "status": "success",
            "content": final_res
        }

    except Exception as e:
        print("Exception occurred:", e)
        return {
            "status": "fail",
            "content": str(e)
        }



@app.get("/sync")
def sync_all_to_opa():
    try:
        # 1. 사용자 정보 동기화
        users_data = {}
        with db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT * FROM user")
            for u in cursor.fetchall():
                users_data[u["emp_id"]] = {
                    "name": u["name"],
                    "dept": u["dept"],
                    "is_admin": bool(u["is_admin"])
                }
        resp_users = requests.put(f"{OPA_DATA_URL}/users", json=users_data)
        if resp_users.status_code != 204:
            raise HTTPException(status_code=500, detail=f"Failed to update users in OPA: {resp_users.text}")

        # 2. 리소스 소유자 동기화
        resources_data = {}
        with db_cursor(dictionary=True) as cursor:
            cursor.execute("SELECT resource_id, owner FROM dummy_resource")
            for r in cursor.fetchall():
                resources_data[r["resource_id"]] = r["owner"]
        resp_resources = requests.put(f"{OPA_DATA_URL}/resource_owners", json=resources_data)
        if resp_resources.status_code != 204:
            raise HTTPException(status_code=500, detail=f"Failed to update resources in OPA: {resp_resources.text}")

        # 3. rego 정책 파일 OPA에 업로드
        policy_dir = "/app/policy"
        for filename in os.listdir(policy_dir):
            if filename.endswith(".rego"):
                with open(os.path.join(policy_dir, filename), "r") as f:
                    rego_code = f.read()

                resp_policy = requests.put(
                    f'{OPA_POLICY_URL}/{filename.replace(".rego", "")}',
                    data=rego_code,
                    headers={"Content-Type": "text/plain"}
                )

                if resp_policy.status_code not in (200, 204):
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to upload policy {filename}: {resp_policy.text}"
                    )

        return {
            "message": "Users, resource owners, and policies synced to OPA successfully",
            "user_count": len(users_data),
            "resource_count": len(resources_data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sync failed: {e}")