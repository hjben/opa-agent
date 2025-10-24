

import os
import subprocess

def opa_syntax_check(rego_code: str):
    """
    Check OPA Rego code syntax.
    
    Parameters:
        rego_code (str): The OPA policy code as a string.
        
    Returns:
        Tuple[bool, str]: (is_valid, error_message)
            is_valid: True if syntax is correct.
            error_message: Empty if valid, otherwise the syntax error.
    """
    try:
        # 임시 파일에 정책 저장
        import tempfile
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
            return True, ""
        else:
            return False, result.stderr.strip()

    except Exception as e:
        return False, str(e)

def opa_test(rego_code: str, test_code: str):
    """
    정책 rego_code와 test_code를 받아 OPA 테스트 수행
    """
    if not rego_code:
        return {"status": "error", "detail": "rego_code is missing"}
    
    if not test_code:
        return {"status": "error", "detail": "test_code is missing"}

    policy_path = "/tmp/policy.rego"
    test_path = "/tmp/policy_test.rego"

    # 정책 코드 저장
    with open(policy_path, "w", encoding="utf-8") as f:
        f.write(rego_code)

    # 테스트 파일 생성 (없으면 생성)
    with open(test_path, "w", encoding="utf-8") as f:
        f.write(test_code)

    try:
        # opa test 실행
        result = subprocess.run(
            ["opa", "test", policy_path, test_path],
            capture_output=True,
            text=True
        )

        if result.returncode == 0:
            return {"status": "success", "detail": "OPA test passed successfully."}
        else:
            return {"status": "fail", "detail": result.stderr.strip() or "OPA test failed."}

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    finally:
        # 테스트 후 임시 정책 파일 삭제
        if os.path.exists(policy_path):
            os.remove(policy_path)

        if os.path.exists(test_path):
            os.remove(test_path)