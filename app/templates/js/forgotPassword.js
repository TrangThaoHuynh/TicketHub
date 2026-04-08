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

function validateEmail(email) {
	return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function validateCode(code) {
	return /^\d{6}$/.test(code.trim());
}

function validatePassword(password) {
	return /^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/.test(password);
}

document.addEventListener("DOMContentLoaded", () => {
	const verifyForm = document.getElementById("verifyForm");
	const resetForm = document.getElementById("resetForm");
	const verifyEmail = document.getElementById("verifyEmail");
	const verifyCode = document.getElementById("verifyCode");
	const verifyHint = document.getElementById("verifyHint");
	const requestCodeBtn = document.getElementById("requestCodeBtn");
	const newPassword = document.getElementById("newPassword");
	const confirmPassword = document.getElementById("confirmPassword");
	const resetHint = document.getElementById("resetHint");
	const backToCode = document.getElementById("backToCode");
	const toggleButtons = document.querySelectorAll(".toggle-password");

	setStep(1);

	let resendCountdown = null;

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

	requestCodeBtn?.addEventListener("click", () => {
		const emailValue = verifyEmail?.value || "";
		const emailValid = validateEmail(emailValue);

		if (verifyEmail) {
			setFieldState(verifyEmail, emailValid);
		}

		if (!emailValid) {
			if (verifyHint) {
				verifyHint.textContent = "Vui lòng nhập email hợp lệ để nhận mã.";
				verifyHint.classList.remove("success");
			}
			return;
		}

		if (verifyHint) {
			verifyHint.textContent = "Mã xác nhận đã được gửi. Vui lòng kiểm tra email của bạn.";
			verifyHint.classList.add("success");
		}

		startResendCountdown(60);
	});

	verifyForm?.addEventListener("submit", (event) => {
		event.preventDefault();

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

		if (verifyHint) {
			verifyHint.textContent = "Xác nhận mã thành công. Hãy đặt mật khẩu mới.";
			verifyHint.classList.add("success");
		}
		setStep(2);
	});

	backToCode?.addEventListener("click", () => {
		setStep(1);
	});

	resetForm?.addEventListener("submit", (event) => {
		event.preventDefault();

		const pwd = newPassword?.value || "";
		const confirm = confirmPassword?.value || "";

		const pwdValid = validatePassword(pwd);
		const confirmValid = pwd === confirm && confirm.length > 0;

		if (newPassword) {
			setFieldState(newPassword, pwdValid);
		}
		if (confirmPassword) {
			setFieldState(confirmPassword, confirmValid);
		}

		if (!pwdValid || !confirmValid) {
			if (resetHint) {
				resetHint.textContent = "Mật khẩu chưa hợp lệ hoặc chưa khớp.";
				resetHint.classList.remove("success");
			}
			return;
		}

		if (resetHint) {
			resetHint.textContent = "Đổi mật khẩu thành công. Bạn có thể đăng nhập lại.";
			resetHint.classList.add("success");
		}

		console.log("Password reset success");
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
