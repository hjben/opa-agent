package httpapi

import data

default allow = false

# Admin은 모든 API 허용
allow if {
    user := data.users[input.user_id]
    user.is_admin
}

# GET 요청은 모든 유저 허용
allow if {
    input.method == "GET"
}

# 리소스 소유자만 수정 허용
allow if {
    input.method == "POST"
    input.path == "/api/resource/modify"
    data.resource_owners[input.resource_id] == input.user_id
}

# platform 부서에 report 생성 권한 부여
allow if {
    input.method == "POST"
    input.path == "/api/report/generate"

    user := data.users[input.user_id]
    data.users[input.user_id].dept == "Platform"
}
