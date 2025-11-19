from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from config.url_config import OPA_ALLOW_URL
import requests
from mariadb.db_connection import db_cursor

app = FastAPI(title="Dummy API Server", description="OPA 권한 테스트 서버")

# ---------------------------
# Models
# ---------------------------
class ResourceCreateRequest(BaseModel):
    resource_id: str
    owner: str
    type: str
    description: Optional[str] = None

class ResourceModifyRequest(BaseModel):
    resource_id: str
    field: str
    new_value: str

class ReportRequest(BaseModel):
    report_type: str
    generated_by: str

# ---------------------------
# OPA 권한 체크
# ---------------------------
def opa_authorize(request: Request, resource_id: Optional[str] = None):
    user_id = request.headers.get("user", "anonymous")
    payload = {
        "user_id": user_id,
        "method": request.method,
        "path": request.url.path,
        "resource_id": resource_id
    }

    print(payload)

    response = requests.post(OPA_ALLOW_URL, json={"input": payload})
    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="OPA server error")

    result = response.json()
    if not result.get("result", False):
        raise HTTPException(status_code=403, detail="Access denied by OPA policy")


# ---------------------------
# API Spec
# ---------------------------
@app.get("/openapi.json")
def get_openapi_spec():
    return app.openapi()

# ---------------------------
# Resource CRUD
# ---------------------------
@app.get("/api/resource")
def get_all_resource(request: Request):
    opa_authorize(request)
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM dummy_resource")
        return cursor.fetchall()

@app.get("/api/resource/{resource_id}")
def get_resource(resource_id: str, request: Request):
    opa_authorize(request, resource_id=resource_id)
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM dummy_resource WHERE resource_id=%s", (resource_id,))
        resource = cursor.fetchone()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        return resource

@app.post("/api/resource/create")
def create_resource(req: ResourceCreateRequest, request: Request):
    opa_authorize(request, resource_id=req.resource_id)
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO dummy_resource (resource_id, owner, type, description) VALUES (%s, %s, %s, %s)",
            (req.resource_id, req.owner, req.type, req.description)
        )
    return {"message": f"Resource '{req.resource_id}' created successfully", "data": req.dict()}

@app.post("/api/resource/modify")
def modify_resource(req: ResourceModifyRequest, request: Request):
    opa_authorize(request, resource_id=req.resource_id)
    print()
    with db_cursor() as cursor:
        cursor.execute(
            f"UPDATE dummy_resource SET {req.field}=%s WHERE resource_id=%s",
            (req.new_value, req.resource_id)
        )
    return {"message": f"Resource '{req.resource_id}' modified successfully"}

@app.delete("/api/resource/{resource_id}")
def delete_resource(resource_id: str, request: Request):
    opa_authorize(request, resource_id=resource_id)
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM dummy_resource WHERE resource_id=%s", (resource_id,))
    return {"message": f"Resource '{resource_id}' deleted successfully"}

# ---------------------------
# Report 생성
# ---------------------------
@app.post("/api/report/generate")
def generate_report(req: ReportRequest, request: Request):
    opa_authorize(request)
    file_path = f"/reports/{req.report_type}.pdf"
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO report_history (report_type, generated_by, file_path) VALUES (%s, %s, %s)",
            (req.report_type, req.generated_by, file_path)
        )
    return {"report_type": req.report_type, "status": "completed", "file": file_path}
