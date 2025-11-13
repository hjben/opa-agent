package policy

default allow := false

# 관리자(admin)는 항상 허용
allow if {
    input.user.role == "admin"
}

# IT 부서는 조회, 수정, 삭제 가능
allow if {
    input.user.role == "it"
    input.action == "read"
}

allow if {
    input.user.role == "it"
    input.action == "update"
}

allow if {
    input.user.role == "it"
    input.action == "delete"
}

# 일반 사용자(user)는 업무시간(09~18시)에 조회만 가능
allow if {
    input.user.role == "user"
    input.action == "read"
    is_business_hour
}

# 업무시간 체크 함수
is_business_hour if {
    hr := time.now_ns()
    hr >= 9
    hr < 18
}
