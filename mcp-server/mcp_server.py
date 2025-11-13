from mcp.server.fastmcp import FastMCP
from service.mariadb import get_user_by_id, get_all_users
# from service.qdrant import QdrantService

import os
import tempfile
import subprocess

# Qdrant 연결
# qdrant = QdrantService(url="http://qdrant:6333")

# MCP Server 생성
mcp_server = FastMCP(name="opa_tools", host="0.0.0.0", port="8001", debug=True)


# -------------------------------
# Prompts
# -------------------------------
@mcp_server.prompt("base_prompt")
def get_agent_prompt() -> str:
    """
    Get a base prompt for the AI agent.
    """
    return "You are an OPA (Open Policy Agent) policy generator."

@mcp_server.prompt("rego_gen_prompt")
def get_rego_gen_prompt() -> str:
    """
    Get a rego code-generate prompt.
    """
    return """
Generate a valid OPA Rego policy based on the request below.

[User request]
{user_request}

Rules:
- Ensure the policy follows valid Rego syntax (with 'opa check' command).
- If the generated code is not valid, re-generate code.
- `if` keyword is required before the rule body starts.
- Do not include explanations or comments.
- Output must be a JSON only.

[Example]
```
package authz

allow if {{
	input.path == ["users"]
	input.method == "POST"
}}

allow if {{
	input.path == ["users", input.user_id]
	input.method == "GET"
}}
```
"""

@mcp_server.prompt("test_rego_gen_prompt")
def get_test_rego_gen_prompt() -> str:
    """
    Get a test rego code-generate prompt.
    """
    return """
Generate a valid rego code to test the code below.

[Rego code]
{rego_code}

Rules:
- Ensure the test code follows valid Rego syntax (with 'opa check' command).
- If the generated code is not valid, re-generate code.
- `if` keyword is required before the rule body starts.
- Don't use '_' variable in test code because it's unsafe.
- Do not include explanations or comments.
- Output must be a JSON only.

[Example]
package authz_test

import data.authz

test_post_allowed if {{
	authz.allow with input as {{"path": ["users"], "method": "POST"}}
}}

test_get_anonymous_denied if {{
	not authz.allow with input as {{"path": ["users"], "method": "GET"}}
}}

test_get_user_allowed if {{
	authz.allow with input as {{"path": ["users", "bob"], "method": "GET", "user_id": "bob"}}
}}

test_get_another_user_denied if {{
	not authz.allow with input as {{"path": ["users", "bob"], "method": "GET", "user_id": "alice"}}
}}
"""

@mcp_server.prompt("opa_test_prompt")
def get_opa_test_prompt() -> str:
    """
    Get a opa test prompt.
    """
    return """
Test the policy with the policy code and test code as input, using 'opa_test' tool.
Policy code is the main rego code to be tested, and test code is to test the policy.
[Policy code]
{policy_code}

[Test code]
{test_code}

Output must be consisted of JSON only, with two keys below:
    "validation": True/False,
    "validation_msg": "test result message"
"""


@mcp_server.prompt("opa_summary_prompt")
def get_opa_summary_prompt() -> str:
    """
    Summarize the OPA policy generation and validation results.
    """
    return """
Summarize the OPA policy generation and validation results clearly and concisely.

[Policy code]
{policy_code}

[Test code]
{test_code}

[Test result]
{validation_result}

Context:
- The user requested a specific API access control policy.
- You generated Rego policy code and a corresponding test file.
- The policy syntax was checked and validated using OPA tools.
- The test results indicate whether the policy logic works as intended.

Output Format:
Provide a short summary including:
1. A one-line description of the policy goal.
2. Whether the syntax check passed or failed.
3. Whether the OPA tests passed or failed.
4. A brief explanation of any detected issue or final validation success.
5. Full-text of the Policy code and test code, and the test result.

Rules:
- The request is made of Korean, your output must be in Korean.
- Present the summary, policy code, test code, and test results in a visually clean and natural format.
- Keep indentation, spacing, and newlines for readability.
- Output plain text only (no JSON).
- Keep the tone concise and professional.

Example output:
"The generated policy controls user access based on roles and time. Syntax and tests passed successfully."
"""


# -------------------------------
# Tool: Rego 코드 테스트
# -------------------------------
@mcp_server.tool("opa_check")
async def opa_check(rego_code):
    """
    Tool Name: opa_check
    --------------------
    Description:
        Validates the syntax of a given OPA (Open Policy Agent) Rego policy code.

        This tool ensures that the provided Rego code follows valid syntax rules
        as defined by the OPA compiler. It does not execute or test the logic of the policy —
        only the correctness of the code structure and grammar.

        The function temporarily writes the given Rego code to a `.rego` file
        and runs the `opa check` CLI command to verify its syntax.
        If the command returns a zero exit code, the code is syntactically valid.

        This tool is particularly useful before running OPA unit tests or deploying
        Rego policies to production environments, as it prevents invalid code
        from being evaluated or executed.

    Args:
        rego_code: str
            The OPA policy code as a string. This should contain valid Rego language syntax.

    Returns (JSON):
        {
            "reto_code": str
                - The input rego code

            "is_valid": bool
                - True if the syntax check passed (valid Rego code)
                - False if syntax errors were detected

            "error_message": str
                - An empty string if valid
                - The compiler error message returned by OPA if invalid
        }
    """
    is_valid = False
    error_message = ""
    try:
        # 임시 파일에 정책 저장
        with tempfile.NamedTemporaryFile(mode="w", suffix=".rego", delete=False) as tmp:
            tmp.write(rego_code)
            tmp_path = tmp.name

        # opa check 실행
        result = subprocess.run(
            ["opa", "check", tmp_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            is_valid = True
        else:
            error_message = result.stderr.strip()

    except Exception as e:
        error_message = str(e)

    return {"rego_code": rego_code, "is_valid": is_valid, "error_message": error_message}

@mcp_server.tool("opa_test")
async def opa_test(policy_code, test_code):
    """
    Tool Name: opa_test
    --------------------
    Description:
        Executes OPA unit tests to validate a given Rego policy against its test definitions.

        This tool runs the `opa test` command on two Rego files:
        - The main policy file (policy_code)
        - The test file containing assertions and expected outcomes (test_code)

        The purpose of this tool is to verify that the logic in the policy behaves
        as intended by executing declarative test cases written in Rego.
        Each test case evaluates specific input data and checks whether the policy produces
        the expected decision output.

        The function automatically writes both Rego sources into temporary files,
        executes the OPA test runner, and captures the detailed CLI output.
        It returns a structured JSON result indicating whether all tests passed or failed,
        along with the OPA output (including any stack traces or failure reasons).

    Args:
        policy_code: str
            The main Rego policy logic to be validated.
        test_code: str
            A Rego test file that defines unit tests using OPA's `test_` naming convention.

    Returns (JSON):
        {
            "status": str
                - "success": All tests passed successfully.
                - "fail": One or more tests failed.
                - "error": An internal error occurred while executing the test.

            "detail": str
                - Detailed stdout/stderr output from the OPA CLI.
                  Includes test result summaries, failure details, or syntax error traces.
        }
    """
    if not policy_code:
        return {"status": "error", "detail": "rego_code is missing"}
    
    if not test_code:
        return {"status": "error", "detail": "test_code is missing"}

    policy_path = "/tmp/policy.rego"
    test_path = "/tmp/policy_test.rego"

    # 정책 파일 생성
    with open(policy_path, "w", encoding="utf-8") as f:
        f.write(policy_code)

    # 테스트 파일 생성
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(test_code)

    try:
        # opa test 실행
        result = subprocess.run(
            ["opa", "test", "-v", policy_path, test_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return {"status": "success", "detail": result.stdout.strip()}
        else:
            return {"status": "fail", "detail": result.stderr.strip()}

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    finally:
        # 테스트 후 임시 정책 파일 삭제
        if os.path.exists(policy_path):
            os.remove(policy_path)

        if os.path.exists(test_path):
            os.remove(test_path)


# -------------------------------
# Tool: User 정보 추출
# -------------------------------
@mcp_server.tool("user")
async def get_user_tool(data: dict):
    """
    Tool Name: user
    --------------------
    Description:
        Retrieves information for a single user based on the provided employee ID (emp_id),
        or returns all users if emp_id is not provided.
    
        This tool is useful for fetching user details from the database in a standardized format.
    
    Args:
        data: dict
            - emp_id: str, optional
                Employee ID of the user to retrieve. If not provided, all users are returned.
    
    Returns (JSON):
        {
            "user": dict
                - Contains user information when emp_id is provided.
            "users": list[dict]
                - List of all users when emp_id is not provided.
        }
    """
    emp_id = data.get("emp_id")
    if emp_id:
        return {"user": get_user_by_id(emp_id)}
    return {"users": get_all_users()}


# -------------------------------
# 서버 시작
# -------------------------------
if __name__ == "__main__":
    print("Starting MCP Server on port 8001...")
    mcp_server.run(transport="streamable-http")
