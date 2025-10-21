from mcp.server.fastmcp import FastMCP
from user_db_service import get_user_data
from opa_service import validate_rego
from qdrant_service import QdrantService

# Qdrant 연결
qdrant = QdrantService(url="http://qdrant:6333")

# MCP Server 생성
mcp_server = FastMCP(name="opa_tools", debug=True)

# -------------------------------
# 기능별 Tool 등록
# -------------------------------

@mcp_server.tool("user")
async def handle_user(data: dict):
    emp_id = data.get("emp_id")
    if not emp_id:
        return {"status": "error", "detail": "emp_id is missing"}
    
    user_data = get_user_data({}, emp_id=emp_id)
    if not user_data:
        return {"status": "error", "detail": "User not found"}
    return {"user_data": user_data}

@mcp_server.tool("qdrant")
async def handle_qdrant(data: dict):
    query_vector = data.get("query_vector")
    collection_name = data.get("collection_name", "context")
    limit = data.get("limit", 5)

    if not query_vector:
        return {"status": "error", "detail": "query_vector is missing"}
    
    try:
        result = qdrant.search(collection_name=collection_name, query_vector=query_vector, limit=limit)
        return {"context": result}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@mcp_server.tool("opa")
async def handle_opa(data: dict):
    rego_code = data.get("rego_code")
    if not rego_code:
        return {"status": "error", "detail": "rego_code is missing"}
    
    validation = validate_rego(rego_code)
    if not validation["success"]:
        return {"status": "error", "detail": validation["error"]}
    
    return {"validated_rego": rego_code}

# -------------------------------
# 서버 시작
# -------------------------------
if __name__ == "__main__":
    print("Starting MCP Server on port 8001...")
    mcp_server.run(transport="sse")
