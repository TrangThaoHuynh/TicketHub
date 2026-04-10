function setStep(step) {
	const verifyForm = document.getElementById("verifyForm");
	const resetForm = document.getElementById("resetForm");
	const stepDot1 = document.getElementById("stepDot1");
	const stepDot2 = document.getElementById("stepDot2");

	if (!verifyForm || !resetForm || !stepDot1 || !stepDot2) {
		return;
	}

	const isVerifyStep = step === 1;
	verifyForm.classList.toggle("panel-active", isVerifyStep);
	resetForm.classList.toggle("panel-active", !isVerifyStep);
	stepDot1.classList.toggle("is-active", isVerifyStep);
	stepDot2.classList.toggle("is-active", !isVerifyStep);
}

function setFieldState(input, isValid) {
	const group = input.closest(".form-group");
	const icon = group?.querySelector(".status-icon");
	if (!group) {
		return;
	}

	group.classList.remove("valid", "invalid");
	if (icon) {
		icon.classList.remove("fa-circle-check", "fa-circle-exclamation");
	}

	if (isValid) {
		group.classList.add("valid");
		if (icon) {
			icon.classList.add("fa-circle-check");
		}
	} else {
		group.classList.add("invalid");
		if (icon) {
			icon.classList.add("fa-circle-exclamation");
		}
	}
}

function resetFieldState(input) {
	const group = input.closest(".form-group");
	const icon = group?.querySelector(".status-icon");
	if (!group) {
		return;
	}

	group.classList.remove("valid", "invalid");
	if (icon) {
		icon.classList.remove("fa-circle-check", "fa-circle-exclamation");
	}
}

function validateEmail(email) {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function validateCode(code) {
	return /^\d{6}$/.test(code.trim());
}

function validatePassword(password) {
	return /^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/.test(password);
}

async function postJson(url, payload) {
	const response = await fetch(url, {
		method: "POST",
		headers: {
			"Content-Type": "application/json"
		},
		credentials: "same-origin",
		body: JSON.stringify(payload)
	});

	const data = await response.json().catch(() => ({}));
	return {
		ok: response.ok,
		data
	};
}

document.addEventListener("DOMContentLoaded", () => {
	const verifyForm = document.getElementById("verifyForm");
	const resetForm = document.getElementById("resetForm");
	const verifyNotice = document.getElementById("verifyNotice");
	const verifyEmail = document.getElementById("verifyEmail");
	const verifyCode = document.getElementById("verifyCode");
	const verifyHint = document.getElementById("verifyHint");
	const requestCodeBtn = document.getElementById("requestCodeBtn");
	const newPassword = document.getElementById("newPassword");
	const newPasswordHint = document.getElementById("newPasswordHint");
	const confirmPassword = document.getElementById("confirmPassword");
	const resetHint = document.getElementById("resetHint");
	const backToCode = document.getElementById("backToCode");
	const toggleButtons = document.querySelectorAll(".toggle-password");
	const requestCodeUrl = verifyForm?.dataset.requestCodeUrl || "/forgot-password/request-code";
	const verifyCodeUrl = verifyForm?.dataset.verifyCodeUrl || "/forgot-password/verify-code";
	const resetPasswordUrl = resetForm?.dataset.resetPasswordUrl || "/forgot-password/reset-password";
	const passwordRuleMessage = "Tối thiểu 8 ký tự, gồm chữ hoa, số và ký tự đặc biệt.";
	const NOTICE_AUTO_HIDE_MS = 5000;

	setStep(1);

	let resendCountdown = null;
	let verifyNoticeTimer = null;

	const clearVerifyNoticeTimer = () => {
		if (verifyNoticeTimer) {
			window.clearTimeout(verifyNoticeTimer);
			verifyNoticeTimer = null;
		}
	};

	const setVerifyNotice = (message, type = "error") => {
		if (!verifyNotice) {
			return;
		}

		clearVerifyNoticeTimer();

		if (!message) {
			verifyNotice.hidden = true;
			verifyNotice.textContent = "";
			verifyNotice.classList.remove("error", "success");
			return;
		}

		verifyNotice.hidden = false;
		verifyNotice.textContent = message;
		verifyNotice.classList.remove("error", "success");
		verifyNotice.classList.add(type === "success" ? "success" : "error");

		verifyNoticeTimer = window.setTimeout(() => {
			setVerifyNotice("");
		}, NOTICE_AUTO_HIDE_MS);
	};

	const isEmailServerError = (message) => {
		const text = (message || "").trim().toLowerCase();
		return (
			text.includes("email này chưa đăng ký") ||
			text.includes("email khong dung dinh dang") ||
			text.includes("email không đúng định dạng") ||
			text.includes("vui lòng nhập email") ||
			text.includes("vui long nhap email")
		);
	};

	setVerifyNotice("");

	const startResendCountdown = (seconds) => {
		if (!requestCodeBtn) {
			return;
		}

		let remain = seconds;
		requestCodeBtn.disabled = true;
		requestCodeBtn.querySelector("span").textContent = `Gửi lại sau ${remain}s`;

		resendCountdown = setInterval(() => {
			remain -= 1;
			if (remain <= 0) {
				clearInterval(resendCountdown);
				resendCountdown = null;
				requestCodeBtn.disabled = false;
				requestCodeBtn.querySelector("span").textContent = "Nhận mã";
				return;
			}

			requestCodeBtn.querySelector("span").textContent = `Gửi lại sau ${remain}s`;
		}, 1000);
	};

	const validateNewPasswordField = (showEmptyError = false) => {
		if (!newPassword) {
			return false;
		}

		const pwd = newPassword.value || "";
		if (!pwd) {
			if (showEmptyError) {
				setFieldState(newPassword, false);
				if (newPasswordHint) {
					newPasswordHint.textContent = passwordRuleMessage;
					newPasswordHint.classList.remove("success");
				}
				return false;
			}

			resetFieldState(newPassword);
			if (newPasswordHint) {
				newPasswordHint.textContent = "";
				newPasswordHint.classList.remove("success");
			}
			return false;
		}

		const pwdValid = validatePassword(pwd);
		setFieldState(newPassword, pwdValid);

		if (newPasswordHint) {
			newPasswordHint.textContent = pwdValid ? "Mật khẩu mạnh." : passwordRuleMessage;
			newPasswordHint.classList.toggle("success", pwdValid);
		}

		return pwdValid;
	};

	const validateConfirmPasswordField = (showEmptyError = false) => {
		if (!confirmPassword) {
			return false;
		}

		const confirm = confirmPassword.value || "";
		const pwd = newPassword?.value || "";

		if (!confirm) {
			if (showEmptyError) {
				setFieldState(confirmPassword, false);
				if (resetHint) {
					resetHint.textContent = "Vui lòng nhập lại mật khẩu mới.";
					resetHint.classList.remove("success");
				}
				return false;
			}

			resetFieldState(confirmPassword);
			if (resetHint) {
				resetHint.textContent = "";
				resetHint.classList.remove("success");
			}
			return false;
		}

		const confirmValid = pwd === confirm;
		setFieldState(confirmPassword, confirmValid);

		if (resetHint) {
			resetHint.textContent = confirmValid ? "Mật khẩu đã khớp." : "Mật khẩu chưa khớp.";
			resetHint.classList.toggle("success", confirmValid);
		}

		return confirmValid;
	};

	requestCodeBtn?.addEventListener("click", async () => {
		const emailValue = verifyEmail?.value || "";
		const emailValid = validateEmail(emailValue);

		if (verifyEmail) {
			setFieldState(verifyEmail, emailValid);
		}

		if (!emailValid) {
			setVerifyNotice("Vui lòng nhập email hợp lệ để nhận mã.", "error");
			if (verifyHint) {
				verifyHint.textContent = "";
				verifyHint.classList.remove("success");
			}
			return;
		}

		setVerifyNotice("");
		if (verifyHint) {
			verifyHint.textContent = "Đang gửi mã xác nhận...";
			verifyHint.classList.remove("success");
		}

		const result = await postJson(requestCodeUrl, { email: emailValue });
		if (!result.ok) {
			const errorMessage = result.data.message || "Không thể gửi mã xác nhận.";
			setVerifyNotice(errorMessage, "error");
			if (verifyEmail && isEmailServerError(errorMessage)) {
				setFieldState(verifyEmail, false);
			}
			if (verifyHint) {
				verifyHint.textContent = "";
				verifyHint.classList.remove("success");
			}
			return;
		}

		setVerifyNotice(result.data.message || "Mã xác nhận đã được gửi. Vui lòng kiểm tra email của bạn.", "success");
		if (verifyEmail) {
			setFieldState(verifyEmail, true);
		}
		if (verifyHint) {
			verifyHint.textContent = "";
			verifyHint.classList.remove("success");
		}

		startResendCountdown(60);
	});

	verifyForm?.addEventListener("submit", async (event) => {
		event.preventDefault();
		setVerifyNotice("");

		const emailValid = validateEmail(verifyEmail?.value || "");
		const codeValid = validateCode(verifyCode?.value || "");

		if (verifyEmail) {
			setFieldState(verifyEmail, emailValid);
		}
		if (verifyCode) {
			setFieldState(verifyCode, codeValid);
		}

		if (!emailValid || !codeValid) {
			if (verifyHint) {
				verifyHint.textContent = "Vui lòng nhập đúng email và mã xác nhận gồm 6 chữ số.";
				verifyHint.classList.remove("success");
			}
			return;
		}

		const result = await postJson(verifyCodeUrl, {
			email: verifyEmail?.value || "",
			code: verifyCode?.value || ""
		});

		if (!result.ok) {
			const errorMessage = result.data.message || "Mã xác nhận không chính xác.";
			if (errorMessage.toLowerCase().includes("email")) {
				setVerifyNotice(errorMessage, "error");
				if (verifyEmail && isEmailServerError(errorMessage)) {
					setFieldState(verifyEmail, false);
				}
				if (verifyHint) {
					verifyHint.textContent = "";
					verifyHint.classList.remove("success");
				}
				return;
			}

			if (verifyHint) {
				verifyHint.textContent = errorMessage;
				verifyHint.classList.remove("success");
			}
			return;
		}

		setVerifyNotice("");
		if (verifyHint) {
			verifyHint.textContent = result.data.message || "Xác nhận mã thành công. Hãy đặt mật khẩu mới.";
			verifyHint.classList.add("success");
		}
		setStep(2);
	});

	backToCode?.addEventListener("click", () => {
		setStep(1);
		setVerifyNotice("");
	});

	verifyEmail?.addEventListener("input", () => {
		const value = verifyEmail.value || "";
		if (!value.trim()) {
			resetFieldState(verifyEmail);
		} else {
			setFieldState(verifyEmail, validateEmail(value));
		}
		setVerifyNotice("");
	});

	newPassword?.addEventListener("input", () => {
		validateNewPasswordField();
		if ((confirmPassword?.value || "").length > 0) {
			validateConfirmPasswordField();
		}
	});

	newPassword?.addEventListener("blur", () => {
		validateNewPasswordField(true);
	});

	confirmPassword?.addEventListener("input", () => {
		validateConfirmPasswordField();
	});

	confirmPassword?.addEventListener("blur", () => {
		validateConfirmPasswordField(true);
	});

	resetForm?.addEventListener("submit", async (event) => {
		event.preventDefault();

		const pwd = newPassword?.value || "";
		const confirm = confirmPassword?.value || "";
		const pwdValid = validateNewPasswordField(true);
		const confirmValid = validateConfirmPasswordField(true);

		if (!pwdValid || !confirmValid) {
			return;
		}

		const result = await postJson(resetPasswordUrl, {
			password: pwd,
			confirmPassword: confirm
		});

		if (!result.ok) {
			if (resetHint) {
				resetHint.textContent = result.data.message || "Không thể cập nhật mật khẩu.";
				resetHint.classList.remove("success");
			}
			return;
		}

		if (resetHint) {
			resetHint.textContent = result.data.message || "Đổi mật khẩu thành công. Bạn có thể đăng nhập lại.";
			resetHint.classList.add("success");
		}

		if (result.data.redirect) {
			setTimeout(() => {
				window.location.href = result.data.redirect;
			}, 1200);
		}
	});

	toggleButtons.forEach((button) => {
		button.addEventListener("click", () => {
			const shell = button.closest(".input-shell");
			const input = shell?.querySelector("input");
			const icon = button.querySelector("i");

			if (!input || !icon) {
				return;
			}

			const show = input.type === "password";
			input.type = show ? "text" : "password";
			icon.classList.toggle("fa-eye", !show);
			icon.classList.toggle("fa-eye-slash", show);
			button.setAttribute("aria-label", show ? "Ẩn mật khẩu" : "Hiện mật khẩu");
		});
	});
});
