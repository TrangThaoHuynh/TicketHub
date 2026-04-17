import hashlib
import hmac
import os
from datetime import datetime, timedelta
from typing import Any, Dict, Mapping
from urllib.parse import quote_plus

from flask import has_app_context, current_app

# VNPay sandbox defaults for local simulation.
VNP_TMNCODE = "YOUR_TMNCODE"
VNP_HASHSECRET = "YOUR_SECRET_KEY"
VNP_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
VNP_RETURN_URL = "http://127.0.0.1:5000/payment_return"


RESPONSE_MESSAGES = {
	"00": "Giao dich thanh cong",
	"07": "Tru tien thanh cong. Giao dich bi nghi ngo",
	"09": "The tai khoan chua dang ky InternetBanking",
	"10": "Xac thuc thong tin the/tai khoan khong dung",
	"11": "Het han cho thanh toan",
	"12": "The tai khoan bi khoa",
	"13": "Sai ma OTP",
	"24": "Khach hang huy giao dich",
	"51": "Tai khoan khong du so du",
	"65": "Tai khoan vuot han muc giao dich",
	"75": "Ngan hang dang bao tri",
	"79": "Sai mat khau thanh toan",
	"99": "Loi khong xac dinh",
}


def _load_setting(name: str, default: str) -> str:
	if has_app_context():
		value = current_app.config.get(name) or os.getenv(name)
	else:
		value = os.getenv(name)

	value = (value or "").strip()
	return value if value else default


def get_vnpay_config() -> Dict[str, str]:
	return {
		"vnp_tmn_code": _load_setting("VNP_TMNCODE", VNP_TMNCODE),
		"vnp_hash_secret": _load_setting("VNP_HASHSECRET", VNP_HASHSECRET),
		"vnp_url": _load_setting("VNP_URL", VNP_URL),
		"vnp_return_url": _load_setting("VNP_RETURN_URL", VNP_RETURN_URL),
	}


def _normalize_params(params: Mapping[str, Any]) -> Dict[str, str]:
	normalized: Dict[str, str] = {}

	for key, value in params.items():
		if value is None:
			continue

		if isinstance(value, (list, tuple)):
			normalized[key] = str(value[0]) if value else ""
		else:
			normalized[key] = str(value)

	return normalized


def _build_hash_data(params: Mapping[str, Any]) -> str:
	filtered = {
		key: value
		for key, value in _normalize_params(params).items()
		if key not in {"vnp_SecureHash", "vnp_SecureHashType"}
	}

	sorted_items = sorted(filtered.items(), key=lambda item: item[0])
	return "&".join(f"{key}={quote_plus(value)}" for key, value in sorted_items)


def create_secure_hash(params: Mapping[str, Any], hash_secret: str | None = None) -> str:
	config = get_vnpay_config()
	secret = (hash_secret or config["vnp_hash_secret"]).strip()
	hash_data = _build_hash_data(params)

	return hmac.new(secret.encode("utf-8"), hash_data.encode("utf-8"), hashlib.sha512).hexdigest()


def build_payment_url(
	amount: float | int,
	txn_ref: str,
	order_info: str,
	ip_addr: str = "127.0.0.1",
	order_type: str = "other",
	locale: str = "vn",
	bank_code: str | None = None,
	create_date: datetime | None = None,
	return_url: str | None = None,
	expire_minutes: int = 15,
) -> Dict[str, Any]:
	config = get_vnpay_config()
	created_at = create_date or datetime.now()
	resolved_return_url = (return_url or "").strip() or config["vnp_return_url"]

	params: Dict[str, Any] = {
		"vnp_Version": "2.1.0",
		"vnp_Command": "pay",
		"vnp_TmnCode": config["vnp_tmn_code"],
		"vnp_Amount": str(int(round(float(amount) * 100))),
		"vnp_CurrCode": "VND",
		"vnp_TxnRef": str(txn_ref),
		"vnp_OrderInfo": order_info,
		"vnp_OrderType": order_type,
		"vnp_Locale": locale,
		"vnp_ReturnUrl": resolved_return_url,
		"vnp_IpAddr": ip_addr,
		"vnp_CreateDate": created_at.strftime("%Y%m%d%H%M%S"),
		"vnp_ExpireDate": (created_at + timedelta(minutes=expire_minutes)).strftime("%Y%m%d%H%M%S"),
	}

	if bank_code:
		params["vnp_BankCode"] = bank_code

	query_without_hash = _build_hash_data(params)
	secure_hash = create_secure_hash(params, config["vnp_hash_secret"])
	payment_url = f"{config['vnp_url']}?{query_without_hash}&vnp_SecureHash={secure_hash}"

	signed_params = dict(_normalize_params(params))
	signed_params["vnp_SecureHash"] = secure_hash

	return {
		"payment_url": payment_url,
		"params": signed_params,
		"hash_data": query_without_hash,
	}


def verify_return_data(query_params: Mapping[str, Any]) -> Dict[str, Any]:
	normalized = _normalize_params(query_params)
	secure_hash = normalized.get("vnp_SecureHash", "")

	expected_hash = create_secure_hash(normalized)
	valid_signature = bool(secure_hash) and hmac.compare_digest(secure_hash.lower(), expected_hash.lower())

	response_code = normalized.get("vnp_ResponseCode", "")
	transaction_status = normalized.get("vnp_TransactionStatus", "")
	success = valid_signature and response_code == "00" and transaction_status in {"", "00"}

	amount_raw = normalized.get("vnp_Amount", "0")
	try:
		amount = int(amount_raw) / 100
	except (ValueError, TypeError):
		amount = 0

	return {
		"is_valid_signature": valid_signature,
		"is_success": success,
		"response_code": response_code,
		"message": RESPONSE_MESSAGES.get(response_code, "Khong xac dinh"),
		"txn_ref": normalized.get("vnp_TxnRef"),
		"transaction_no": normalized.get("vnp_TransactionNo"),
		"amount": amount,
		"raw": normalized,
	}


def build_mock_return_url(txn_ref: str, amount: float | int, success: bool = True) -> str:
	response_code = "00" if success else "24"
	transaction_status = "00" if success else "02"

	params = {
		"vnp_Amount": str(int(round(float(amount) * 100))),
		"vnp_TxnRef": str(txn_ref),
		"vnp_ResponseCode": response_code,
		"vnp_TransactionStatus": transaction_status,
		"vnp_TransactionNo": f"MOCK{datetime.now().strftime('%Y%m%d%H%M%S')}",
		"vnp_PayDate": datetime.now().strftime("%Y%m%d%H%M%S"),
		"vnp_OrderInfo": "Mock payment callback",
	}

	secure_hash = create_secure_hash(params)
	query = _build_hash_data(params)

	return_url = get_vnpay_config()["vnp_return_url"]
	return f"{return_url}?{query}&vnp_SecureHash={secure_hash}"

