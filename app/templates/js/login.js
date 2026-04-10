function togglePassword() {
	const passwordInput = document.getElementById("password");
	const passwordIcon = document.getElementById("password-icon");

	if (!passwordInput || !passwordIcon) {
		return;
	}

	if (passwordInput.type === "password") {
		passwordInput.type = "text";
		passwordIcon.classList.remove("fa-eye");
		passwordIcon.classList.add("fa-eye-slash");
	} else {
		passwordInput.type = "password";
		passwordIcon.classList.remove("fa-eye-slash");
		passwordIcon.classList.add("fa-eye");
	}
}

document.addEventListener("DOMContentLoaded", () => {
	const FLASH_AUTO_HIDE_MS = 5000;
	const inputs = document.querySelectorAll(".form-input");
	const flashContainer = document.querySelector(".flash-messages");
	const flashAlerts = flashContainer?.querySelectorAll(".alert") || [];

	if (flashAlerts.length > 0) {
		window.setTimeout(() => {
			flashAlerts.forEach((alert) => {
				alert.style.transition = "opacity 0.25s ease";
				alert.style.opacity = "0";
				window.setTimeout(() => alert.remove(), 260);
			});

			window.setTimeout(() => {
				if (flashContainer && !flashContainer.querySelector(".alert")) {
					flashContainer.remove();
				}
			}, 300);
		}, FLASH_AUTO_HIDE_MS);
	}

	inputs.forEach((input) => {
		const wrapper = input.parentElement;
		if (!wrapper) {
			return;
		}

		const syncState = () => {
			if (input.value.trim() !== "" || input === document.activeElement) {
				wrapper.classList.add("focused");
			} else {
				wrapper.classList.remove("focused");
			}
		};

		input.addEventListener("focus", syncState);
		input.addEventListener("blur", syncState);
		input.addEventListener("input", syncState);
		syncState();
	});
});
