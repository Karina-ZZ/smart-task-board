"""SMS verification sender with mock and Alibaba Cloud number-auth adapters."""

from __future__ import annotations

import json
import secrets

import config


def generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send_code(phone: str, code: str) -> str:
    if config.SMS_PROVIDER == "mock":
        return "mock-request"
    if config.SMS_PROVIDER != "aliyun_dypnsapi":
        raise RuntimeError("unsupported SMS_PROVIDER")
    if not all([
        config.ALIYUN_ACCESS_KEY_ID,
        config.ALIYUN_ACCESS_KEY_SECRET,
        config.ALIYUN_SMS_SIGN_NAME,
        config.ALIYUN_SMS_TEMPLATE_CODE,
    ]):
        raise RuntimeError("Aliyun number-auth SMS environment variables are incomplete")

    from alibabacloud_dypnsapi20170525.client import Client as DypnsClient
    from alibabacloud_dypnsapi20170525 import models as dypns_models
    from alibabacloud_tea_openapi import models as open_api_models
    from alibabacloud_tea_util import models as util_models

    client = DypnsClient(open_api_models.Config(
        access_key_id=config.ALIYUN_ACCESS_KEY_ID,
        access_key_secret=config.ALIYUN_ACCESS_KEY_SECRET,
        endpoint=config.ALIYUN_DYPN_ENDPOINT,
    ))
    request = dypns_models.SendSmsVerifyCodeRequest(
        phone_number=phone,
        sign_name=config.ALIYUN_SMS_SIGN_NAME,
        template_code=config.ALIYUN_SMS_TEMPLATE_CODE,
        template_param=json.dumps({"code": code}, ensure_ascii=False),
    )
    response = client.send_sms_verify_code_with_options(request, util_models.RuntimeOptions())
    request_id = getattr(getattr(response, "body", None), "request_id", None)
    return request_id or "aliyun-request"
