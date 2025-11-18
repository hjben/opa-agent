from mcp.server.fastmcp import FastMCP
from service.mariadb import get_user_by_id, get_all_users
# from service.qdrant import QdrantService

import json
import os
import requests
import tempfile
import subprocess

# Qdrant 연결
# qdrant = QdrantService(url="http://qdrant:6333")

DUMMY_API_URL = "http://localhost:8085"
OPA_URL = "http://localhost:8181/v1/policies"

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
    return "You are an OPA (Open Policy Agent) policy manager."


@mcp_server.prompt("opa_orchestrator_prompt")
def analyze_request_prompt() -> str:

    return """
Main OPA Orchestrator Prompt
----------------------------------------------------

This is the top-level orchestrator for all OPA policy management tasks.
It supports *multiple user intentions in a single request* and intelligently
breaks them down into atomic tasks, then assigns the correct sub-prompt,
tool usage, and parameters for each task.

============================================================
[User Request]
{user_query}
============================================================

Your role: “OPA Policy Management Orchestrator with Multi-Intent Routing”

------------------------------------------------------------------------
1. Intent Extraction
------------------------------------------------------------------------
- Parse the user's request and extract ALL distinct intentions.
- If multiple goals are mentioned in one sentence, separate them into different tasks.
- If the same goal is repeated (even with different wording), merge into a single task.
- Normalize text for duplicates: lowercase, strip spaces, remove punctuation.
- Output ONLY in a JSON array with the following format:
    [
        {{ "intent_id": 1, "intent_text": "..." }},
        {{ "intent_id": 2, "intent_text": "..." }}
    ]

Example:
    Input: "Show me the policy for user access. Also update admin rule. Delete old test policy."
    Output:
    [
        {{ "intent_id": 1, "intent_text": "Show me the policy for user access" }},
        {{ "intent_id": 2, "intent_text": "Update admin rule" }},
        {{ "intent_id": 3, "intent_text": "Delete old test policy" }}
    ]

------------------------------------------------------------------------
2. Categorize Each Intent
------------------------------------------------------------------------

- Assign each intent to EXACTLY ONE category:
    A. Policy Explanation  
    B. New Policy Generation  
    C. Policy Update / Modify / Deletion
    D. Non-OPA / unclear → mark as "unknown"
- You MUST NOT guess meaning beyond the text. If insufficient → mark missing fields as null.
- Include representative examples in classification to improve accuracy.
    * Category A → explanation of current policies
    * Category B → create new policy
    * Category C → modify/update/delete existing policy
    * unknown → clarification needed

Example output:
    [
        {{ "intent_id": 1, "category": "A" }},
        {{ "intent_id": 2, "category": "C" }},
        {{ "intent_id": 3, "category": "D" }}
    ]

------------------------------------------------------------------------
3. Map Each Category to a Sub-Prompt
------------------------------------------------------------------------
- Category A → use `get_policy_prompt`  
  Required params: {{
      "user_query": "<raw user query>"
      "policy_id": "<policy_id if provided>",
    }}

- Category B → use `rego_gen_prompt`  
  Required params: {{ 
      "user_query": "<raw user query>"
  }}

- Category C → use `rego_update_prompt`  
  Required params: {{ 
      "user_query": "<raw user query>",
      "policy_code": "<existing policy code to process>",
      "policy_id": "<policy_id>",
      "update_type": "<add|modify|remove>"
  }}

- "unknown" → return a clarification request

You MUST prepare the `target_prompt` and `params` for EACH intent.
Example output:
[
    {{
        "intent_id": 1,
        "target_prompt": "rego_update_prompt",
        "params": {{
            "policy_id": "authz",
            "update_type": "modify",
            "policy_code": "<existing policy code>",
            "user_query": "<raw user query>"
        }}
    }},
    {{
        "intent_id": 2,
        "target_prompt": "rego_gen_prompt",
        "params": {{
            "policy_id": null,
            "user_query": "<raw user query>"
        }}
    }}
]

------------------------------------------------------------------------
4. Final Output Structure (Required)
------------------------------------------------------------------------
Return ONLY a JSON in the following format:

{{
    "tasks": [
        {{
            "intent_id": <number>,
            "intent_text": "<raw text>",
            "category": "<A|B|C|unknown>",
            "target_prompt": "<prompt_name or null>",
            "params": {{ ... }}
        }},
        ...
    ],
    "notes": "<short reasoning (same language as user)>"
}}

Rules:
- NEVER include code fences
- NEVER generate Rego code here
- NEVER validate policy here
- ONLY route tasks and prepare next actions
- "notes" must be short & high-level
- If user writes in Korean, "notes" must also be Korean

============================================================
End of orchestrator instructions.

"""

@mcp_server.prompt("get_policy_prompt")
def get_policy_prompt() -> str:
    """
    Get a policy for proper policy information prompt.
    """
    return """
Your job is to analyze OPA policies and explain them clearly to the user.
You can get the current policies with 'list_policies' tool.
The policy_id is an optional parameter. if it's None, call the tool without it.

You MUST:
1. Understand the meaning and logic of the provided Rego policies.
2. Explain what each rule does in simple terms.
3. Extract key conditions, permission logic, and decision branches.
4. Answer the user's request based strictly on the given policies.
5. If the policy is invalid or contains syntax problems, identify them and explain.

User Request:
{user_query}

Your Tasks:
1. Provide a concise summary of what the policy set does. Give information about only related to the user request.
2. List key rules and the logic behind them.
3. Explain how authorization is determined.
4. Based on the user's request, give an appropriate answer:
   - If user wants explanation → explain clearly.
   - If user asks what is allowed/denied → answer using policy logic.
   - If user wants examples → provide examples.
   - If user wants modification suggestions → propose safe improvements.
5. Include a "Reasoning Based on Policy" section that directly cites relevant rules.

Avoid:
- Adding new rules not present in the policy.
- Making assumptions outside the policy.

Output Rules:
- Provide a JSON with exactly two keys: "user_query" and "content". add all your results in string type.
- The "content" value must be a **Markdown-formatted string**, including:
    - ## Summary: concise explanation of the policies
    - ## Policy Code: fenced code block (```rego```) for policy code
    - ## Key Rules: explanation of rules, decision logic, and examples
- Do NOT add other JSON keys or code fences outside of the Markdown in "content".
- If the user query is written in Korean, also answer in Korean.
- Your responses must be precise, structured, and helpful.
"""

@mcp_server.prompt("rego_gen_prompt")
def get_rego_gen_prompt() -> str:
    """
    Summarize the OPA policy generation and validation results.
    """
    return """
You will perform a full OPA policy generation and validation workflow in a single sequence.
Follow every step carefully and use the available tools when needed.

============================================================
[User Request]
{user_query}
============================================================

Your tasks:

------------------------------------------------------------
1. Generate Rego Policy Code
------------------------------------------------------------
- Generate a valid OPA Rego policy that satisfies the user request.
- Keep in mind that the policy MUST be implemented to the existing APIs. Check the possibility before generating the policy.
  The existing API list is given by `list_apis` tool.
- Refer to the current OPA policies using the `list_policies` tool.
- Ensure strict Rego syntax correctness.
- The generated policy must:
  - include the `if` keyword before rule bodies
  - contain NO explanations, comments, or extraneous text
- Validate the generated policy using the `opa_check` tool.
- If validation fails, regenerate the code until it becomes valid.
- Store the final code internally as <policy_code>.

Example format:
package authz

allow if {{
    input.path == ["users"]
    input.method == "POST"
}}

allow if {{
    input.path == ["users", input.user_id]
    input.method == "GET"
}}

------------------------------------------------------------
2. Generate Test Rego Code
------------------------------------------------------------
- Write a full test suite to validate <policy_code>.
- Follow OPA test syntax rules.
- Requirements:
  - MUST include `import data.<package>` for the policy
  - MUST use `if` before test rule bodies
  - MUST avoid '_' variables entirely
  - MUST contain no explanations or comments
- Validate the test code using the `opa_check` tool.
- If validation fails, regenerate until valid.
- Store the final test code internally as <test_code>.

Example format:
package authz_test

import data.authz

test_post_allowed if {{
    authz.allow with input as {{"path": ["users"], "method": "POST"}}
}}

test_get_denied if {{
    not authz.allow with input as {{"path": ["users"], "method": "GET"}}
}}

------------------------------------------------------------
3. Run OPA Tests
------------------------------------------------------------
- Use the `opa_test` tool with:
    - policy_code = <policy_code>
    - test_code  = <test_code>
- Collect the full test result including:
    - pass/fail status
    - detailed execution logs
- Store this internally as <validation_result>.
- If some fail case exists, go to the step 1 and re-generate the policy code.

------------------------------------------------------------
4. Summarize Everything (Markdown) (strictly required)
------------------------------------------------------------
Provide a clean, concise summary of the OPA policy generation and validation results using Markdown formatting.

Requirements:
1. Add a `## Summary` section with:
   - One-line description of the policy goal.
   - Whether policy syntax validation passed or failed.
   - Whether test syntax validation passed or failed.
   - Whether OPA tests passed or failed.
2. Add a `## Policy Code` section in a fenced code block with language `rego`, containing the full policy code.
3. Add a `## Test Code` section in a fenced code block with language `rego`, containing the full test code.
4. Add a `## Test Results` section in a normal plain text with ``` block, and don't use any markdown tags. Just show the `opa test` validation result.
5. Ensure all sections are clearly separated using `---`.
6. Keep indentation, spacing, and newlines for readability.
7. Output plain Markdown only; do not include additional JSON or explanatory text outside the Markdown structure.
8. Tone should be professional, concise, and suitable for technical documentation.

Example structure:

## Policy Code
# Policy Summary

## Summary
This policy controls resource access based on user roles and request methods.  
Policy syntax validation passed successfully, the test code syntax also passed,  
and all OPA tests have passed successfully.

## POLICY CODE
<policy code here>

## TEST CODE
<test code here>

## TEST RESULTS
<test results here>


[Output Rules]
- The FINAL answer must be JSON with exactly TWO key: "content" and "policy_code".
- The value of "content" must be a single plain text string that contains the formatted summary, policy code, test code, and results.
- In the "policy_code" key, repeat the policy code with a single plain text string.
- Preserve indentation, line breaks, headings, and code fences.
- Do NOT include any unnecessary escaping.
- Do NOT include any additional JSON fields.
- The text inside "content" must be human-readable.
- The user request is made of Korean, your content also constructed with Korean.
============================================================

End of instructions. Begin the workflow now.
"""

@mcp_server.prompt("rego_update_prompt")
def get_rego_update_prompt() -> str:
    """
    Get a policy for proper policy information prompt.
    """
    return """

[User Request]
{user_query}

{policy_code}

[Policy ID]
{policy_id}

[Update type]
{update_type}

Your job is to create, update, or delete OPA Rego policies based on the user request, 
and respond with the exact tool instructions needed to apply the modification.

You MUST:
1. Correctly interpret the user's requested modification (add, update, remove).
2. Understand the meaning and logic of the existing Rego policy.
3. Validate the syntax and semantics of any updated or newly generated Rego code.
4. When modifying a policy:
   - Identify the affected package, rule, and logical conditions.
   - Generate the updated Rego block exactly as it should appear.
5. When deleting a policy or rule:
   - Identify the correct policy_id or rule name to remove.
   - Ensure no partial or inconsistent deletions occur.
6. If the user query is written in Korean, then all explanations must be in Korean.
7. The policy_id is optional parameter. If provided, use it to query the target policy.

Output Rules:
- Return a JSON with exactly two keys: "user_query" and "content".
- The "content" value must be **Markdown-formatted** and include:
    - ## User request: what the LLM understood
    - ## Modification Plan: steps or rules being changed
    - ## Target Policy Code: fenced code block (```rego```) with updated code
    - ## Explanation: short reasoning in same language as user
- No extra code fences outside the Markdown.
- Preserve formatting, indentation, and newlines.
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
            return {"status": "fail", "detail": result.stdout.strip()}

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

@mcp_server.tool("list_policies")
def list_policies_tool(policy_id: str = None):
    """
    Tool Name: list_policies
    --------------------
    Description:
        Fetches policies from the connected OPA server.

        If a specific policy_id is provided, the tool retrieves only that policy.
        If policy_id is omitted or None, the tool returns all registered policies.

        The returned payload includes complete policy definitions or error details.
        This tool performs read-only operations and does not modify any OPA data.

    Args:
        policy_id: str (optional)
            - If provided, fetches only the policy matching this ID.
            - If None, fetches all policies currently registered in OPA.

    Returns (JSON):
        {
            "policies": dict
                - Mapping from policy_id to policy details or error info.

            "error": str (optional)
                - Present only if a top-level OPA request failure occurred.

        Example:
        {
            "policies": {
                "example_policy": {
                    "id": "example_policy",
                    "raw": "package policy\n\ndefault allow := false\n...",
                    "metadata": { ... }
                },
                "missing_policy": {
                    "error": "Failed to retrieve: 404 Not Found"
                }
            }
        }
    """
    if policy_id is not None:
        res = requests.get(f"{OPA_URL}/{policy_id}")
    else:
        res = requests.get(OPA_URL)

    if res.status_code != 200:
        return {
            "error": f"OPA responded with {res.status_code}",
            "detail": res.text
        }

    data = res.json()

    # policies 필드가 없는 경우 방어 처리
    policies = data.get("result", data)

    # 정책 상세를 모두 가져오기
    result = {}
    for policy in policies:
        result[policy['id']] = policy['raw']

    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp_server.tool("update_policy")
def update_policy(policy_id: str, policy_str: str):
    """
    Tool Name: update_policy
    --------------------
    Description:
        Updates an existing OPA policy or creates a new one if the policy_id does not exist.

        The tool sends the provided policy string to the OPA server using a PUT request.
        OPA will replace the entire policy content corresponding to policy_id with the
        supplied Rego policy text. This operation fully overwrites the existing policy.

        The tool validates the response status code and returns an error object if
        the update fails (e.g., invalid Rego, policy not accepted, or network issues).

    Args:
        policy_id: str
            - Identifier of the policy to update on the OPA server.
            - If the ID does not currently exist, OPA will create a new policy.

        policy_str: str
            - Full Rego policy text to upload.
            - Must be a syntactically valid Rego module or OPA will reject it.

    Returns (JSON):
        {
            "message": str
                - Confirmation message when the update succeeds.

            "policy_id": str
                - The updated policy identifier.

            "error": str (optional)
                - Included if OPA returns a non-success status code.

            "detail": str (optional)
                - The raw OPA error response text for debugging.
        }

        Example:
        {
            "message": "Policy updated successfully",
            "policy_id": "example_policy"
        }
    """
    headers = {"Content-Type": "text/plain"}
    res = requests.put(f"{OPA_URL}/{policy_id}", data=policy_str.encode("utf-8"), headers=headers)

    if res.status_code not in (200, 204):
        return {
            "error": f"OPA responded with {res.status_code}",
            "detail": res.text
        }

    return {"message": "Policy updated successfully", "policy_id": policy_id}


@mcp_server.tool("delete_policy")
def delete_policy(policy_id: str):
    """
    Tool Name: delete_policy
    --------------------
    Description:
        Deletes an existing policy from the OPA server.

        The tool performs an HTTP DELETE request to remove the policy associated
        with the given policy_id. If the policy does not exist or the OPA server
        cannot process the request, the tool returns an error description.

        This operation permanently removes the specified policy from OPA and
        cannot be undone via this tool.

    Args:
        policy_id: str
            - Identifier of the policy to delete.
            - If the policy does not exist, OPA typically returns a 404 status code.

    Returns (JSON):
        {
            "message": str
                - Confirmation message when deletion succeeds.

            "policy_id": str
                - The deleted policy identifier.

            "error": str (optional)
                - Present if the deletion request failed.

            "detail": str (optional)
                - Raw OPA error details for debugging.
        }

        Example:
        {
            "message": "Policy deleted successfully",
            "policy_id": "example_policy"
        }
    """
    res = requests.delete(f"{OPA_URL}/{policy_id}")

    if res.status_code not in (200, 204):
        return {
            "error": f"OPA responded with {res.status_code}",
            "detail": res.text
        }
    return {"message": "Policy deleted successfully", "policy_id": policy_id}


@mcp_server.tool("list_api")
def list_apis_tool():
    """
    Function Name: get_api_list
    ---------------------------
    Description:
        Collects and returns all API specifications registered in the current FastAPI
        application. The function extracts metadata from the FastAPI router, including:
            - HTTP method
            - Path
            - Handler function name
            - Summary and description (if provided in the FastAPI route definitions)
            - Request/Response model schemas (if available)

        This function is the internal data provider for the `list_apis` tool. It performs
        read-only introspection of the FastAPI application and does not modify any routing
        or OpenAPI configuration.

        The returned structure is suitable for display, analysis, or further processing
        by agents or tools (e.g., documentation generation, automatic testing, or
        dynamic routing decisions).

    Args:
        None

    Returns (dict):
        {
            "apis": [
                {
                    "path": str,                 # API endpoint path (e.g., "/items/{id}")
                    "method": str,               # HTTP method ("GET", "POST", ...)
                    "name": str,                 # Handler function name
                    "summary": str or None,      # Route summary if defined
                    "description": str or None,  # Route description if defined
                    "request_model": dict or None,   # Pydantic schema for request body
                    "response_model": dict or None   # Pydantic schema for response body
                },
                ...
            ],
            "error": str (optional)
                - Present only if an exception occurs during FastAPI route inspection.
        }
    """
    response = requests.get(f"{DUMMY_API_URL}/openapi.json")
    response.raise_for_status()  # 오류 발생 시 예외

    return json.dumps(response.json(), ensure_ascii=False)


# -------------------------------
# 서버 시작
# -------------------------------
if __name__ == "__main__":
    print("Starting MCP Server on port 8001...")
    mcp_server.run(transport="streamable-http")
