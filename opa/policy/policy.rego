package httpapi

default allow = false

# Admin은 모든 API 허용
allow if {
    user := data.users[input.user_id]
    user.role == "Admin"
}

# GET 요청은 모든 유저 허용
allow if {
    input.method == "GET"
}

# 리소스 소유자만 수정 허용
allow if {
    input.input.method == "POST"
    input.input.path == "/api/resource/modify"
    resource_owner := data.resource_owners[input.input.resource_id]
    input.input.user_id == resource_owner
}

# platform 부서에 report 생성 권한 부여
allow if {
    input.method == "POST"
    input.path == "/api/resource/modify"
    input.user.department == "platform"
}
