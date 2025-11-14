package httpapi

default allow = false

# 관리자 전체 허용
allow if {
    input.user == "admin"
}

# 조회는 누구나 가능
allow if {
    input.method == "GET"
}

# 생성/수정/삭제는 owner만 허용 (simplified example)
allow if {
    input.method == "POST"
    input.path == "/api/resource/create"
    input.user == "owner"
}
