const PENDING_ORDER_KEY_PREFIX = "tickethub:pendingOrder:";

function formatVND(n) {
  return (
    new Intl.NumberFormat("vi-VN").format(Math.round(Number(n) || 0)) + " VNĐ"
  );
}

function clampQty(value, max) {
  let normalized = parseInt(value || "0", 10);
  if (isNaN(normalized) || normalized < 0) normalized = 0;
  if (max > 0 && normalized > max) normalized = max;
  return normalized;
}

function recalcSubtotal() {
  let sum = 0;
  document.querySelectorAll(".qty-input").forEach((inp) => {
    if (inp.disabled) return;

    const max = parseInt(inp.getAttribute("max") || "0", 10);
    const qty = clampQty(inp.value, max);
    const price = parseFloat(inp.dataset.price || "0");

    inp.value = qty;
    if (qty > 0 && price >= 0) sum += qty * price;
  });

  const subtotalEl = document.getElementById("subtotal");
  if (subtotalEl) subtotalEl.textContent = formatVND(sum);

  const submitBtn = document.getElementById("btnSubmit");
  if (submitBtn) submitBtn.disabled = sum <= 0;
}

function changeQty(id, delta, max) {
  const el = document.getElementById("qty-" + id);
  if (!el || el.disabled) return;

  const cur = parseInt(el.value || "0", 10);
  let next = cur + delta;

  if (next < 0) next = 0;
  if (typeof max === "number" && next > max) next = max;

  el.value = next;
  recalcSubtotal();
}

function collectSelectedTickets() {
  const selectedTickets = [];

  document.querySelectorAll(".qty-input").forEach((inp) => {
    if (inp.disabled) return;

    const qty = parseInt(inp.value || "0", 10);
    if (!qty || qty <= 0) return;

    const ticketTypeId = parseInt(inp.dataset.ticketId || "0", 10);
    const ticketName = inp.dataset.ticketName || "";
    const ticketDescription = inp.dataset.ticketDescription || "";
    const price = parseFloat(inp.dataset.price || "0");

    selectedTickets.push({
      ticketTypeId,
      name: ticketName,
      description: ticketDescription,
      price,
      quantity: qty,
      subtotal: qty * price,
    });
  });

  return selectedTickets;
}

function savePendingOrder() {
  const submitBtn = document.getElementById("btnSubmit");
  if (!submitBtn) return null;

  const eventId = parseInt(submitBtn.dataset.eventId || "0", 10);
  if (!eventId || eventId <= 0) return null;

  const tickets = collectSelectedTickets();
  if (!tickets.length) return null;

  const totalQuantity = tickets.reduce((acc, item) => acc + item.quantity, 0);
  const subtotal = tickets.reduce((acc, item) => acc + item.subtotal, 0);

  const payload = {
    eventId,
    eventTitle: submitBtn.dataset.eventTitle || "",
    createdAt: new Date().toISOString(),
    totalQuantity,
    subtotal,
    tickets,
  };

  try {
    const key = PENDING_ORDER_KEY_PREFIX + eventId;
    localStorage.setItem(key, JSON.stringify(payload));
    localStorage.setItem("tickethub:lastPendingOrderKey", key);
    return payload;
  } catch (error) {
    return null;
  }
}

function restorePendingOrder() {
  const submitBtn = document.getElementById("btnSubmit");
  if (!submitBtn) return;

  const eventId = parseInt(submitBtn.dataset.eventId || "0", 10);
  if (!eventId || eventId <= 0) return;

  let parsed = null;
  try {
    parsed = JSON.parse(
      localStorage.getItem(PENDING_ORDER_KEY_PREFIX + eventId) || "null",
    );
  } catch (error) {
    parsed = null;
  }

  if (
    !parsed ||
    Number(parsed.eventId) !== eventId ||
    !Array.isArray(parsed.tickets)
  )
    return;

  const qtyByType = new Map();
  parsed.tickets.forEach((item) => {
    const typeId = String(item.ticketTypeId || "");
    const quantity = parseInt(item.quantity || "0", 10);
    if (!typeId || !quantity || quantity <= 0) return;
    qtyByType.set(typeId, quantity);
  });

  document.querySelectorAll(".qty-input").forEach((inp) => {
    const typeId = String(inp.dataset.ticketId || "");
    if (!qtyByType.has(typeId)) return;

    const max = parseInt(inp.getAttribute("max") || "0", 10);
    inp.value = clampQty(qtyByType.get(typeId), max);
  });
}

function goToConfirmPage() {
  const submitBtn = document.getElementById("btnSubmit");
  if (!submitBtn || submitBtn.disabled) return;

  const payload = savePendingOrder();
  if (!payload || !payload.tickets || payload.tickets.length === 0) {
    alert("Vui lòng chọn ít nhất một loại vé để tiếp tục.");
    return;
  }

  const confirmUrl = submitBtn.dataset.confirmUrl || "";
  if (!confirmUrl) {
    alert("Không tìm thấy trang xác nhận thông tin vé.");
    return;
  }

  window.location.href = confirmUrl;
}

document.addEventListener("input", function (e) {
  if (!e.target.matches(".qty-input")) return;

  const max = parseInt(e.target.getAttribute("max") || "0", 10);
  e.target.value = clampQty(e.target.value, max);
  recalcSubtotal();
});

document.addEventListener("click", function (e) {
  const qtyButton = e.target.closest(".qty-btn");
  if (!qtyButton) return;

  const ticketId = qtyButton.dataset.ticketId || "";
  const delta = parseInt(qtyButton.dataset.delta || "0", 10);
  const max = parseInt(qtyButton.dataset.max || "0", 10);

  if (!ticketId || !delta) return;
  changeQty(ticketId, delta, max);
});

document.addEventListener("DOMContentLoaded", function () {
  restorePendingOrder();
  recalcSubtotal();

  const submitBtn = document.getElementById("btnSubmit");
  if (submitBtn) {
    submitBtn.addEventListener("click", goToConfirmPage);
  }
});

/* ===== THÊM MỚI CHO NÚT "THÊM" ===== */

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function escapeAttr(value) {
  return escapeHtml(value);
}

function updateSelectedTicketEmpty() {
  const list = document.getElementById("selected-ticket-list");
  const empty = document.getElementById("selected-ticket-empty");
  if (!list || !empty) return;

  empty.style.display = list.children.length > 0 ? "none" : "block";
}

function buildSelectedTicketHtml(data, quantity = 1) {
  const safeQty = clampQty(quantity, data.max);

  return `
    <div class="selected-ticket-item" id="selected-ticket-${data.id}">
      <div class="d-flex justify-content-between align-items-start">
        <div class="flex-grow-1">
          <div class="fw-semibold">${escapeHtml(data.name)}</div>
          <div class="small text-muted mb-1">${escapeHtml(data.description || "Chưa có mô tả")}</div>
        </div>

        <div class="text-end ms-2" style="min-width: 190px;">
          <div class="text-primary">${formatVND(data.price)}</div>

          <div class="input-group input-group-sm mt-1">
            <button
              class="btn btn-outline-secondary qty-btn"
              type="button"
              data-ticket-id="${data.id}"
              data-delta="-1"
              data-max="${data.max}"
            >−</button>

            <input
              class="form-control text-center qty-input"
              id="qty-${data.id}"
              type="number"
              min="0"
              max="${data.max}"
              value="${safeQty}"
              data-ticket-id="${data.id}"
              data-ticket-name="${escapeAttr(data.name)}"
              data-ticket-description="${escapeAttr(data.description || "")}"
              data-price="${data.price}"
            >

            <button
              class="btn btn-outline-secondary qty-btn"
              type="button"
              data-ticket-id="${data.id}"
              data-delta="1"
              data-max="${data.max}"
            >+</button>
          </div>
        </div>
      </div>
    </div>
  `;
}

function addTicketToSelectedList(button) {
  const list = document.getElementById("selected-ticket-list");
  if (!list) return;

  const id = parseInt(button.dataset.ticketId || "0", 10);
  const max = parseInt(button.dataset.max || "0", 10);
  const name = button.dataset.ticketName || "";
  const description = button.dataset.ticketDescription || "";
  const price = parseFloat(button.dataset.price || "0");

  if (!id || max <= 0) return;

  const existedInput = document.getElementById(`qty-${id}`);

  if (existedInput) {
    const nextQty = clampQty(parseInt(existedInput.value || "0", 10) + 1, max);
    existedInput.value = nextQty;
  } else {
    list.insertAdjacentHTML(
      "beforeend",
      buildSelectedTicketHtml(
        {
          id,
          name,
          description,
          price,
          max,
        },
        1,
      ),
    );
  }

  updateSelectedTicketEmpty();
  recalcSubtotal();
}

function removeSelectedTicketIfZero(ticketId) {
  const input = document.getElementById(`qty-${ticketId}`);
  if (!input) return;

  const qty = parseInt(input.value || "0", 10);
  if (qty > 0) return;

  const item = document.getElementById(`selected-ticket-${ticketId}`);
  if (item) item.remove();

  updateSelectedTicketEmpty();
  recalcSubtotal();
}

function restoreSelectedTicketsFromStorage() {
  const submitBtn = document.getElementById("btnSubmit");
  if (!submitBtn) return;

  const eventId = parseInt(submitBtn.dataset.eventId || "0", 10);
  if (!eventId || eventId <= 0) return;

  let parsed = null;
  try {
    parsed = JSON.parse(
      localStorage.getItem(PENDING_ORDER_KEY_PREFIX + eventId) || "null",
    );
  } catch (error) {
    parsed = null;
  }

  if (
    !parsed ||
    Number(parsed.eventId) !== eventId ||
    !Array.isArray(parsed.tickets)
  )
    return;

  parsed.tickets.forEach((item) => {
    const button = document.querySelector(
      `.add-ticket-btn[data-ticket-id="${item.ticketTypeId}"]`,
    );
    if (!button) return;

    const list = document.getElementById("selected-ticket-list");
    if (!list) return;

    const id = parseInt(button.dataset.ticketId || "0", 10);
    const max = parseInt(button.dataset.max || "0", 10);
    const name = button.dataset.ticketName || "";
    const description = button.dataset.ticketDescription || "";
    const price = parseFloat(button.dataset.price || "0");
    const quantity = clampQty(parseInt(item.quantity || "0", 10), max);

    if (!id || quantity <= 0) return;
    if (document.getElementById(`qty-${id}`)) return;

    list.insertAdjacentHTML(
      "beforeend",
      buildSelectedTicketHtml(
        {
          id,
          name,
          description,
          price,
          max,
        },
        quantity,
      ),
    );
  });

  updateSelectedTicketEmpty();
  recalcSubtotal();
}

document.addEventListener("click", function (e) {
  const addBtn = e.target.closest(".add-ticket-btn");
  if (!addBtn) return;

  addTicketToSelectedList(addBtn);
});

document.addEventListener("click", function (e) {
  const qtyBtn = e.target.closest(".qty-btn");
  if (!qtyBtn) return;

  const ticketId = qtyBtn.dataset.ticketId || "";
  if (!ticketId) return;

  setTimeout(() => {
    removeSelectedTicketIfZero(ticketId);
  }, 0);
});

document.addEventListener("input", function (e) {
  const qtyInput = e.target.closest("#selected-ticket-list .qty-input");
  if (!qtyInput) return;

  const max = parseInt(qtyInput.getAttribute("max") || "0", 10);
  qtyInput.value = clampQty(qtyInput.value, max);

  if (parseInt(qtyInput.value || "0", 10) <= 0) {
    const item = qtyInput.closest(".selected-ticket-item");
    if (item) item.remove();
  }

  updateSelectedTicketEmpty();
  recalcSubtotal();
});

document.addEventListener("DOMContentLoaded", function () {
  restoreSelectedTicketsFromStorage();
  updateSelectedTicketEmpty();
  recalcSubtotal();
});
