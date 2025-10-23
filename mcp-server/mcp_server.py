from mcp.server.fastmcp import FastMCP
# from service.mariadb import get_user_by_id, get_all_users
from service.opa import opa_test
from service.qdrant import QdrantService

# Qdrant 연결
qdrant = QdrantService(url="http://qdrant:6333")

# MCP Server 생성
mcp_server = FastMCP(name="opa_tools", host="0.0.0.0", port="8001", debug=True)


@mcp_server.prompt("base_prompt")
def get_agent_prompt() -> str:
    """
    Get a base prompt for the AI agent.
    """
    return "You're a helpful AI assistant that specialized in rego code generation."

@mcp_server.prompt("rego_gen_prompt")
def get_opa_gen_prompt() -> str:
    """
    Get a code-generate prompt.
    """
    return """
You are an expert in OPA (Open Policy Agent) policy authoring.
Generate a Rego policy that satisfies the following requirement:

{user_request}
"""

@mcp_server.prompt("rego_regen_prompt")
def get_opa_gen_prompt() -> str:
    """
    Get a code-regenerate prompt.
    """
    return """
The generated policy failed the opa test. Error message:
{stderr}
Please fix the issue and regenerate the policy.
"""


# -------------------------------
# 기능별 Tool 등록
# -------------------------------

# @mcp_server.tool("user")
# async def get_user_tool(data: dict):
#     emp_id = data.get("emp_id")
#     if emp_id:
#         return {"user": get_user_by_id(emp_id)}
#     return {"users": get_all_users()}

# -------------------------------
# Tool: Rego 코드 테스트
# -------------------------------

@mcp_server.tool("opa_test")
async def handle_opa_test(data: dict):
    """
    Tool Name: opa_test
    --------------------
    Description:
        This tool runs OPA (Open Policy Agent) unit tests on a given Rego policy code
        and a corresponding test file. It is designed to validate whether the generated
        policy logic behaves as expected.

    Expected Inputs (data: dict):
        {
            "rego_code": str,   # The main Rego policy code to be tested
            "test_rego": str    # The test file written in Rego to validate the policy
        }

    Behavior:
        - The function calls the `opa_test` utility, which executes OPA's built-in test command.
        - It captures whether the test succeeded or failed, along with the detailed OPA output.

    Returns:
        {
            "success": bool,     # True if all tests passed, False otherwise
            "opa_output": str    # Detailed OPA CLI test results (stdout/stderr)
        }

    Example Usage (from MCP client or agent):
        ```python
        result = await call_tool("opa_test", {
            "rego_code": "<generated policy code>",
            "test_rego": "<test cases for the policy>"
        })
        if result["success"]:
            print("All OPA tests passed successfully.")
        else:
            print("OPA test failed:", result["opa_output"])
        ```

    Notes:
        - This tool should be registered in the MCP server, and called remotely from the MCP client.
        - The MCP client may use this tool to verify the validity of generated Rego policies
          before returning them to end-users.
    """
    success, output = opa_test(data.get("rego_code"), data.get("test_rego"))
    return {"success": success, "opa_output": output}

# -------------------------------
# 서버 시작
# -------------------------------
if __name__ == "__main__":
    print("Starting MCP Server on port 8001...")
    mcp_server.run(transport="streamable-http")
