(function () {
    const ROW_SELECTOR = '.js-order-row';
    const PER_PAGE = 5;

    const codeInput = document.getElementById('orderCode');
    const statusSelect = document.getElementById('orderStatus');
    const btnFilter = document.getElementById('btnFilter');
    const btnClear = document.getElementById('btnClear');

    const tbody = document.getElementById('ordersTbody');
    const pageButtonsWrap = document.getElementById('pageButtons');
    const pagePrev = document.getElementById('pagePrev');
    const pageNext = document.getElementById('pageNext');

    if (!tbody || !pageButtonsWrap || !pagePrev || !pageNext) return;

    const allRows = Array.from(tbody.querySelectorAll(ROW_SELECTOR));
    let filteredRows = allRows.slice();
    let page = 1;

    function normalize(text) {
        return (text || '').toString().trim().toLowerCase();
    }

    function pageCount() {
        return Math.max(1, Math.ceil(filteredRows.length / PER_PAGE));
    }

    function setRowVisible(row, visible) {
        row.style.display = visible ? '' : 'none';
    }

    function renderEmptyState() {
        const existing = document.getElementById('ordersEmpty');
        if (existing) existing.remove();

        if (filteredRows.length > 0) return;

        const tr = document.createElement('tr');
        tr.id = 'ordersEmpty';
        tr.innerHTML =
            '<td colspan="8" class="orders-empty">' +
            '<div class="alert alert-light border mb-0" role="alert">Không có đơn mua phù hợp.</div>' +
            '</td>';
        tbody.appendChild(tr);
    }

    function renderRows() {
        const totalPages = pageCount();
        if (page < 1) page = 1;
        if (page > totalPages) page = totalPages;

        const startIndex = (page - 1) * PER_PAGE;
        const endIndex = startIndex + PER_PAGE;

        allRows.forEach((row) => setRowVisible(row, false));
        filteredRows.slice(startIndex, endIndex).forEach((row) => setRowVisible(row, true));

        pagePrev.disabled = page <= 1;
        pageNext.disabled = page >= totalPages;
    }

    function renderPager() {
        const totalPages = pageCount();
        pageButtonsWrap.innerHTML = '';

        const maxButtons = 3;
        let start = Math.max(1, page - 1);
        let end = Math.min(totalPages, start + maxButtons - 1);
        start = Math.max(1, end - maxButtons + 1);

        for (let p = start; p <= end; p++) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'orders-page-btn' + (p === page ? ' is-active' : '');
            btn.textContent = String(p);
            btn.addEventListener('click', () => {
                page = p;
                render();
            });
            pageButtonsWrap.appendChild(btn);
        }
    }

    function render() {
        renderRows();
        renderPager();
        renderEmptyState();
    }

    function applyFilter() {
        const code = normalize(codeInput ? codeInput.value : '');
        const status = normalize(statusSelect ? statusSelect.value : '');

        filteredRows = allRows.filter((row) => {
            const rowCode = normalize(row.getAttribute('data-order-code'));
            const rowStatus = normalize(row.getAttribute('data-status'));

            const codeOk = !code || rowCode.includes(code);
            const statusOk = !status || rowStatus === status;
            return codeOk && statusOk;
        });

        page = 1;
        render();
    }

    function clearFilter() {
        if (codeInput) codeInput.value = '';
        if (statusSelect) statusSelect.value = '';
        filteredRows = allRows.slice();
        page = 1;
        render();
    }

    btnFilter && btnFilter.addEventListener('click', applyFilter);
    btnClear && btnClear.addEventListener('click', clearFilter);

    codeInput &&
        codeInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                applyFilter();
            }
        });

    pagePrev.addEventListener('click', () => {
        page -= 1;
        render();
    });

    pageNext.addEventListener('click', () => {
        page += 1;
        render();
    });

    render();
})();
