const PENDING_ORDER_KEY_PREFIX = 'tickethub:pendingOrder:';

function formatVND(value) {
	return new Intl.NumberFormat('vi-VN').format(Math.round(Number(value) || 0)) + ' đ';
}

function escapeHtml(text) {
	return String(text || '')
		.replace(/&/g, '&amp;')
		.replace(/</g, '&lt;')
		.replace(/>/g, '&gt;')
		.replace(/"/g, '&quot;')
		.replace(/'/g, '&#39;');
}

function parseJsonScript(id, fallbackValue) {
	const node = document.getElementById(id);
	if (!node) return fallbackValue;

	try {
		const parsed = JSON.parse(node.textContent || 'null');
		return parsed ?? fallbackValue;
	} catch (error) {
		return fallbackValue;
	}
}

function getPageContext() {
	const root = document.getElementById('confirmTicketPage');
	if (!root) return null;

	return {
		root,
		eventId: parseInt(root.dataset.eventId || '0', 10),
		eventTitle: root.dataset.eventTitle || '',
		eventDetailUrl: root.dataset.eventDetailUrl || '/',
		requireFace: root.dataset.requireFace === '1',
	};
}

function getTicketMetaMap(ticketMetaList) {
	const metaMap = new Map();

	(ticketMetaList || []).forEach((item) => {
		const id = String(item.id || '');
		if (!id) return;

		metaMap.set(id, {
			name: item.name || '',
			description: item.description || '',
			price: Number(item.price) || 0,
			remaining: Number(item.remaining) || 0,
		});
	});

	return metaMap;
}

function getPendingOrder(eventId) {
	if (!eventId || eventId <= 0) return null;

	try {
		const raw = localStorage.getItem(PENDING_ORDER_KEY_PREFIX + eventId);
		if (!raw) return null;

		const parsed = JSON.parse(raw);
		if (!parsed || Number(parsed.eventId) !== eventId || !Array.isArray(parsed.tickets)) {
			return null;
		}

		return parsed;
	} catch (error) {
		return null;
	}
}

function normalizeOrder(order, ticketMetaMap) {
	if (!order || !Array.isArray(order.tickets)) return null;

	const tickets = order.tickets
		.map((ticket) => {
			const ticketTypeId = Number(ticket.ticketTypeId) || 0;
			if (!ticketTypeId) return null;

			const meta = ticketMetaMap.get(String(ticketTypeId)) || {};
			const quantity = Math.max(0, parseInt(ticket.quantity || '0', 10));
			if (!quantity) return null;

			const price = Number(ticket.price);
			const normalizedPrice = Number.isFinite(price) ? price : Number(meta.price || 0);

			return {
				ticketTypeId,
				name: ticket.name || meta.name || 'Vé',
				description: ticket.description || meta.description || '',
				quantity,
				price: normalizedPrice,
				subtotal: normalizedPrice * quantity,
			};
		})
		.filter(Boolean);

	if (!tickets.length) return null;

	const subtotal = tickets.reduce((acc, item) => acc + item.subtotal, 0);
	const totalQuantity = tickets.reduce((acc, item) => acc + item.quantity, 0);

	return {
		eventId: Number(order.eventId) || 0,
		eventTitle: order.eventTitle || '',
		tickets,
		subtotal,
		totalQuantity,
	};
}

function formatTicketCount(quantity) {
	return quantity + ' vé';
}

function renderSummary(order) {
	const summaryList = document.getElementById('summaryList');
	const subtotalEl = document.getElementById('summarySubtotal');
	const totalTicketCountEl = document.getElementById('totalTicketCount');

	if (!summaryList || !subtotalEl || !totalTicketCountEl) return;

	summaryList.innerHTML = order.tickets
		.map((item) => {
			return (
				'<div class="summary-item">' +
				'<div>' +
				'<div class="summary-item__name">' + escapeHtml(item.name) + '</div>' +
				'<div class="summary-item__price">' + formatVND(item.price) + '</div>' +
				'</div>' +
				'<div>' +
				'<div class="summary-item__qty">' + item.quantity + '</div>' +
				'<div class="summary-item__subtotal">' + formatVND(item.subtotal) + '</div>' +
				'</div>' +
				'</div>'
			);
		})
		.join('');

	subtotalEl.textContent = formatVND(order.subtotal);
	totalTicketCountEl.textContent = formatTicketCount(order.totalQuantity);
}

function renderTicketHolderRows(item, requireFace) {
	const rows = [];

	for (let idx = 1; idx <= item.quantity; idx += 1) {
		const inputBase = item.ticketTypeId + '-' + idx;
		const faceHint = requireFace ? '<small>Khuôn mặt (bắt buộc)</small>' : '<small>Khuôn mặt (không bắt buộc)</small>';

		rows.push(
			'<div class="ticket-holder" data-holder-key="' + inputBase + '">' +
				'<span class="ticket-holder__label">Vé ' + idx + '</span>' +
				'<div class="ticket-holder__grid">' +
					'<div class="field-group">' +
						'<label for="name-' + inputBase + '">Họ và tên người mua</label>' +
						'<div class="input-with-icon">' +
							'<input id="name-' + inputBase + '" class="js-holder-name" type="text" placeholder="Nguyễn Văn A">' +
							'<i class="fa-solid fa-check field-valid-icon"></i>' +
						'</div>' +
						'<span class="name-helper js-name-helper">chính xác!</span>' +
					'</div>' +
					'<div class="field-group">' +
						'<label for="phone-' + inputBase + '">Số điện thoại</label>' +
						'<div class="input-with-icon">' +
							'<input id="phone-' + inputBase + '" class="js-holder-phone" type="tel" placeholder="0912345678">' +
							'<i class="fa-solid fa-check field-valid-icon"></i>' +
						'</div>' +
						'<span class="name-helper phone-helper js-phone-helper">hợp lệ!</span>' +
					'</div>' +
					'<div class="field-group field-group--full">' +
						'<label for="face-' + inputBase + '">Khuôn mặt</label>' +
						'<input id="face-' + inputBase + '" class="js-holder-face" type="file" accept="image/*" ' + (requireFace ? 'required' : '') + '>' +
						faceHint +
					'</div>' +
				'</div>' +
			'</div>'
		);
	}

	return rows.join('');
}

function renderTicketAccordion(order, requireFace) {
	const accordion = document.getElementById('ticketAccordion');
	if (!accordion) return;

	accordion.innerHTML = order.tickets
		.map((item, index) => {
			const openClass = index === 0 ? ' is-open' : '';
			return (
				'<article class="ticket-group' + openClass + '">' +
					'<button class="ticket-group__header" type="button">' +
						'<span class="ticket-group__title">' +
							'<span>' + escapeHtml(item.name) + '</span>' +
							'<small>' + formatVND(item.price) + ' x ' + item.quantity + '</small>' +
						'</span>' +
						'<i class="fa-solid fa-chevron-down"></i>' +
					'</button>' +
					'<div class="ticket-group__body">' + renderTicketHolderRows(item, requireFace) + '</div>' +
				'</article>'
			);
		})
		.join('');
}

function showEmptyState(ctx) {
	const emptyState = document.getElementById('confirmEmptyState');
	const ticketAccordion = document.getElementById('ticketAccordion');
	const summaryList = document.getElementById('summaryList');
	const subtotalEl = document.getElementById('summarySubtotal');
	const totalTicketCountEl = document.getElementById('totalTicketCount');
	const paymentHint = document.getElementById('paymentHint');
	const payButton = document.getElementById('payButton');

	if (emptyState) emptyState.classList.remove('d-none');
	if (ticketAccordion) {
		ticketAccordion.innerHTML = '';
		ticketAccordion.classList.add('d-none');
	}
	if (summaryList) summaryList.innerHTML = '<p class="summary-empty">Bạn chưa có vé tạm giữ cho sự kiện này.</p>';
	if (subtotalEl) subtotalEl.textContent = formatVND(0);
	if (totalTicketCountEl) totalTicketCountEl.textContent = formatTicketCount(0);

	if (paymentHint) {
		paymentHint.classList.remove('is-valid');
		paymentHint.textContent = 'Vui lòng quay lại để chọn loại vé trước khi thanh toán.';
	}

	if (payButton) {
		payButton.disabled = true;
		payButton.addEventListener('click', function () {
			window.location.href = ctx.eventDetailUrl;
		});
	}
}

function isValidName(value) {
	return String(value || '').trim().length >= 2;
}

function isValidPhone(value) {
	const normalized = String(value || '').replace(/\s+/g, '');
	return /^(0\d{9,10}|\+84\d{9,10})$/.test(normalized);
}

function validateAllHolders(requireFace) {
	const holders = Array.from(document.querySelectorAll('.ticket-holder'));
	if (!holders.length) return false;

	let allValid = true;

	holders.forEach((holder) => {
		const nameInput = holder.querySelector('.js-holder-name');
		const phoneInput = holder.querySelector('.js-holder-phone');
		const faceInput = holder.querySelector('.js-holder-face');
		const nameHelper = holder.querySelector('.js-name-helper');
		const phoneHelper = holder.querySelector('.js-phone-helper');

		const validName = isValidName(nameInput ? nameInput.value : '');
		const validPhone = isValidPhone(phoneInput ? phoneInput.value : '');
		const hasFace = !!(faceInput && faceInput.files && faceInput.files.length > 0);
		const validFace = !requireFace || hasFace;

		if (nameInput) nameInput.classList.toggle('is-valid', validName);
		if (phoneInput) {
			phoneInput.classList.toggle('is-valid', validPhone);
			phoneInput.classList.toggle('is-invalid', !validPhone && String(phoneInput.value || '').trim().length > 0);
		}

		if (nameHelper) nameHelper.classList.toggle('is-visible', validName);
		if (phoneHelper) phoneHelper.classList.toggle('is-visible', validPhone);
		if (faceInput) faceInput.classList.toggle('is-invalid', requireFace && !validFace);

		if (!(validName && validPhone && validFace)) {
			allValid = false;
		}
	});

	return allValid;
}

function updatePaymentState(requireFace) {
	const payButton = document.getElementById('payButton');
	const paymentHint = document.getElementById('paymentHint');
	if (!payButton || !paymentHint) return false;

	const formValid = validateAllHolders(requireFace);
	payButton.disabled = !formValid;
	paymentHint.classList.toggle('is-valid', formValid);
	paymentHint.textContent = formValid
		? 'Thông tin vé đã đầy đủ. Bạn có thể tiếp tục thanh toán.'
		: 'Vui lòng nhập thông tin vé trước khi thanh toán';

	return formValid;
}

function bindAccordionToggle() {
	const accordion = document.getElementById('ticketAccordion');
	if (!accordion) return;

	accordion.addEventListener('click', function (event) {
		const header = event.target.closest('.ticket-group__header');
		if (!header) return;

		const group = header.closest('.ticket-group');
		if (!group) return;

		const shouldOpen = !group.classList.contains('is-open');

		accordion.querySelectorAll('.ticket-group').forEach((item) => {
			item.classList.remove('is-open');
		});

		if (shouldOpen) group.classList.add('is-open');
	});
}

function bindFormValidation(requireFace) {
	const accordion = document.getElementById('ticketAccordion');
	if (!accordion) return;

	accordion.addEventListener('input', function (event) {
		if (event.target.matches('.js-holder-name, .js-holder-phone')) {
			updatePaymentState(requireFace);
		}
	});

	accordion.addEventListener('change', function (event) {
		if (event.target.matches('.js-holder-face')) {
			updatePaymentState(requireFace);
		}
	});
}

function bindPaymentAction(order, ctx) {
	const payButton = document.getElementById('payButton');
	if (!payButton) return;

	payButton.addEventListener('click', function () {
		if (!updatePaymentState(ctx.requireFace)) return;

		alert(
			'Đã xác nhận thông tin cho ' +
			order.totalQuantity +
			' vé của sự kiện "' +
			(ctx.eventTitle || order.eventTitle || 'TicketHub') +
			'". Chức năng tích hợp thanh toán sẽ được bổ sung sau.'
		);
	});
}

document.addEventListener('DOMContentLoaded', function () {
	const ctx = getPageContext();
	if (!ctx || !ctx.eventId) return;

	const ticketMetaMap = getTicketMetaMap(parseJsonScript('confirmTicketTypesData', []));
	const pendingOrder = getPendingOrder(ctx.eventId);
	const normalizedOrder = normalizeOrder(pendingOrder, ticketMetaMap);

	if (!normalizedOrder) {
		showEmptyState(ctx);
		return;
	}

	renderTicketAccordion(normalizedOrder, ctx.requireFace);
	renderSummary(normalizedOrder);
	bindAccordionToggle();
	bindFormValidation(ctx.requireFace);
	bindPaymentAction(normalizedOrder, ctx);
	updatePaymentState(ctx.requireFace);
});
