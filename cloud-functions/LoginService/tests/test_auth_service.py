"""Feature 05 LoginService pure service test; Flask/MySQL are not required."""

from services.auth_service import login_by_phone, request_sms

result = request_sms("13800138000")
assert result["phone"] == "13800138000"
assert len(result["debugCode"]) == 6
session = login_by_phone("13800138000", result["debugCode"])
assert session["token"]
assert session["tokenType"] == "bearer"
assert session["user"]["phone"] == "13800138000"
print("LoginService test_auth_service.py: PASS")
