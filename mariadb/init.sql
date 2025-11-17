-- ========================================
-- Database 생성
-- ========================================
CREATE DATABASE IF NOT EXISTS opa_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE opa_db;

-- ========================================
-- user 테이블
-- ========================================
CREATE TABLE IF NOT EXISTS user (
    emp_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dept VARCHAR(100),
);

-- 샘플 데이터 (이미 존재하지 않을 때만 추가)
INSERT INTO user (emp_id, name, dept, role)
SELECT 'E001', 'Alice Johnson', 'AI Research', 'Data Scientist'
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E001');

INSERT INTO user (emp_id, name, dept, role)
SELECT 'E002', 'Bob Smith', 'Cloud Engineering', 'MLOps Engineer'
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E002');

INSERT INTO user (emp_id, name, dept, role)
SELECT 'E003', 'Charlie Davis', 'Security', 'Policy Analyst'
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E003');

INSERT INTO user (emp_id, name, dept, role)
SELECT 'E004', 'Diana Lopez', 'Platform', 'Backend Developer'
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E004');

-- ========================================
-- 3️⃣ api 테이블
-- ========================================
CREATE TABLE IF NOT EXISTS api (
    api_id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) DEFAULT 'GET',
    description TEXT
);

-- 1. 리소스 조회
INSERT INTO api (name, endpoint, method, description)
SELECT 'GetResource', '/api/resource/{resource_id}', 'GET', 'Retrieve resource details'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='GetResource');

-- 2. 리소스 생성
INSERT INTO api (name, endpoint, method, description)
SELECT 'CreateResource', '/api/resource/create', 'POST', 'Create a new resource'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='CreateResource');

-- 3. 리소스 수정
INSERT INTO api (name, endpoint, method, description)
SELECT 'ModifyResource', '/api/resource/modify', 'POST', 'Modify a resource'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='ModifyResource');

-- 4. 리소스 삭제
INSERT INTO api (name, endpoint, method, description)
SELECT 'DeleteResource', '/api/resource/{resource_id}', 'DELETE', 'Delete a resource'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='DeleteResource');

-- 5. 리포트 생성
INSERT INTO api (name, endpoint, method, description)
SELECT 'GenerateReport', '/api/report/generate', 'POST', 'Generate a mock report'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='GenerateReport');


-- ========================================
-- 1️⃣ dummy_resource 테이블
-- ========================================
CREATE TABLE IF NOT EXISTS dummy_resource (
    resource_id VARCHAR(50) PRIMARY KEY,
    owner VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- 샘플 데이터
INSERT INTO dummy_resource (resource_id, owner, type, description)
SELECT 'res_001', 'E001', 'document', 'Sample document resource'
WHERE NOT EXISTS (SELECT 1 FROM dummy_resource WHERE resource_id='res_001');

INSERT INTO dummy_resource (resource_id, owner, type, description)
SELECT 'res_002', 'E002', 'image', 'Sample image resource'
WHERE NOT EXISTS (SELECT 1 FROM dummy_resource WHERE resource_id='res_002');

-- ========================================
-- 2️⃣ report_history 테이블
-- ========================================
CREATE TABLE IF NOT EXISTS report_history (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    report_type VARCHAR(50) NOT NULL,
    generated_by VARCHAR(50) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
