let r2ChartInstance = null;
let latestChartData = null;

// ================= UTILITY: SHOW INLINE ALERT =================
function showAlert(message, type = "danger") {
    let alertBox = document.getElementById("globalAlert");
    if (!alertBox) {
        alertBox = document.createElement("div");
        alertBox.id = "globalAlert";
        alertBox.style.cssText = "position:fixed;top:16px;right:16px;z-index:9999;max-width:380px;";
        document.body.appendChild(alertBox);
    }
    alertBox.innerHTML = `
        <div class="alert alert-${type} alert-dismissible fade show shadow" role="alert" style="font-size:0.9em;">
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        </div>`;
    // Auto-dismiss after 6 seconds
    setTimeout(() => {
        const alert = alertBox.querySelector(".alert");
        if (alert) alert.classList.remove("show");
    }, 6000);
}

// ================= DB STATUS BANNER =================
function checkDbStatus() {
    fetch("/db-status")
    .then(res => res.json())
    .then(data => {
        let banner = document.getElementById("dbStatusBanner");
        if (!banner) return;
        if (data.mongo_status === "offline") {
            banner.innerHTML = `
                <div class="alert alert-warning py-1 px-3 mb-0 text-center small" style="border-radius:0;border:none;">
                    ⚠️ <b>Offline Mode:</b> MongoDB is not connected. Your data is stored in memory and will be lost on restart.
                </div>`;
            banner.style.display = "block";
        } else if (data.mongo_status === "reconnected") {
            banner.innerHTML = `
                <div class="alert alert-info py-1 px-3 mb-0 text-center small" style="border-radius:0;border:none;">
                    🔄 <b>Reconnected:</b> MongoDB connection was restored.
                </div>`;
            banner.style.display = "block";
            setTimeout(() => { banner.style.display = "none"; }, 5000);
        } else {
            banner.style.display = "none";
        }
    })
    .catch(() => {
        // Can't reach server, silently ignore
    });
}

// ================= MAIN FUNCTION =================
function calculateEMI() {
    let principal = document.getElementById("principal").value;
    let years = document.getElementById("years").value;
    let income = document.getElementById("income").value;
    let loanType = document.getElementById("loanType").value;
    let compound = document.getElementById("compoundType").value;

    // Basic validation
    if (!principal || !years || !income) {
        showAlert("Please fill in all fields: Loan Amount, Tenure, and Monthly Income.", "warning");
        return;
    }
    if (parseFloat(principal) <= 0 || parseFloat(years) <= 0 || parseFloat(income) <= 0) {
        showAlert("All values must be positive numbers.", "warning");
        return;
    }

    fetch("/calculate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            principal: principal,
            years: years,
            income: income,
            loan_type: loanType,
            compound: compound
        })
    })
    .then(res => {
        return res.json().then(body => {
            if (!res.ok) {
                const msg = body.error || `Server error (HTTP ${res.status}). Please try again.`;
                throw new Error(msg);
            }
            return body;
        });
    })
    .then(data => {
        if (data.error) {
            showAlert(data.error, "danger");
            return;
        }
        console.log("DATA RECEIVED:", data);
        latestChartData = data;

        // ================= EMI SUMMARY =================
        document.getElementById("emi").innerHTML =
            `<b>EMI:</b> ₹${Number(data.emi || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;

        document.getElementById("repo").innerHTML =
            `<b>Latest RBI Repo Rate:</b> ${data.repo_rate || 0}%`;

        document.getElementById("bestModel").innerHTML =
            `<span class="badge bg-primary fs-6 p-2">
                Best Predictive Formula: ${data.best_model || "-"} Model
             </span>`;

        // ================= MODEL COMPARISON =================
        document.getElementById("comparison").innerHTML =
            `<h5><b>Goodness-of-Fit (R²)</b></h5>
             <div class="row mt-2">
                 <div class="col-sm-4"><b>Linear:</b> ${data.model1_r2 || 0}</div>
                 <div class="col-sm-4"><b>Multiple:</b> ${data.model2_r2 || 0}</div>
                 <div class="col-sm-4"><b>Polynomial:</b> ${data.model3_r2 || 0}</div>
             </div>
             <hr>
             <h5><b>Akaike Information Criterion (AIC)</b></h5>
             <div class="row mt-2">
                 <div class="col-sm-4"><b>Linear:</b> ${data.model1_aic || 0}</div>
                 <div class="col-sm-4"><b>Multiple:</b> ${data.model2_aic || 0}</div>
                 <div class="col-sm-4"><b>Polynomial:</b> ${data.model3_aic || 0}</div>
             </div>`;

        // ================= RISK ANALYSIS =================
        let riskColor = "success";
        if (data.risk_level === "Moderate") riskColor = "warning text-dark";
        if (data.risk_level === "High") riskColor = "danger";

        document.getElementById("risk").innerHTML =
            `<div class="card bg-light border-0 p-3">
                 <div class="mb-2">Your Debt Ratio is <b>${data.debt_ratio || 0}%</b> of your monthly net income.</div>
                 <div>
                     Affordability Status: 
                     <span class="badge bg-${riskColor} fs-6 px-3 py-2 ms-2">
                         ${data.risk_level || "-"} Risk
                     </span>
                 </div>
             </div>`;

        // ================= SCENARIO SIMULATION =================
        document.getElementById("scenario").innerHTML =
            `<table class="table table-sm table-bordered mt-2">
                 <thead>
                     <tr class="table-light">
                         <th>Scenario Rate Shift</th>
                         <th>Simulated Interest Rate</th>
                         <th>Compound Installment (EMI)</th>
                     </tr>
                 </thead>
                 <tbody>
                     <tr>
                         <td>Rate Drops <b>-0.50%</b></td>
                         <td>${(data.repo_rate - 0.50).toFixed(2)}%</td>
                         <td>₹${Number(data.low_emi || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                     </tr>
                     <tr class="table-primary fw-bold">
                         <td>Base Calculated Rate</td>
                         <td>${(data.repo_rate).toFixed(2)}%</td>
                         <td>₹${Number(data.base_emi || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                     </tr>
                     <tr>
                         <td>Rate Rises <b>+0.50%</b></td>
                         <td>${(data.repo_rate + 0.50).toFixed(2)}%</td>
                         <td>₹${Number(data.high_emi || 0).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                     </tr>
                 </tbody>
             </table>`;

        // ================= DIAGNOSTICS =================
        document.getElementById("diagnostics").innerHTML =
            `<div class="row">
                 <div class="col-sm-6"><b>Residual Average Error:</b> ${data.residual_mean || 0}</div>
                 <div class="col-sm-6"><b>Residual Std Deviation:</b> ${data.residual_std || 0}</div>
             </div>
             <div class="row mt-2">
                 <div class="col-sm-6"><b>Jarque-Bera p-value:</b> ${data.jb_pvalue || 0}</div>
                 <div class="col-sm-6"><b>Durbin-Watson Stat:</b> ${data.durbin_watson || 0}</div>
             </div>
             <p class="text-muted mt-3 small">
                 Note: Jarque-Bera tests residual normality. Durbin-Watson tests residual serial correlation (value near 2.0 indicates none).
             </p>`;

        // ================= COEFFICIENTS TABLE =================
        let coefHTML = `
            <table class="table table-bordered table-striped">
                <thead>
                    <tr class="table-secondary">
                        <th>Variable / Fit Feature</th>
                        <th>OLS Coefficient (Beta Weight)</th>
                    </tr>
                </thead>
                <tbody>
        `;

        if (data.coefficients) {
            for (let key in data.coefficients) {
                let formattedKey = key;
                if (key === "const") formattedKey = "Constant Intercept (C)";
                coefHTML += `
                    <tr>
                        <td><b>${formattedKey}</b></td>
                        <td class="font-monospace">${Number(data.coefficients[key]).toFixed(4)}</td>
                    </tr>
                `;
            }
        }

        coefHTML += `</tbody></table>`;
        document.getElementById("coefTable").innerHTML = coefHTML;

        // If the current visible tab is the Graph, render the chart immediately
        const activeTab = document.querySelector(".nav-link.active");
        if (activeTab && activeTab.getAttribute("data-bs-target") === "#graphTab") {
            renderChart(data);
        }
    })
    .catch(err => {
        console.error("[calculateEMI] Error:", err);
        showAlert(err.message || "Server error occurred. Please check your inputs and try again.", "danger");
    });
}

// ================= GRAPH RENDER =================
function renderChart(data) {
    const canvas = document.getElementById("r2Chart");
    if (!canvas || !data) return;

    const ctx = canvas.getContext("2d");

    if (r2ChartInstance) {
        r2ChartInstance.destroy();
    }

    r2ChartInstance = new Chart(ctx, {
        type: "bar",
        data: {
            labels: ["Simple Linear", "Multiple Linear (OLS)", "Polynomial"],
            datasets: [{
                label: "R-squared Comparison",
                data: [
                    data.model1_r2 || 0,
                    data.model2_r2 || 0,
                    data.model3_r2 || 0
                ],
                backgroundColor: [
                    "rgba(220, 53, 69, 0.8)",  // Linear Red
                    "rgba(25, 135, 84, 0.8)",  // Multiple Green
                    "rgba(13, 110, 253, 0.8)"  // Polynomial Blue
                ],
                borderColor: [
                    "#dc3545",
                    "#198754",
                    "#0d6efd"
                ],
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                y: {
                    beginAtZero: true,
                    max: 1.0,
                    title: {
                        display: true,
                        text: "Goodness-of-Fit Score (R²)"
                    }
                }
            }
        }
    });
}

// ================= HISTORY LOGS LOADER =================
function loadHistory() {
    const container = document.getElementById("historyTable");
    if (container) {
        container.innerHTML = `<p class="text-muted text-center py-3"><span class="spinner-border spinner-border-sm me-2"></span>Loading history...</p>`;
    }
    fetch("/history")
    .then(res => {
        return res.json().then(body => {
            if (!res.ok) {
                throw new Error(body.error || `Failed to load history (HTTP ${res.status})`);
            }
            return body;
        });
    })
    .then(data => {
        if (data && data.error) {
            throw new Error(data.error);
        }
        const loanFilter = document.getElementById("loanFilter").value;
        const riskFilter = document.getElementById("riskFilter").value;
        const sortOption = document.getElementById("sortOption").value;

        let filtered = data;

        // Apply filters
        if (loanFilter) {
            filtered = filtered.filter(item => item.loan_type === loanFilter);
        }

        if (riskFilter) {
            filtered = filtered.filter(item => item.risk_level === riskFilter);
        }

        // Apply sorting
        if (sortOption === "emi") {
            filtered.sort((a, b) => b.emi - a.emi);
        } else {
            // Sort by date
            filtered.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
        }

        const container = document.getElementById("historyTable");
        if (filtered.length === 0) {
            container.innerHTML = `<p class="text-muted text-center py-4">No matching logged history records found.</p>`;
            return;
        }

        let html = `
            <table class="table table-bordered table-hover align-middle">
                <thead class="table-light">
                    <tr>
                        <th>Loan Category</th>
                        <th>Principal Amount</th>
                        <th>EMI Installment</th>
                        <th>Risk Assessment</th>
                        <th>Compounding Period</th>
                        <th>Calculated Date</th>
                    </tr>
                </thead>
                <tbody>
        `;

        const compoundingMap = {0: "Simple Interest", 12: "Monthly", 4: "Quarterly", 2: "Semi-Annual", 1: "Yearly"};

        filtered.forEach(item => {
            let riskBadgeColor = "success";
            if (item.risk_level === "Moderate") riskBadgeColor = "warning text-dark";
            if (item.risk_level === "High") riskBadgeColor = "danger";

            let compText = compoundingMap[item.compounding] || `${item.compounding}x/Yr`;

            html += `
                <tr>
                    <td><b>${item.loan_type}</b></td>
                    <td>₹${Number(item.principal).toLocaleString()}</td>
                    <td class="text-primary fw-bold">₹${Number(item.emi).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    <td>
                        <span class="badge bg-${riskBadgeColor}">
                            ${item.risk_level}
                        </span>
                    </td>
                    <td>${compText}</td>
                    <td class="text-muted small">${new Date(item.timestamp).toLocaleString()}</td>
                </tr>
            `;
        });

        html += "</tbody></table>";
        container.innerHTML = html;
    })
    .catch(err => {
        console.error("[loadHistory] Error:", err);
        const container = document.getElementById("historyTable");
        if (container) {
            container.innerHTML = `<div class="alert alert-warning text-center">⚠️ Could not load history: ${err.message}</div>`;
        }
    });
}

// ================= TAB SHOWN EVENTS =================
document.addEventListener("shown.bs.tab", function (event) {
    const targetId = event.target.getAttribute("data-bs-target");

    if (targetId === "#graphTab") {
        if (latestChartData) {
            setTimeout(() => {
                renderChart(latestChartData);
            }, 120);
        }
    }

    if (targetId === "#historyTab") {
        loadHistory();
    }
});

// ================= FILTER LISTENERS =================
document.addEventListener("DOMContentLoaded", function() {
    const loanFilter = document.getElementById("loanFilter");
    const riskFilter = document.getElementById("riskFilter");
    const sortOption = document.getElementById("sortOption");

    if (loanFilter) loanFilter.addEventListener("change", loadHistory);
    if (riskFilter) riskFilter.addEventListener("change", loadHistory);
    if (sortOption) sortOption.addEventListener("change", loadHistory);

    // Check DB status on page load and every 60 seconds
    checkDbStatus();
    setInterval(checkDbStatus, 60000);
});

// ================= THEME TOGGLING =================
function toggleTheme() {
    document.body.classList.toggle("dark-mode");
}