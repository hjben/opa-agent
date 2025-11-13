from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from mariadb.db_connection import db_cursor

app = FastAPI(title="Dummy API Server", description="Test APIs for policy validation")

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
# Resource CRUD
# ---------------------------
@app.get("/api/resource")
def get_all_resource():
    """모든 리소스 조회"""
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM dummy_resource")
        return cursor.fetchall()

@app.get("/api/resource/{resource_id}")
def get_resource(resource_id: str):
    """특정 리소스 조회"""
    with db_cursor(dictionary=True) as cursor:
        cursor.execute("SELECT * FROM dummy_resource WHERE resource_id=%s", (resource_id,))
        resource = cursor.fetchone()
        if not resource:
            raise HTTPException(status_code=404, detail="Resource not found")
        return resource

@app.post("/api/resource/create")
def create_resource(req: ResourceCreateRequest):
    """리소스 생성"""
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO dummy_resource (resource_id, owner, type, description) VALUES (%s, %s, %s, %s)",
            (req.resource_id, req.owner, req.type, req.description)
        )
    return {"message": f"Resource '{req.resource_id}' created successfully", "data": req.dict()}

@app.post("/api/resource/modify")
def modify_resource(req: ResourceModifyRequest):
    """리소스 수정"""
    with db_cursor() as cursor:
        cursor.execute(
            f"UPDATE dummy_resource SET {req.field}=%s WHERE resource_id=%s",
            (req.new_value, req.resource_id)
        )
    return {"message": f"Resource '{req.resource_id}' modified successfully"}

@app.delete("/api/resource/{resource_id}")
def delete_resource(resource_id: str):
    """리소스 삭제"""
    with db_cursor() as cursor:
        cursor.execute("DELETE FROM dummy_resource WHERE resource_id=%s", (resource_id,))
    return {"message": f"Resource '{resource_id}' deleted successfully"}

# ---------------------------
# Report
# ---------------------------
@app.post("/api/report/generate")
def generate_report(req: ReportRequest):
    """리포트 생성"""
    file_path = f"/reports/{req.report_type}.pdf"
    with db_cursor() as cursor:
        cursor.execute(
            "INSERT INTO report_history (report_type, generated_by, file_path) VALUES (%s, %s, %s)",
            (req.report_type, req.generated_by, file_path)
        )
    return {"report_type": req.report_type, "status": "completed", "file": file_path}
