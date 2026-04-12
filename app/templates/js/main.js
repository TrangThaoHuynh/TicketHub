    document.addEventListener("DOMContentLoaded", function () {
        const noticeStack = document.getElementById("mainNoticeStack");
        const notices = document.querySelectorAll(".js-main-notice");

        function removeNotice(notice) {
            if (!notice || notice.classList.contains("is-hiding")) return;

            notice.classList.add("is-hiding");
            window.setTimeout(function () {
                notice.remove();
                if (noticeStack && !noticeStack.querySelector(".js-main-notice")) {
                    noticeStack.remove();
                }
            }, 260);
        }

        notices.forEach(function (notice) {
            const closeButton = notice.querySelector(".js-main-notice-close");
            if (closeButton) {
                closeButton.addEventListener("click", function () {
                    removeNotice(notice);
                });
            }

            window.setTimeout(function () {
                removeNotice(notice);
            }, 5000);
        });

        const container = document.getElementById("eventTypes");
        const more = document.getElementById("eventTypeMore");
        const menu = document.getElementById("eventTypeMoreMenu");

        if (!container || !more || !menu) return;

        function reset() {
            menu.innerHTML = "";
            more.classList.add("d-none");

            const pills = container.querySelectorAll(".js-event-type-pill");
            pills.forEach((pill) => {
                pill.classList.remove("d-none");
            });
        }

        function buildMenuItem(pill) {
            const li = document.createElement("li");
            const a = document.createElement("a");
            a.className = "dropdown-item";
            if (pill.dataset.active === "1") a.classList.add("active");
            a.href = pill.getAttribute("href") || "#";
            a.textContent = pill.textContent ? pill.textContent.trim() : "";
            li.appendChild(a);
            return li;
        }

        function layout() {
            reset();

            if (container.scrollWidth <= container.clientWidth) return;

            more.classList.remove("d-none");

            const pills = Array.from(container.querySelectorAll(".js-event-type-pill"));
            const activePill = pills.find((p) => p.dataset.active === "1");

            for (let i = pills.length - 1; i >= 0; i--) {
                if (container.scrollWidth <= container.clientWidth) break;

                const pill = pills[i];
                if (pill === activePill) continue;

                pill.classList.add("d-none");
                menu.prepend(buildMenuItem(pill));
            }

            for (let i = 0; i < pills.length; i++) {
                if (container.scrollWidth <= container.clientWidth) break;

                const pill = pills[i];
                if (pill === activePill) continue;
                if (pill.classList.contains("d-none")) continue;

                pill.classList.add("d-none");
                menu.appendChild(buildMenuItem(pill));
            }

            if (!menu.children.length) {
                more.classList.add("d-none");
            }
        }

        let resizeTimer;
        window.addEventListener("resize", function () {
            window.clearTimeout(resizeTimer);
            resizeTimer = window.setTimeout(layout, 80);
        });

        layout();
    });