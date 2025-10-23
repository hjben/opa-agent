import subprocess
import tempfile
import os

def opa_test(policy_code: str, test_code: str) -> tuple[bool, str]:
    """
    OPA 테스트 실행 함수
    :param policy_code: OPA 정책 코드 문자열
    :param test_code: OPA 테스트 코드 문자열
    :return: (성공 여부, 로그)
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        policy_path = os.path.join(tmpdir, "policy.rego")
        test_path = os.path.join(tmpdir, "test_policy.rego")

        # 파일 쓰기
        with open(policy_path, "w") as f:
            f.write(policy_code)
        with open(test_path, "w") as f:
            f.write(test_code)

        # OPA test 명령 실행
        cmd = ["opa", "test", policy_path, test_path, "-v"]
        process = subprocess.run(cmd, capture_output=True, text=True)

        success = process.returncode == 0
        output = process.stdout + "\n" + process.stderr

        return success, output
