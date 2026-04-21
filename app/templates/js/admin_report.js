document.addEventListener("DOMContentLoaded", function () {
  function parseDataset(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    return {
      el,
      labels: JSON.parse(el.dataset.labels || "[]"),
      values: JSON.parse(el.dataset.values || "[]"),
    };
  }

  function setScrollableWidth(
    wrapperId,
    itemCount,
    pixelsPerItem,
    minWidth = 520,
  ) {
    const wrapper = document.getElementById(wrapperId);
    if (!wrapper) return;

    const width = Math.max(minWidth, itemCount * pixelsPerItem);
    wrapper.style.width = width + "px";
  }

  function makeMoney(value) {
    return Number(value || 0).toLocaleString("vi-VN") + " VND";
  }

  function createLineChart(target, wrapperId) {
    if (!target || !target.labels.length) return;

    setScrollableWidth(wrapperId, target.labels.length, 90, 700);

    new Chart(target.el.getContext("2d"), {
      type: "line",
      data: {
        labels: target.labels,
        datasets: [
          {
            label: "Doanh thu",
            data: target.values,
            borderColor: "#3da9fc",
            backgroundColor: "rgba(61, 169, 252, 0.15)",
            tension: 0.35,
            fill: true,
            pointRadius: 4,
            pointBackgroundColor: "#3da9fc",
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            callbacks: {
              label: function (context) {
                return "Doanh thu: " + makeMoney(context.parsed.y);
              },
            },
          },
        },
        scales: {
          x: {
            ticks: {
              autoSkip: false,
            },
          },
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return Number(value).toLocaleString("vi-VN");
              },
            },
          },
        },
      },
    });
  }

  function createBarChart(target, wrapperId) {
    if (!target || !target.labels.length) return;

    setScrollableWidth(wrapperId, target.labels.length, 130, 700);

    new Chart(target.el.getContext("2d"), {
      type: "bar",
      data: {
        labels: target.labels,
        datasets: [
          {
            label: "Doanh thu",
            data: target.values,
            backgroundColor: "rgba(72, 187, 217, 0.85)",
            borderColor: "rgba(72, 187, 217, 1)",
            borderWidth: 1,
            borderRadius: 8,
            categoryPercentage: 0.55,
            barPercentage: 0.55,
            maxBarThickness: 36,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          tooltip: {
            callbacks: {
              label: function (context) {
                return "Doanh thu: " + makeMoney(context.parsed.y);
              },
            },
          },
        },
        scales: {
          x: {
            ticks: {
              autoSkip: false,
              maxRotation: 35,
              minRotation: 35,
            },
          },
          y: {
            beginAtZero: true,
            ticks: {
              callback: function (value) {
                return Number(value).toLocaleString("vi-VN");
              },
            },
          },
        },
      },
    });
  }

  function createDoughnutChart(target) {
    if (!target || !target.labels.length) return;

    new Chart(target.el.getContext("2d"), {
      type: "doughnut",
      data: {
        labels: target.labels,
        datasets: [
          {
            data: target.values,
            backgroundColor: [
              "#1677d8",
              "#3da9fc",
              "#59c3c3",
              "#84dcc6",
              "#f4d35e",
              "#ee964b",
              "#f95738",
            ],
          },
        ],
      },
      options: {
        responsive: true,
        plugins: {
          legend: {
            position: "top",
          },
        },
      },
    });
  }
  createLineChart(parseDataset("timeRevenueChart"), "timeRevenueChartWrap");
  createBarChart(parseDataset("eventRevenueChart"), "eventRevenueChartWrap");
  createDoughnutChart(parseDataset("bookingStatusChart"));
  createDoughnutChart(parseDataset("eventStatusChart"));
  createDoughnutChart(parseDataset("ticketStatusChart"));
});
