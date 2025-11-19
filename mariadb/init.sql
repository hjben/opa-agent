-- 사용자 테이블
CREATE TABLE IF NOT EXISTS user (
    emp_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    dept VARCHAR(100),
    is_admin TINYINT(1) DEFAULT 0
);

INSERT INTO user (emp_id, name, dept, is_admin)
SELECT 'E001', 'Alice Johnson', 'AI Research', 0
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E001');

INSERT INTO user (emp_id, name, dept, is_admin)
SELECT 'E002', 'Bob Smith', 'Cloud Engineering', 0
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E002');

INSERT INTO user (emp_id, name, dept, is_admin)
SELECT 'E003', 'Charlie Davis', 'Security', 0
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E003');

INSERT INTO user (emp_id, name, dept, is_admin)
SELECT 'E004', 'Diana Lopez', 'Platform', 0
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E004');

INSERT INTO user (emp_id, name, dept, is_admin)
SELECT 'E005', 'Edward King', 'Platform', 1
WHERE NOT EXISTS (SELECT 1 FROM user WHERE emp_id='E005');

-- 리소스 테이블
CREATE TABLE IF NOT EXISTS dummy_resource (
    resource_id VARCHAR(50) PRIMARY KEY,
    owner VARCHAR(50) NOT NULL,
    type VARCHAR(50) NOT NULL,
    description TEXT,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO dummy_resource (resource_id, owner, type, description)
SELECT 'res_001', 'E001', 'document', 'Sample document resource'
WHERE NOT EXISTS (SELECT 1 FROM dummy_resource WHERE resource_id='res_001');

INSERT INTO dummy_resource (resource_id, owner, type, description)
SELECT 'res_002', 'E002', 'image', 'Sample image resource'
WHERE NOT EXISTS (SELECT 1 FROM dummy_resource WHERE resource_id='res_002');

INSERT INTO dummy_resource (resource_id, owner, type, description)
SELECT 'res_003', 'E003', 'document', 'Policy document resource'
WHERE NOT EXISTS (SELECT 1 FROM dummy_resource WHERE resource_id='res_003');

-- 보고서 테이블
CREATE TABLE IF NOT EXISTS report_history (
    report_id INT AUTO_INCREMENT PRIMARY KEY,
    report_type VARCHAR(50) NOT NULL,
    generated_by VARCHAR(50) NOT NULL,
    file_path VARCHAR(255) NOT NULL,
    status VARCHAR(20) DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO report_history (report_type, generated_by, file_path)
SELECT 'MonthlyResource', 'E001', '/reports/MonthlyResource.pdf'
WHERE NOT EXISTS (SELECT 1 FROM report_history WHERE report_type='MonthlyResource');
