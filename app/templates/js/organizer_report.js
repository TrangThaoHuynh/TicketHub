document.addEventListener("DOMContentLoaded", function () {
  const canvas = document.getElementById("organizerRevenueChart");
  const dataEl = document.getElementById("organizer-chart-data");

  if (!canvas || !dataEl) return;

  let chartData = { labels: [], values: [] };

  try {
    chartData = JSON.parse(dataEl.textContent || "{}");
  } catch (error) {
    console.error("Không đọc được dữ liệu chart organizer:", error);
    return;
  }

  const labels = Array.isArray(chartData.labels) ? chartData.labels : [];
  const values = Array.isArray(chartData.values) ? chartData.values : [];

  if (!labels.length) return;

  const ctx = canvas.getContext("2d");

  new Chart(ctx, {
    type: "bar",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Doanh thu (VND)",
          data: values,
          backgroundColor: "rgba(72, 187, 217, 0.85)",
          borderColor: "rgba(72, 187, 217, 1)",
          borderWidth: 1,
          borderRadius: 8,
          maxBarThickness: 54,
        },
      ],
    },
    options: {
      responsive: true,
      plugins: {
        legend: {
          display: true,
        },
        tooltip: {
          callbacks: {
            label: function (context) {
              return (
                "Doanh thu: " +
                Number(context.parsed.y || 0).toLocaleString("vi-VN") +
                " VND"
              );
            },
          },
        },
      },
      scales: {
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
});
