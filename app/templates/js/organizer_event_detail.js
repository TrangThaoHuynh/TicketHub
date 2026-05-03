document.addEventListener("DOMContentLoaded", function () {
	const ticketChips = Array.from(document.querySelectorAll("[data-ticket-chip]"));
	const ticketPriceValue = document.getElementById("ticketPriceValue");
	const eventStatusValue = document.getElementById("eventStatusValue");
	const openTicketAdjustButton = document.querySelector("[data-action='open-ticket-adjust']");
	const editButton = document.querySelector("[data-action='edit-event']");
	const deleteButton = document.querySelector("[data-action='delete-event']");
	const eventInfoBox = document.querySelector(".js-event-info");
	const eventInfoContent = document.querySelector(".js-event-info-content");
	const eventInfoToggle = document.querySelector(".js-event-info-toggle");
	const noticeStack = document.getElementById("orgDetailNoticeStack");
	const noticeItems = noticeStack ? Array.from(noticeStack.querySelectorAll(".js-org-detail-notice")) : [];
	const eventDeleteHideModal = document.getElementById("eventDeleteHideModal");
	const confirmDeleteEventBtn = document.getElementById("confirmDeleteEventBtn");

	let isDeletingOrHidingEvent = false;

	const ticketAdjustModal = document.getElementById("ticketAdjustModal");
	const ticketAdjustTabs = document.getElementById("ticketAdjustTabs");
	const ticketAdjustForm = document.getElementById("ticketAdjustForm");
	const ticketAdjustInitialDataScript = document.getElementById("ticketAdjustInitialData");
	const organizerEventDetailContextScript = document.getElementById("organizerEventDetailContext");
	const ticketAdjustUpdateUrl = ticketAdjustModal ? (ticketAdjustModal.getAttribute("data-update-url") || "") : "";
	const adjustTicketTypeIdInput = document.getElementById("adjustTicketTypeId");
	const adjustTicketTypeName = document.getElementById("adjustTicketTypeName");
	const adjustCustomPriceCheckbox = document.getElementById("adjustCustomPrice");
	const adjustSuggestedPriceCheckbox = document.getElementById("adjustSuggestedPrice");
	const adjustPriceInput = document.getElementById("adjustPriceInput");
	const adjustSuggestedPriceInput = document.getElementById("adjustSuggestedPriceInput");
	const adjustQtyMinusBtn = document.getElementById("adjustQtyMinus");
	const adjustQtyPlusBtn = document.getElementById("adjustQtyPlus");
	const adjustRemainingQtyInput = document.getElementById("adjustRemainingQtyInput");
	const adjustSaleStartInput = document.getElementById("adjustSaleStartInput");
	const adjustSaleEndInput = document.getElementById("adjustSaleEndInput");
	const adjustTicketDescInput = document.getElementById("adjustTicketDescInput");
	const adjustSubmitBtn = ticketAdjustForm ? ticketAdjustForm.querySelector("button[type='submit']") : null;

	const suggestedPriceByTicketId = new Map();
	let isSuggestingPrice = false;
	let activeAdjustTicketIndex = 0;

	function parseEventDetailContext() {
		if (!organizerEventDetailContextScript) {
			return {};
		}

		try {
			const raw = JSON.parse(organizerEventDetailContextScript.textContent || "{}");
			return raw && typeof raw === "object" ? raw : {};
		} catch (e) {
			return {};
		}
	}

	const eventDetailContext = parseEventDetailContext();

	function parseAdjustInitialData() {
		if (!ticketAdjustInitialDataScript) {
			return [];
		}

		try {
			const raw = JSON.parse(ticketAdjustInitialDataScript.textContent || "[]");
			if (!Array.isArray(raw)) {
				return [];
			}
			return raw;
		} catch (e) {
			return [];
		}
	}

	function normalizePrice(value) {
		const parsed = Number(value);
		if (!Number.isFinite(parsed) || parsed < 0) {
			return "0";
		}
		return String(Math.round(parsed));
	}

	function normalizeQuantity(value) {
		const parsed = Number(value);
		if (!Number.isFinite(parsed) || parsed < 0) {
			return 0;
		}
		return Math.floor(parsed);
	}

	function normalizeTicketAdjustItem(rawTicket) {
		const ticketId = Number(rawTicket && rawTicket.id);
		return {
			id: Number.isInteger(ticketId) && ticketId > 0 ? ticketId : null,
			name: String((rawTicket && rawTicket.name) || "").trim(),
			price: normalizePrice(rawTicket && rawTicket.price),
			remainingQuantity: normalizeQuantity(rawTicket && rawTicket.remainingQuantity),
			soldQuantity: normalizeQuantity(rawTicket && rawTicket.soldQuantity),
			saleStart: String((rawTicket && rawTicket.saleStart) || ""),
			saleEnd: String((rawTicket && rawTicket.saleEnd) || ""),
			description: String((rawTicket && rawTicket.description) || ""),
		};
	}

	const ticketAdjustItems = parseAdjustInitialData().map(normalizeTicketAdjustItem);

	function formatVnd(amount) {
		const parsed = Number(amount || 0);
		return parsed.toLocaleString("vi-VN") + " đ";
	}

	function normalizeStatus(status) {
		const text = String(status || "").trim().toUpperCase();
		if (!text) {
			return "PENDING";
		}
		return text;
	}

	function setSuggestPriceLoading(isLoading) {
		isSuggestingPrice = Boolean(isLoading);
		if (adjustSubmitBtn) {
			adjustSubmitBtn.disabled = isSuggestingPrice;
		}
		if (adjustSuggestedPriceCheckbox) {
			adjustSuggestedPriceCheckbox.disabled = isSuggestingPrice;
		}
		if (adjustCustomPriceCheckbox) {
			adjustCustomPriceCheckbox.disabled = isSuggestingPrice;
		}
		if (adjustSuggestedPriceInput) {
			adjustSuggestedPriceInput.value = isSuggestingPrice ? "Đang gợi ý..." : (adjustSuggestedPriceInput.value || "");
		}
	}

	function getActiveTicketForAdjust() {
		return ticketAdjustItems && ticketAdjustItems.length ? ticketAdjustItems[activeAdjustTicketIndex] : null;
	}

	function getSuggestedPriceForTicket(ticket) {
		if (!ticket || !ticket.id) {
			return null;
		}
		const cached = suggestedPriceByTicketId.get(ticket.id);
		return cached != null ? String(cached) : null;
	}

	function getEventContextValue(key, fallback) {
		if (!eventDetailContext || typeof eventDetailContext !== "object") {
			return fallback;
		}
		if (!(key in eventDetailContext)) {
			return fallback;
		}
		return eventDetailContext[key];
	}

	function buildSuggestPricePayload(ticket, saleStartValue, saleEndValue, remainingQty) {
		const eventIdRaw = getEventContextValue("eventId", null);
		const eventTypeIdRaw = getEventContextValue("eventTypeId", null);
		const locationRaw = getEventContextValue("location", "");
		const startTimeRaw = getEventContextValue("startTime", "");
		const endTimeRaw = getEventContextValue("endTime", "");
		const hasFaceRegRaw = getEventContextValue("hasFaceReg", true);
		const limitQuantityRaw = getEventContextValue("limitQuantity", null);

		const eventId = Number(eventIdRaw);
		const eventTypeId = Number(eventTypeIdRaw);
		const limitQuantity = limitQuantityRaw == null || limitQuantityRaw === "" ? null : Number(limitQuantityRaw);

		const sold = normalizeQuantity(ticket ? ticket.soldQuantity : 0);
		const remaining = normalizeQuantity(remainingQty);
		const totalTicketQuantity = sold + remaining;

		return {
			event: {
				eventId: Number.isFinite(eventId) ? eventId : null,
				eventTypeId: Number.isFinite(eventTypeId) ? eventTypeId : null,
				location: String(locationRaw || "").trim(),
				startTime: String(startTimeRaw || "").trim(),
				endTime: String(endTimeRaw || "").trim(),
				hasFaceReg: Boolean(hasFaceRegRaw),
				limitQuantity: Number.isFinite(limitQuantity) && limitQuantity > 0 ? limitQuantity : null,
			},
			tickets: [
				{
					ticketTypeName: String((ticket && ticket.name) || "").trim(),
					ticketQuantity: totalTicketQuantity,
					saleStart: String(saleStartValue || "").trim(),
					saleEnd: String(saleEndValue || "").trim(),
				},
			],
		};
	}

	function validateSuggestPayload(payload) {
		const event = payload && payload.event ? payload.event : null;
		const tickets = payload && Array.isArray(payload.tickets) ? payload.tickets : [];
		const firstTicket = tickets.length ? tickets[0] : null;

		if (!event || !firstTicket) {
			window.alert("Dữ liệu gợi ý giá vé không hợp lệ.");
			return false;
		}
		if (!event.eventId) {
			window.alert("Không tìm thấy sự kiện để gợi ý giá vé.");
			return false;
		}
		if (!event.eventTypeId) {
			window.alert("Thiếu thể loại sự kiện nên không thể gợi ý giá vé.");
			return false;
		}
		if (!event.location) {
			window.alert("Thiếu địa điểm nên không thể gợi ý giá vé.");
			return false;
		}
		if (!event.startTime || !event.endTime) {
			window.alert("Thiếu thời gian sự kiện nên không thể gợi ý giá vé.");
			return false;
		}
		if (!firstTicket.ticketTypeName) {
			window.alert("Thiếu tên vé nên không thể gợi ý giá vé.");
			return false;
		}
		if (!firstTicket.ticketQuantity || Number(firstTicket.ticketQuantity) <= 0) {
			window.alert("Số lượng vé phải lớn hơn 0 để gợi ý giá.");
			return false;
		}
		if (!firstTicket.saleStart || !firstTicket.saleEnd) {
			window.alert("Vui lòng nhập đầy đủ thời gian bán vé trước khi gợi ý giá.");
			return false;
		}
		if (new Date(event.endTime) < new Date(event.startTime)) {
			window.alert("Thời gian kết thúc sự kiện phải sau thời gian bắt đầu.");
			return false;
		}
		if (new Date(firstTicket.saleEnd) < new Date(firstTicket.saleStart)) {
			window.alert("Thời gian kết thúc bán vé phải sau thời gian bắt đầu.");
			return false;
		}

		return true;
	}

	async function fetchSuggestedPriceForActiveTicket() {
		const ticket = getActiveTicketForAdjust();
		if (!ticket || !ticket.id) {
			return null;
		}

		const saleStartValue = adjustSaleStartInput ? (adjustSaleStartInput.value || "") : "";
		const saleEndValue = adjustSaleEndInput ? (adjustSaleEndInput.value || "") : "";
		const remainingQty = adjustRemainingQtyInput ? adjustRemainingQtyInput.value : 0;
		const payload = buildSuggestPricePayload(ticket, saleStartValue, saleEndValue, remainingQty);
		if (!validateSuggestPayload(payload)) {
			return null;
		}

		setSuggestPriceLoading(true);
		try {
			const response = await fetch("/api/organizer/ticket-types/suggest-price", {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
				},
				body: JSON.stringify(payload),
			});

			if (response.status === 401) {
				throw new Error("unauthorized");
			}

			const result = await response.json().catch(function () {
				return {};
			});

			if (!response.ok) {
				throw new Error(result.message || "Không thể gợi ý giá vé.");
			}

			const suggestions = result && Array.isArray(result.suggestions) ? result.suggestions : [];
			const first = suggestions.length ? suggestions[0] : null;
			const suggested = first && typeof first.suggestedPrice === "number" ? first.suggestedPrice : null;
			if (!Number.isFinite(suggested) || suggested < 0) {
				throw new Error("Không nhận được giá gợi ý hợp lệ.");
			}

			suggestedPriceByTicketId.set(ticket.id, Math.round(suggested));
			return String(Math.round(suggested));
		} catch (error) {
			if (String(error && error.message) === "unauthorized") {
				window.alert("Bạn cần đăng nhập tài khoản nhà tổ chức để dùng chức năng này.");
				return null;
			}
			window.alert(error.message || "Không thể gợi ý giá vé.");
			return null;
		} finally {
			setSuggestPriceLoading(false);
		}
	}

	function setActiveTicketChip(nextChip) {
		if (!nextChip) {
			return;
		}

		ticketChips.forEach(function (chip) {
			chip.classList.remove("is-active");
		});
		nextChip.classList.add("is-active");

		const nextPrice = nextChip.getAttribute("data-price") || 0;
		const nextStatus = nextChip.getAttribute("data-status") || "PENDING";

		if (ticketPriceValue) {
			ticketPriceValue.textContent = formatVnd(nextPrice);
		}
		if (eventStatusValue) {
			eventStatusValue.textContent = normalizeStatus(nextStatus);
		}
	}

	ticketChips.forEach(function (chip) {
		chip.addEventListener("click", function () {
			setActiveTicketChip(chip);
		});
	});

	if (ticketChips.length > 0) {
		const initialActiveChip = ticketChips.find(function (chip) {
			return chip.classList.contains("is-active");
		}) || ticketChips[0];

		setActiveTicketChip(initialActiveChip);
	}

	function dismissNoticeItem(noticeItem) {
		if (!noticeItem || !noticeItem.parentNode) {
			return;
		}

		noticeItem.style.opacity = "0";
		noticeItem.style.transform = "translateY(-4px)";

		window.setTimeout(function () {
			if (noticeItem.parentNode) {
				noticeItem.remove();
			}
			if (noticeStack && !noticeStack.querySelector(".js-org-detail-notice")) {
				noticeStack.remove();
			}
		}, 240);
	}

	if (noticeStack && noticeItems.length) {
		noticeStack.addEventListener("click", function (e) {
			const closeBtn = e.target.closest(".js-org-detail-notice-close");
			if (!closeBtn) {
				return;
			}

			const targetNotice = closeBtn.closest(".js-org-detail-notice");
			dismissNoticeItem(targetNotice);
		});

		noticeItems.forEach(function (noticeItem, index) {
			window.setTimeout(function () {
				dismissNoticeItem(noticeItem);
			}, 5500 + index * 120);
		});
	}

	function syncEventInfoOverflow() {
		if (!eventInfoBox || !eventInfoContent || !eventInfoToggle) {
			return;
		}

		const wasExpanded = eventInfoBox.classList.contains("is-expanded");
		eventInfoBox.classList.remove("is-expanded");
		eventInfoBox.classList.add("is-collapsed");

		const isOverflowing = eventInfoContent.scrollHeight > eventInfoContent.clientHeight + 2;
		if (!isOverflowing) {
			eventInfoBox.classList.remove("is-collapsed");
			eventInfoToggle.classList.add("is-hidden");
			eventInfoToggle.setAttribute("aria-expanded", "true");
			return;
		}

		eventInfoToggle.classList.remove("is-hidden");
		if (wasExpanded) {
			eventInfoBox.classList.remove("is-collapsed");
			eventInfoBox.classList.add("is-expanded");
			eventInfoToggle.setAttribute("aria-expanded", "true");
		} else {
			eventInfoToggle.setAttribute("aria-expanded", "false");
		}
	}

	if (eventInfoToggle && eventInfoBox) {
		eventInfoToggle.addEventListener("click", function () {
			const isExpanded = eventInfoBox.classList.contains("is-expanded");
			if (isExpanded) {
				eventInfoBox.classList.remove("is-expanded");
				eventInfoBox.classList.add("is-collapsed");
				eventInfoToggle.setAttribute("aria-expanded", "false");
				return;
			}

			eventInfoBox.classList.remove("is-collapsed");
			eventInfoBox.classList.add("is-expanded");
			eventInfoToggle.setAttribute("aria-expanded", "true");
		});
	}

	window.addEventListener("resize", function () {
		window.requestAnimationFrame(syncEventInfoOverflow);
	});
	window.addEventListener("load", function () {
		window.requestAnimationFrame(syncEventInfoOverflow);
	});

	if (eventInfoContent && typeof ResizeObserver !== "undefined") {
		const eventInfoObserver = new ResizeObserver(function () {
			window.requestAnimationFrame(syncEventInfoOverflow);
		});
		eventInfoObserver.observe(eventInfoContent);
	}

	window.setTimeout(syncEventInfoOverflow, 0);

	function openTicketAdjustModal() {
		if (!ticketAdjustModal) {
			return;
		}
		if (!ticketAdjustItems.length) {
			window.alert("Su kien nay chua co loai ve de dieu chinh.");
			return;
		}

		const activeMainChip = ticketChips.find(function (chip) {
			return chip.classList.contains("is-active");
		});
		if (activeMainChip) {
			const activeTicketId = Number(activeMainChip.getAttribute("data-ticket-id"));
			const matchedIndex = ticketAdjustItems.findIndex(function (ticket) {
				return ticket.id === activeTicketId;
			});
			if (matchedIndex >= 0) {
				activeAdjustTicketIndex = matchedIndex;
			}
		}

		renderTicketAdjustTabs();
		activateAdjustTicket(activeAdjustTicketIndex);
		ticketAdjustModal.classList.remove("is-hidden");
		document.body.classList.add("is-modal-open");
	}

	function closeTicketAdjustModal() {
		if (!ticketAdjustModal) {
			return;
		}
		ticketAdjustModal.classList.add("is-hidden");
		document.body.classList.remove("is-modal-open");
	}

	function syncAdjustPriceMode() {
		if (!adjustPriceInput || !adjustCustomPriceCheckbox || !adjustSuggestedPriceCheckbox) {
			return;
		}

		if (adjustSuggestedPriceCheckbox.checked) {
			adjustCustomPriceCheckbox.checked = false;
			if (adjustPriceInput) {
				const ticket = getActiveTicketForAdjust();
				const suggested = getSuggestedPriceForTicket(ticket);
				if (suggested != null) {
					adjustPriceInput.value = normalizePrice(suggested);
				}
			}
			adjustPriceInput.disabled = true;
			return;
		}

		if (!adjustCustomPriceCheckbox.checked) {
			adjustCustomPriceCheckbox.checked = true;
		}

		adjustPriceInput.disabled = false;

		if (!String(adjustPriceInput.value || "").trim()) {
			const activeTicket = ticketAdjustItems[activeAdjustTicketIndex];
			adjustPriceInput.value = normalizePrice(activeTicket ? activeTicket.price : 0);
			return;
		}

		adjustPriceInput.value = normalizePrice(adjustPriceInput.value);
	}

	function renderTicketAdjustTabs() {
		if (!ticketAdjustTabs) {
			return;
		}
		ticketAdjustTabs.innerHTML = "";

		ticketAdjustItems.forEach(function (ticket, index) {
			const tabButton = document.createElement("button");
			tabButton.type = "button";
			tabButton.className = "ticket-adjust-tab" + (index === activeAdjustTicketIndex ? " is-active" : "");
			tabButton.textContent = ticket.name || ("Loại " + String(index + 1));
			tabButton.setAttribute("role", "tab");
			tabButton.setAttribute("aria-selected", index === activeAdjustTicketIndex ? "true" : "false");
			tabButton.addEventListener("click", function () {
				activateAdjustTicket(index);
			});
			ticketAdjustTabs.appendChild(tabButton);
		});
	}

	function activateAdjustTicket(index) {
		if (!ticketAdjustItems.length) {
			return;
		}
		if (index < 0 || index >= ticketAdjustItems.length) {
			return;
		}

		activeAdjustTicketIndex = index;
		const targetTicket = ticketAdjustItems[index];

		if (adjustTicketTypeIdInput) {
			adjustTicketTypeIdInput.value = targetTicket.id ? String(targetTicket.id) : "";
		}
		if (adjustTicketTypeName) {
			adjustTicketTypeName.textContent = targetTicket.name || "-";
		}
		if (adjustPriceInput) {
			adjustPriceInput.value = normalizePrice(targetTicket.price);
		}
		if (adjustSuggestedPriceInput) {
			const cachedSuggested = getSuggestedPriceForTicket(targetTicket);
			adjustSuggestedPriceInput.value = cachedSuggested != null ? cachedSuggested : "";
			adjustSuggestedPriceInput.setAttribute("readonly", "readonly");
		}
		if (adjustRemainingQtyInput) {
			adjustRemainingQtyInput.value = String(normalizeQuantity(targetTicket.remainingQuantity));
		}
		if (adjustSaleStartInput) {
			adjustSaleStartInput.value = targetTicket.saleStart || "";
		}
		if (adjustSaleEndInput) {
			adjustSaleEndInput.value = targetTicket.saleEnd || "";
		}
		if (adjustTicketDescInput) {
			adjustTicketDescInput.value = targetTicket.description || "";
		}

		if (adjustCustomPriceCheckbox) {
			adjustCustomPriceCheckbox.checked = true;
		}
		if (adjustSuggestedPriceCheckbox) {
			adjustSuggestedPriceCheckbox.checked = false;
		}
		syncAdjustPriceMode();

		renderTicketAdjustTabs();
	}

	function syncMainTicketChipPrice(ticketId, nextPrice) {
		const targetChip = ticketChips.find(function (chip) {
			return Number(chip.getAttribute("data-ticket-id")) === Number(ticketId);
		});

		if (!targetChip) {
			return;
		}

		targetChip.setAttribute("data-price", String(nextPrice || "0"));
		if (targetChip.classList.contains("is-active")) {
			setActiveTicketChip(targetChip);
		}
	}

	if (openTicketAdjustButton) {
		openTicketAdjustButton.addEventListener("click", openTicketAdjustModal);
	}

	if (ticketAdjustModal) {
		ticketAdjustModal.addEventListener("click", function (e) {
			if (e.target.closest("[data-close-ticket-adjust]")) {
				closeTicketAdjustModal();
			}
		});
	}

	document.addEventListener("keydown", function (e) {
		if (e.key !== "Escape") {
			return;
		}
		if (!ticketAdjustModal || ticketAdjustModal.classList.contains("is-hidden")) {
			return;
		}
		closeTicketAdjustModal();
	});

	if (adjustSuggestedPriceCheckbox) {
		adjustSuggestedPriceCheckbox.addEventListener("change", function () {
			if (adjustSuggestedPriceCheckbox.checked && adjustCustomPriceCheckbox) {
				adjustCustomPriceCheckbox.checked = false;
			}

			if (adjustSuggestedPriceCheckbox.checked) {
				syncAdjustPriceMode();
				fetchSuggestedPriceForActiveTicket().then(function (suggested) {
					if (!adjustSuggestedPriceCheckbox.checked) {
						return;
					}
					if (suggested == null) {
						adjustSuggestedPriceCheckbox.checked = false;
						if (adjustCustomPriceCheckbox) {
							adjustCustomPriceCheckbox.checked = true;
						}
						syncAdjustPriceMode();
						return;
					}
					if (adjustSuggestedPriceInput) {
						adjustSuggestedPriceInput.value = suggested;
					}
					syncAdjustPriceMode();
				});
				return;
			}

			syncAdjustPriceMode();
		});
	}

	if (adjustCustomPriceCheckbox) {
		adjustCustomPriceCheckbox.addEventListener("change", function () {
			if (adjustCustomPriceCheckbox.checked && adjustSuggestedPriceCheckbox) {
				adjustSuggestedPriceCheckbox.checked = false;
			}
			syncAdjustPriceMode();
		});
	}

	if (adjustPriceInput) {
		adjustPriceInput.addEventListener("input", function () {
			adjustPriceInput.value = adjustPriceInput.value.replace(/\D+/g, "");
		});
	}

	if (adjustRemainingQtyInput) {
		adjustRemainingQtyInput.addEventListener("input", function () {
			adjustRemainingQtyInput.value = String(normalizeQuantity(adjustRemainingQtyInput.value));
		});
	}

	if (adjustQtyMinusBtn && adjustRemainingQtyInput) {
		adjustQtyMinusBtn.addEventListener("click", function () {
			const currentValue = normalizeQuantity(adjustRemainingQtyInput.value);
			adjustRemainingQtyInput.value = String(Math.max(0, currentValue - 1));
		});
	}

	if (adjustQtyPlusBtn && adjustRemainingQtyInput) {
		adjustQtyPlusBtn.addEventListener("click", function () {
			const currentValue = normalizeQuantity(adjustRemainingQtyInput.value);
			adjustRemainingQtyInput.value = String(currentValue + 1);
		});
	}

	if (ticketAdjustForm) {
		ticketAdjustForm.addEventListener("submit", async function (e) {
			e.preventDefault();

			if (!ticketAdjustUpdateUrl) {
				window.alert("Không tìm thấy đường dẫn cập nhật loại vé.");
				return;
			}

			const currentTicket = ticketAdjustItems[activeAdjustTicketIndex];
			if (!currentTicket || !currentTicket.id) {
				window.alert("Không tìm thấy loại vé để cập nhật.");
				return;
			}

			syncAdjustPriceMode();

			const payloadPrice = adjustSuggestedPriceCheckbox && adjustSuggestedPriceCheckbox.checked
				? normalizePrice(adjustSuggestedPriceInput ? adjustSuggestedPriceInput.value : 0)
				: normalizePrice(adjustPriceInput ? adjustPriceInput.value : 0);

			if (adjustSuggestedPriceCheckbox && adjustSuggestedPriceCheckbox.checked) {
				if (!String(payloadPrice || "").trim() || payloadPrice === "0") {
					window.alert("Chưa có giá gợi ý hợp lệ. Vui lòng thử lại.");
					return;
				}
			}

			const remainingQty = normalizeQuantity(adjustRemainingQtyInput ? adjustRemainingQtyInput.value : 0);
			const saleStartValue = adjustSaleStartInput ? (adjustSaleStartInput.value || "") : "";
			const saleEndValue = adjustSaleEndInput ? (adjustSaleEndInput.value || "") : "";

			if (!saleStartValue || !saleEndValue) {
				window.alert("Vui lòng nhập đầy đủ thời gian bắt đầu và kết thúc bán vé.");
				return;
			}

			if (new Date(saleEndValue) < new Date(saleStartValue)) {
				window.alert("Thời gian kết thúc bán vé phải sau thời gian bắt đầu.");
				return;
			}

			const requestPayload = {
				ticketTypeId: currentTicket.id,
				price: payloadPrice,
				remainingQuantity: remainingQty,
				saleStart: saleStartValue,
				saleEnd: saleEndValue,
				description: adjustTicketDescInput ? (adjustTicketDescInput.value || "") : "",
			};

			if (adjustSubmitBtn) {
				adjustSubmitBtn.disabled = true;
			}

			try {
				const response = await fetch(ticketAdjustUpdateUrl, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify(requestPayload),
				});

				const result = await response.json().catch(function () {
					return {};
				});

				if (!response.ok) {
					throw new Error(result.message || "Không thể cập nhật loại vé.");
				}

				const updatedTicket = normalizeTicketAdjustItem(result.ticket || {});
				ticketAdjustItems[activeAdjustTicketIndex] = {
					...ticketAdjustItems[activeAdjustTicketIndex],
					...updatedTicket,
				};

				activateAdjustTicket(activeAdjustTicketIndex);
				syncMainTicketChipPrice(updatedTicket.id, updatedTicket.price);

				window.alert(result.message || "Cập nhật loại vé thành công.");
			} catch (error) {
				window.alert(error.message || "Không thể cập nhật loại vé.");
			} finally {
				if (adjustSubmitBtn) {
					adjustSubmitBtn.disabled = false;
				}
			}
		});
	}

	if (editButton) {
		editButton.addEventListener("click", function () {
			const editUrl = editButton.getAttribute("data-edit-url");
			if (!editUrl) {
				return;
			}
			window.location.href = editUrl;
		});
	}

	if (deleteButton) {
		deleteButton.addEventListener("click", function () {
			if (!eventDeleteHideModal) {
				return;
			}

			eventDeleteHideModal.classList.remove("is-hidden");
			document.body.classList.add("is-modal-open");
		});
	}

	function closeEventDeleteHideModal() {
		if (!eventDeleteHideModal) {
			return;
		}
		eventDeleteHideModal.classList.add("is-hidden");
		document.body.classList.remove("is-modal-open");
	}

	if (eventDeleteHideModal) {
		eventDeleteHideModal.addEventListener("click", function (e) {
			if (e.target.closest("[data-close-event-action]")) {
				closeEventDeleteHideModal();
			}
		});
	}

	if (confirmDeleteEventBtn && deleteButton) {
		confirmDeleteEventBtn.addEventListener("click", async function () {
			if (isDeletingOrHidingEvent) {
				return;
			}

			const actionUrl = deleteButton.getAttribute("data-delete-hide-url") || "";
			if (!actionUrl) {
				return;
			}

			isDeletingOrHidingEvent = true;
			confirmDeleteEventBtn.disabled = true;

			try {
				const response = await fetch(actionUrl, {
					method: "POST",
					headers: {
						"Content-Type": "application/json",
					},
					body: JSON.stringify({}),
				});

				const result = await response.json().catch(function () {
					return {};
				});

				if (!response.ok) {
					throw new Error(result.message || "Không thể xử lý sự kiện.");
				}

				if (result.redirectUrl) {
					window.location.href = result.redirectUrl;
					return;
				}
				window.location.reload();
			} catch (error) {
				console.error(error.message || "Không thể xử lý sự kiện.");
				confirmDeleteEventBtn.disabled = false;
				isDeletingOrHidingEvent = false;
			}
		});
	}

	document.addEventListener("keydown", function (e) {
		if (e.key !== "Escape") {
			return;
		}

		if (eventDeleteHideModal && !eventDeleteHideModal.classList.contains("is-hidden")) {
			closeEventDeleteHideModal();
			return;
		}
	});
});
