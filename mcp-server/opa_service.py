import requests

OPA_URL = "http://opa:8181/v1/policies/test"

def validate_rego(rego_code):
    payload = {"policy": rego_code}
    try:
        resp = requests.put(OPA_URL, json=payload)
        if resp.status_code == 200:
            return {"success": True}
        else:
            return {"success": False, "error": resp.text}
    except Exception as e:
        return {"success": False, "error": str(e)}
