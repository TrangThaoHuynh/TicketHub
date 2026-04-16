function formatVND(n) {
  return new Intl.NumberFormat('vi-VN').format(Math.round(Number(n) || 0)) + ' VNĐ';
}

function recalcSubtotal() {
  let sum = 0;
  document.querySelectorAll('.qty-input').forEach((inp) => {
    if (inp.disabled) return;
    const qty = parseInt(inp.value || '0', 10);
    const price = parseFloat(inp.dataset.price || '0');
    if (qty > 0 && price >= 0) sum += qty * price;
  });
  document.getElementById('subtotal').textContent = formatVND(sum);
  document.getElementById('btnSubmit').disabled = sum <= 0;
}

function changeQty(id, delta, max) {
  const el = document.getElementById('qty-' + id);
  if (!el || el.disabled) return;

  const cur = parseInt(el.value || '0', 10);
  let next = cur + delta;

  if (next < 0) next = 0;
  if (typeof max === 'number' && next > max) next = max;

  el.value = next;
  recalcSubtotal();
}

document.addEventListener('input', function (e) {
  if (e.target.matches('.qty-input')) {
    const max = parseInt(e.target.getAttribute('max') || '0', 10);
    let v = parseInt(e.target.value || '0', 10);

    if (isNaN(v) || v < 0) v = 0;
    if (max > 0 && v > max) v = max;

    e.target.value = v;
    recalcSubtotal();
  }
});
