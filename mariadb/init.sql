-- ========================================
-- 1️⃣ Database 생성 (없을 경우에만)
-- ========================================
CREATE DATABASE IF NOT EXISTS opa_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE opa_db;

-- ========================================
-- 2️⃣ user 테이블
-- ========================================
CREATE TABLE IF NOT EXISTS user (
    emp_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dept VARCHAR(100),
    role VARCHAR(100)
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

INSERT INTO api (name, endpoint, method, description)
SELECT 'GetUserInfo', '/api/v1/user', 'GET', 'Retrieve user information by employee ID'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='GetUserInfo');

INSERT INTO api (name, endpoint, method, description)
SELECT 'SubmitPolicy', '/api/v1/policy', 'POST', 'Submit a new policy definition'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='SubmitPolicy');

INSERT INTO api (name, endpoint, method, description)
SELECT 'ListAPIs', '/api/v1/apis', 'GET', 'List all available APIs'
WHERE NOT EXISTS (SELECT 1 FROM api WHERE name='ListAPIs');

-- ========================================
-- 4️⃣ policy 테이블
-- ========================================
CREATE TABLE IF NOT EXISTS policy (
    policy_id INT AUTO_INCREMENT PRIMARY KEY,
    policy_name VARCHAR(100) NOT NULL,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(20),
    FOREIGN KEY (created_by) REFERENCES user(emp_id)
);

INSERT INTO policy (policy_name, description, created_by)
SELECT 'DataAccessPolicy', 'Controls data access permissions based on user roles', 'E003'
WHERE NOT EXISTS (SELECT 1 FROM policy WHERE policy_name='DataAccessPolicy');

INSERT INTO policy (policy_name, description, created_by)
SELECT 'ServiceAccessPolicy', 'Defines service-level API permissions for internal users', 'E002'
WHERE NOT EXISTS (SELECT 1 FROM policy WHERE policy_name='ServiceAccessPolicy');

INSERT INTO policy (policy_name, description, created_by)
SELECT 'DefaultPolicy', 'Fallback policy for unregistered users', 'E001'
WHERE NOT EXISTS (SELECT 1 FROM policy WHERE policy_name='DefaultPolicy');
