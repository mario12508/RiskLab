document.addEventListener("DOMContentLoaded", () => {
    if (typeof Chart === "undefined") return;

    const dataNode = document.getElementById("portfolio-data");
    let data = {};
    if (dataNode) {
        try {
            data = JSON.parse(dataNode.textContent || "{}");
        } catch (_e) { console.error("Data parse error"); return; }
    }

    const toArray = (v) => (Array.isArray(v) ? v : []);
    const toNum = (v) => { const n = Number(v); return Number.isFinite(n) ? n : 0; };
    const toNumArr = (arr) => toArray(arr).map(toNum);

    const charts = {};

    const showEmpty = (id, show) => {
        const emptyEl = document.getElementById(id + "Empty");
        const canvasEl = document.getElementById(id);
        if (emptyEl) emptyEl.classList.toggle("d-none", !show);
        if (canvasEl) canvasEl.style.display = show ? "none" : "block";
    };

    const COLORS = [
        "#2563eb","#16a34a","#dc2626","#d97706","#7c3aed",
        "#0891b2","#be185d","#65a30d","#ea580c","#4f46e5"
    ];

    const render = (id, configFactory) => {
        const el = document.getElementById(id);
        if (!el) return;
        if (charts[id]) { charts[id].destroy(); delete charts[id]; }
        const cfg = configFactory(el.getContext("2d"));
        if (!cfg) { showEmpty(id, true); return; }
        showEmpty(id, false);
        charts[id] = new Chart(el, cfg);
    };

    const initAllCharts = () => {

        render("performanceChart", () => {
            const labels = toArray(data.performanceDates);
            const portfolio = toNumArr(data.performanceValues);
            const moex = toNumArr(data.moexValues);
            if (labels.length < 2) return null;
            return {
                type: "line",
                data: {
                    labels,
                    datasets: [
                        {
                            label: "Портфель",
                            data: portfolio,
                            borderColor: "#2563eb",
                            backgroundColor: "rgba(37,99,235,0.08)",
                            fill: true, tension: 0.3, pointRadius: 0, borderWidth: 2,
                        },
                        {
                            label: "IMOEX (масштаб)",
                            data: moex,
                            borderColor: "#6b7280",
                            borderDash: [5, 5],
                            fill: false, tension: 0.3, pointRadius: 0, borderWidth: 1.5,
                        }
                    ]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: { legend: { position: "top" } },
                    scales: {
                        x: { ticks: { maxTicksLimit: 8 } },
                        y: { ticks: { callback: v => (v/1000).toFixed(0) + "k ₽" } }
                    }
                }
            };
        });

        render("growthChart", () => {
            const pg = data.portfolioGrowthPct ?? 0;
            const mg = data.moexGrowthPct ?? 0;
            return {
                type: "bar",
                data: {
                    labels: ["Портфель", "IMOEX"],
                    datasets: [{
                        data: [pg, mg],
                        backgroundColor: [
                            pg >= 0 ? "rgba(37,99,235,0.7)" : "rgba(220,38,38,0.7)",
                            mg >= 0 ? "rgba(107,114,128,0.7)" : "rgba(220,38,38,0.7)",
                        ],
                        borderRadius: 6,
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: { y: { ticks: { callback: v => v.toFixed(1) + "%" } } }
                }
            };
        });

        render("sectorChart", () => {
            const alloc = data.sectorAlloc || {};
            const labels = Object.keys(alloc);
            const values = Object.values(alloc).map(Number);
            if (!labels.length) return null;
            return {
                type: "doughnut",
                data: {
                    labels,
                    datasets: [{ data: values, backgroundColor: COLORS, borderWidth: 2 }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: {
                        legend: { position: "right" },
                        tooltip: { callbacks: { label: ctx => ` ${(ctx.raw/1000).toFixed(0)}k ₽` } }
                    }
                }
            };
        });

        render("positionsChart", () => {
            const alloc = data.holdingsAlloc || {};
            const labels = Object.keys(alloc);
            const values = Object.values(alloc).map(Number);
            if (!labels.length) return null;
            return {
                type: "bar",
                data: {
                    labels,
                    datasets: [{
                        label: "Стоимость позиции",
                        data: values,
                        backgroundColor: COLORS,
                        borderRadius: 6,
                    }]
                },
                options: {
                    responsive: true, maintainAspectRatio: false,
                    plugins: { legend: { display: false } },
                    scales: {
                        x: { ticks: { font: { size: 11 } } },
                        y: { ticks: { callback: v => (v/1000).toFixed(0) + "k ₽" } }
                    }
                }
            };
        });

        render("returnsLineChart", () => {
            const pr = toNumArr(data.portfolioReturns);
            const mr = toNumArr(data.moexReturns);
            if (pr.length < 5) return null;

            const step = pr.length > 60 ? 3 : pr.length > 30 ? 2 : 1;
            const sample = (arr) => arr.filter((_, i) => i % step === 0);
            const sampledPr = sample(pr);
            const sampledMr = sample(mr);
            const sampledDates = sample(toArray(data.performanceDates));

            return {
                type: "bar",
                data: {
                    labels: sampledDates,
                    datasets: [
                        {
                            label: "Портфель %",
                            data: sampledPr,
                            backgroundColor: sampledPr.map(v =>
                                v >= 0 ? "rgba(37,99,235,0.75)" : "rgba(220,38,38,0.75)"
                            ),
                            borderRadius: 3,
                            order: 1,
                        },
                        {
                            label: "IMOEX %",
                            data: sampledMr,
                            type: "line",
                            borderColor: "#6b7280",
                            backgroundColor: "transparent",
                            borderDash: [4, 3],
                            pointRadius: 0,
                            borderWidth: 1.5,
                            order: 0,
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { mode: "index", intersect: false },
                    plugins: {
                        legend: {
                            position: "top",
                            labels: {
                                usePointStyle: true,
                                pointStyleWidth: 20,
                                generateLabels: (chart) => {
                                    const labels = Chart.defaults.plugins.legend.labels.generateLabels(chart);
                                    const portfolioLabel = labels.find(l => l.text === "Портфель %");
                                    if (portfolioLabel) {
                                        const size = 20;
                                        const off = document.createElement("canvas");
                                        off.width = size;
                                        off.height = size;
                                        const ctx2 = off.getContext("2d");
                                        ctx2.fillStyle = "rgba(37,99,235,0.85)";
                                        ctx2.fillRect(0, 0, size / 2, size);
                                        ctx2.fillStyle = "rgba(220,38,38,0.80)";
                                        ctx2.fillRect(size / 2, 0, size / 2, size);

                                        portfolioLabel.pointStyle  = off;
                                        portfolioLabel.fillStyle   = "transparent";
                                        portfolioLabel.strokeStyle = "transparent";
                                    }
                                    return labels;
                                }
                            }
                        },
                        tooltip: {
                            callbacks: {
                                label: ctx => ` ${ctx.dataset.label}: ${ctx.raw.toFixed(2)}%`
                            }
                        }
                    },
                    scales: {
                        x: {
                            ticks: {
                                maxTicksLimit: 10,
                                font: { size: 11 },
                            },
                            grid: { display: false }
                        },
                        y: {
                            ticks: { callback: v => v.toFixed(1) + "%" },
                            grid: { color: "rgba(128,128,128,0.15)" }
                        }
                    }
                }
            };
        });
    };

    initAllCharts();

    document.querySelectorAll('button[data-bs-toggle="pill"]').forEach(tabEl => {
        tabEl.addEventListener("shown.bs.tab", () => {
            setTimeout(initAllCharts, 50);
        });
    });
});