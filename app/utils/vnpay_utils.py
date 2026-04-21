import hashlib
import hmac
import os
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Any, Dict, Mapping
from urllib.parse import quote_plus

from flask import has_app_context, current_app
import requests

# VNPay sandbox defaults for local simulation.
VNP_TMNCODE = "YOUR_TMNCODE"
VNP_HASHSECRET = "YOUR_SECRET_KEY"
VNP_URL = "https://sandbox.vnpayment.vn/paymentv2/vpcpay.html"
VNP_RETURN_URL = "http://127.0.0.1:5000/payment_return"
VNP_API_URL = "https://sandbox.vnpayment.vn/merchant_webapi/api/transaction"


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
		"vnp_api_url": _load_setting("VNP_API_URL", VNP_API_URL),
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
		"pay_date": normalized.get("vnp_PayDate"),
		"amount": amount,
		"raw": normalized,
	}


def build_refund_payload(
	amount: float | int,
	txn_ref: str,
	transaction_no: str,
	transaction_date: str,
	order_info: str,
	ip_addr: str = "127.0.0.1",
	transaction_type: str = "02",
	create_by: str = "system",
	create_date: datetime | None = None,
	request_id: str | None = None,
) -> Dict[str, str]:
	config = get_vnpay_config()
	created_at = create_date or datetime.now()
	resolved_request_id = (request_id or f"RF{created_at.strftime('%Y%m%d%H%M%S%f')}")[:32]
	resolved_order_info = (order_info or "Hoan tien giao dich")[:255]

	try:
		amount_decimal = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
	except (InvalidOperation, TypeError, ValueError):
		amount_decimal = Decimal("0.00")

	amount_minor_units = int(
		(amount_decimal * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP)
	)

	payload = {
		"vnp_RequestId": resolved_request_id,
		"vnp_Version": "2.1.0",
		"vnp_Command": "refund",
		"vnp_TmnCode": config["vnp_tmn_code"],
		"vnp_TransactionType": str(transaction_type or "02"),
		"vnp_TxnRef": str(txn_ref or ""),
		"vnp_Amount": str(amount_minor_units),
		"vnp_TransactionNo": str(transaction_no or ""),
		"vnp_TransactionDate": str(transaction_date or ""),
		"vnp_CreateBy": str(create_by or "system"),
		"vnp_CreateDate": created_at.strftime("%Y%m%d%H%M%S"),
		"vnp_IpAddr": str(ip_addr or "127.0.0.1"),
		"vnp_OrderInfo": resolved_order_info,
	}

	hash_data = "|".join(
		[
			payload["vnp_RequestId"],
			payload["vnp_Version"],
			payload["vnp_Command"],
			payload["vnp_TmnCode"],
			payload["vnp_TransactionType"],
			payload["vnp_TxnRef"],
			payload["vnp_Amount"],
			payload["vnp_TransactionNo"],
			payload["vnp_TransactionDate"],
			payload["vnp_CreateBy"],
			payload["vnp_CreateDate"],
			payload["vnp_IpAddr"],
			payload["vnp_OrderInfo"],
		]
	)

	payload["vnp_SecureHash"] = hmac.new(
		config["vnp_hash_secret"].encode("utf-8"),
		hash_data.encode("utf-8"),
		hashlib.sha512,
	).hexdigest()

	return payload


def request_refund(
	amount: float | int,
	txn_ref: str,
	transaction_no: str,
	transaction_date: str,
	order_info: str,
	ip_addr: str = "127.0.0.1",
	transaction_type: str = "02",
	create_by: str = "system",
	timeout_seconds: int = 25,
	max_retries: int = 2,
) -> Dict[str, Any]:
	config = get_vnpay_config()
	payload = build_refund_payload(
		amount=amount,
		txn_ref=txn_ref,
		transaction_no=transaction_no,
		transaction_date=transaction_date,
		order_info=order_info,
		ip_addr=ip_addr,
		transaction_type=transaction_type,
		create_by=create_by,
	)

	attempt_count = max(1, int(max_retries or 1))
	read_timeout = max(5, int(timeout_seconds or 25))
	connect_timeout = 5

	last_timeout_error = None
	for attempt_index in range(attempt_count):
		try:
			response = requests.post(
				config["vnp_api_url"],
				json=payload,
				timeout=(connect_timeout, read_timeout),
			)
			response.raise_for_status()
			data = response.json() if response.content else {}
			break
		except requests.Timeout as exc:
			last_timeout_error = exc
			if attempt_index < attempt_count - 1:
				continue
			return {
				"is_success": False,
				"response_code": "99",
				"message": (
					f"VNPay phan hoi cham (timeout {read_timeout}s) sau {attempt_count} lan thu"
				),
				"raw": {},
				"request_payload": payload,
			}
		except requests.RequestException as exc:
			return {
				"is_success": False,
				"response_code": "99",
				"message": f"Khong the ket noi VNPay: {exc}",
				"raw": {},
				"request_payload": payload,
			}
		except ValueError:
			return {
				"is_success": False,
				"response_code": "99",
				"message": "VNPay tra ve du lieu khong hop le.",
				"raw": {},
				"request_payload": payload,
			}
	else:
		return {
			"is_success": False,
			"response_code": "99",
			"message": f"Khong the ket noi VNPay: {last_timeout_error or 'Unknown timeout'}",
			"raw": {},
			"request_payload": payload,
		}

	response_code = str(data.get("vnp_ResponseCode") or "").strip()
	transaction_status = str(data.get("vnp_TransactionStatus") or "").strip()
	message = str(data.get("vnp_Message") or RESPONSE_MESSAGES.get(response_code, "Khong xac dinh")).strip()

	# Refund API can return success message even when transaction status is not "00".
	is_success = response_code == "00"
	if not is_success and "refund success" in message.lower():
		is_success = True

	return {
		"is_success": is_success,
		"response_code": response_code,
		"message": message,
		"raw": data,
		"request_payload": payload,
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

