(function () {
  function setupFilterDropdown(buttonId, panelId) {
    const btn = document.getElementById(buttonId);
    const panel = document.getElementById(panelId);
    if (!btn || !panel) {
      return;
    }

    function closePanel() {
      panel.classList.add("is-hidden");
      btn.setAttribute("aria-expanded", "false");
    }

    function openPanel() {
      panel.classList.remove("is-hidden");
      btn.setAttribute("aria-expanded", "true");
    }

    btn.addEventListener("click", function (e) {
      e.preventDefault();
      if (panel.classList.contains("is-hidden")) {
        openPanel();
      } else {
        closePanel();
      }
    });

    panel.addEventListener("click", function (e) {
      if (!e.target.closest(".js-ticket-filter-close")) {
        return;
      }
      e.preventDefault();
      closePanel();
    });

    document.addEventListener("click", function (e) {
      if (panel.classList.contains("is-hidden")) {
        return;
      }
      if (btn.contains(e.target) || panel.contains(e.target)) {
        return;
      }
      closePanel();
    });

    document.addEventListener("keydown", function (e) {
      if (e.key !== "Escape") {
        return;
      }
      if (panel.classList.contains("is-hidden")) {
        return;
      }
      closePanel();
    });
  }

  function setupBackToTop() {
    const backToTopBtn = document.getElementById("backToTopBtn");
    if (!backToTopBtn) {
      return;
    }

    function scrollToTop() {
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    }

    window.addEventListener("scroll", function () {
      if (window.pageYOffset > 300) {
        backToTopBtn.classList.add("show");
        backToTopBtn.style.display = "inline-block";
        return;
      }

      backToTopBtn.classList.remove("show");
      window.setTimeout(function () {
        if (!backToTopBtn.classList.contains("show")) {
          backToTopBtn.style.display = "none";
        }
      }, 300);
    });

    backToTopBtn.addEventListener("click", scrollToTop);

    backToTopBtn.addEventListener("keydown", function (e) {
      if (e.key !== "Enter" && e.key !== " ") {
        return;
      }
      e.preventDefault();
      scrollToTop();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    setupFilterDropdown("ticketFilterBtnDesktop", "ticketFilterPanelDesktop");
    setupFilterDropdown("ticketFilterBtnMobile", "ticketFilterPanelMobile");
    setupBackToTop();
  });
})();
