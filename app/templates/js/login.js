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
	const inputs = document.querySelectorAll(".form-input");

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
