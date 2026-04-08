const validators = {
	displayName: (value) => value.trim().length >= 3,
	email: (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()),
	phone: (value) => /^0\d{9,10}$/.test(value.trim()),
	username: (value) => /^[a-zA-Z0-9_]{4,20}$/.test(value.trim()),
	password: (value) => /^(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).{8,}$/.test(value),
	confirmPassword: (value) => value === document.getElementById("password")?.value && value.length > 0
};

const messages = {
	displayName: {
		valid: "Chinh xac!",
		invalid: "Toi thieu 3 ky tu"
	},
	email: {
		valid: "Email hop le",
		invalid: "Email khong dung dinh dang"
	},
	phone: {
		valid: "So dien thoai hop le",
		invalid: "So bat dau bang 0 va gom 10-11 so"
	},
	username: {
		valid: "Chinh xac!",
		invalid: "4-20 ky tu: chu, so hoac _"
	},
	password: {
		valid: "Mat khau manh",
		invalid: "Mat khau it nhat 8 ky tu gom: ky tu hoa, so, dac biet"
	},
	confirmPassword: {
		valid: "Mat khau da khop",
		invalid: "Nhap lai mat khau chua khop"
	},
	avatar: {
		valid: "Tap tin hop le",
		invalid: "Chi chap nhan anh .jpg, .jpeg, .png, .webp"
	}
};

function setFieldState(group, state, text) {
	const icon = group.querySelector(".status-icon");
	const statusText = group.querySelector(".status-text");

	group.classList.remove("valid", "invalid");
	if (icon) {
		icon.classList.remove("fa-circle-check", "fa-circle-exclamation");
	}

	if (state === "valid") {
		group.classList.add("valid");
		if (icon) {
			icon.classList.add("fa-circle-check");
		}
		if (statusText) {
			statusText.textContent = text;
		}
	}

	if (state === "invalid") {
		group.classList.add("invalid");
		if (icon) {
			icon.classList.add("fa-circle-exclamation");
		}
		if (statusText) {
			statusText.textContent = text;
		}
	}

	if (state === "idle" && statusText) {
		statusText.textContent = "";
	}
}

function validateInput(input, isSubmit = false) {
	const field = input.name;
	const group = input.closest(".form-group");
	if (!group || !validators[field]) {
		return true;
	}

	if (!input.value && !isSubmit) {
		setFieldState(group, "idle", "");
		return false;
	}

	const isValid = validators[field](input.value);
	setFieldState(group, isValid ? "valid" : "invalid", isValid ? messages[field].valid : messages[field].invalid);
	return isValid;
}

function validateAvatar(input, isSubmit = false) {
	const group = input.closest(".form-group");
	const fileName = document.getElementById("fileName");
	const file = input.files?.[0];
	const accepted = ["image/jpeg", "image/png", "image/webp"];

	if (!file) {
		if (fileName) {
			fileName.textContent = "Chua chon file";
		}
		if (group) {
			setFieldState(group, isSubmit ? "invalid" : "idle", isSubmit ? "Vui long chon anh dai dien" : "");
		}
		return !isSubmit;
	}

	if (fileName) {
		fileName.textContent = file.name;
	}

	const isValid = accepted.includes(file.type);
	if (group) {
		setFieldState(group, isValid ? "valid" : "invalid", isValid ? messages.avatar.valid : messages.avatar.invalid);
	}
	return isValid;
}

document.addEventListener("DOMContentLoaded", () => {
	const form = document.getElementById("signupForm");
	if (!form) {
		return;
	}

	const inputs = form.querySelectorAll("input[type='text'], input[type='email'], input[type='tel'], input[type='password']");
	const avatarInput = document.getElementById("avatar");
	const passwordToggles = form.querySelectorAll(".toggle-password");

	inputs.forEach((input) => {
		input.addEventListener("input", () => {
			validateInput(input);
			if (input.name === "password") {
				const confirm = document.getElementById("confirmPassword");
				if (confirm && confirm.value) {
					validateInput(confirm);
				}
			}
		});

		input.addEventListener("blur", () => validateInput(input, true));
	});

	if (avatarInput) {
		avatarInput.addEventListener("change", () => validateAvatar(avatarInput));
	}

	passwordToggles.forEach((toggle) => {
		toggle.addEventListener("click", () => {
			const fieldWrap = toggle.closest(".input-shell");
			const input = fieldWrap?.querySelector("input[type='password'], input[type='text']");
			const icon = toggle.querySelector("i");
			if (!input || !icon) {
				return;
			}

			const showPassword = input.type === "password";
			input.type = showPassword ? "text" : "password";
			icon.classList.toggle("fa-eye", !showPassword);
			icon.classList.toggle("fa-eye-slash", showPassword);
			toggle.setAttribute("aria-label", showPassword ? "An mat khau" : "Hien mat khau");
		});
	});

	form.addEventListener("submit", (event) => {
		event.preventDefault();

		let isFormValid = true;

		inputs.forEach((input) => {
			const valid = validateInput(input, true);
			if (!valid) {
				isFormValid = false;
			}
		});

		if (avatarInput && !validateAvatar(avatarInput, true)) {
			isFormValid = false;
		}

		if (isFormValid) {
			console.log("Sign up data is valid");
		}
	});
});
