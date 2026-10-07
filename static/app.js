async function postJSON(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  return response.json();
}

async function getJSON(url) {
  const response = await fetch(url);
  return response.json();
}

function currency(value) {
  return `Rs. ${Number(value).toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

function statusClass(label) {
  if (["BUY", "Low", "Undervalued", "HOLD"].includes(label)) {
    return "success";
  }
  if (["SELL", "EXIT", "High"].includes(label)) {
    return "danger";
  }
  return "warn";
}

function card(title, body, extraClass = "") {
  return `<article class="result-card ${extraClass}"><h3>${title}</h3>${body}</article>`;
}

function readAnalysisPayload() {
  return {
    age: Number(document.getElementById("age")?.value || 28),
    income: Number(document.getElementById("income")?.value || 90000),
    horizon: Number(document.getElementById("horizon")?.value || 10),
    tolerance: Number(document.getElementById("tolerance")?.value || 7),
    stock_name: document.getElementById("stock_name")?.value || "Reliance Industries",
    investment_amount: Number(document.getElementById("investment_amount")?.value || 500000),
  };
}

window.currentRiskProfile = "Medium";

async function runFullAnalysis() {
  const container = document.getElementById("analysisResult");
  container.innerHTML = card("Running", "<p>Fetching risk profile, prediction, and portfolio...</p>");
  const result = await postJSON("/api/analyze", readAnalysisPayload());

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const data = result.data;
  const profile = data.risk_profile;
  window.currentRiskProfile = profile.profile;
  const prediction = data.prediction;
  const portfolio = data.portfolio;
  const picks = data.recommendations
    .map((item) => `<li>${item.name} (${item.symbol}) - ${item.verdict} score ${item.undervalued_score}</li>`)
    .join("");

  container.innerHTML = [
    card(
      "Risk Profile",
      `<p><span class="pill ${statusClass(profile.profile)}">${profile.profile}</span></p>
       <p>${profile.description}</p>
       <p class="mono">Score: ${profile.score}/${profile.max_score}</p>`
    ),
    card(
      "Stock Prediction",
      `<p><span class="pill ${statusClass(prediction.signal)}">${prediction.signal}</span></p>
       <p>${prediction.symbol} current ${currency(prediction.current_price)}</p>
       <p>5-day target ${currency(prediction.predicted_5d_price)} (${prediction.change_pct}%)</p>
       <p class="mono">Accuracy ${prediction.model_accuracy}% | Source ${prediction.data_source} | Price date ${prediction.latest_trading_date}</p>`
    ),
    card(
      "Portfolio Allocation",
      `<ul>
        ${Object.entries(portfolio.allocation_inr)
          .map(([key, value]) => `<li>${key}: ${currency(value)} (${portfolio.allocation_pct[key]}%)</li>`)
          .join("")}
      </ul>`
    ),
    card("Top Recommendations", `<ul>${picks}</ul>`),
  ].join("");
}

async function runRiskOnly() {
  const container = document.getElementById("analysisResult");
  container.innerHTML = card("Checking", "<p>Calculating investor risk profile...</p>");
  const payload = readAnalysisPayload();
  const result = await postJSON("/api/risk-profile", payload);

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const d = result.data;
  window.currentRiskProfile = d.profile;
  container.innerHTML = [
    card(
      "Risk Result",
      `<p><span class="pill ${statusClass(d.profile)}">${d.profile}</span></p>
       <p>${d.description}</p>
       <p class="mono">Score: ${d.score}/${d.max_score}</p>`
    ),
    card(
      "Suggested Allocation",
      `<ul>${Object.entries(d.allocation).map(([key, value]) => `<li>${key}: ${value}%</li>`).join("")}</ul>`
    ),
  ].join("");
}

async function runPredictionOnly() {
  const container = document.getElementById("analysisResult");
  container.innerHTML = card("Predicting", "<p>Training the Random Forest model...</p>");
  const result = await postJSON("/api/predict", { stock_name: document.getElementById("stock_name")?.value || "Reliance Industries" });

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const d = result.data;
  container.innerHTML = [
    card(
      "Prediction Summary",
      `<p><span class="pill ${statusClass(d.signal)}">${d.signal}</span></p>
       <p>${d.rationale}</p>
       <p>${currency(d.current_price)} to ${currency(d.predicted_5d_price)}</p>
       <p class="mono">Predicted path: ${d.predicted_prices.join(", ")}</p>
       <p class="mono">Latest price date: ${d.latest_trading_date}</p>`
    ),
    card(
      "Model Metrics",
      `<p class="mono">Accuracy: ${d.model_accuracy}%</p>
       <p class="mono">MAE: ${d.mae}</p>
       <p class="mono">MAPE: ${d.mape}%</p>
       <p class="mono">Data Source: ${d.data_source}</p>`
    ),
  ].join("");
}

async function runSip() {
  const payload = {
    salary: Number(document.getElementById("sip_salary").value),
    goal: Number(document.getElementById("sip_goal").value),
    years: Number(document.getElementById("sip_years").value),
    return_pct: Number(document.getElementById("sip_return").value),
  };
  const container = document.getElementById("sipResult");
  container.innerHTML = card("Calculating", "<p>Estimating SIP requirement...</p>");
  const result = await postJSON("/api/sip", payload);

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const d = result.data;
  const milestones = Object.entries(d.milestones)
    .map(([year, amount]) => `<li>${year}: ${currency(amount)}</li>`)
    .join("");
  const funds = (d.recommended_funds || [])
    .map(
      (fund) => `
        <tr>
          <td>${fund.name}</td>
          <td>${fund.category}</td>
          <td>${fund.risk}</td>
          <td>${fund.three_year_return}</td>
          <td>${fund.five_year_return}</td>
          <td>${currency(fund.min_sip)}</td>
        </tr>`
    )
    .join("");

  container.innerHTML = [
    card(
      "SIP Recommendation",
      `<p>${currency(d.monthly_sip)} per month</p>
       <p>${d.salary_percentage}% of salary | ${d.affordability}</p>
       <p>Total invested ${currency(d.total_invested)}</p>`
    ),
    card("Milestones", `<ul>${milestones}</ul>`),
    card(
      "Reference Buckets",
      `<ul>
        <li>Conservative: ${currency(d.suggested_sip_conservative)}</li>
        <li>Moderate: ${currency(d.suggested_sip_moderate)}</li>
        <li>Aggressive: ${currency(d.suggested_sip_aggressive)}</li>
      </ul>`
    ),
    card(
      "10 Mutual Fund Suggestions",
      `<div class="table-wrap">
        <table>
          <thead><tr><th>Fund</th><th>Category</th><th>Risk</th><th>3Y</th><th>5Y</th><th>Min SIP</th></tr></thead>
          <tbody>${funds}</tbody>
        </table>
      </div>
      <p class="mono">Shortlisted from current India SIP-focused fund lists and fund pages.</p>`,
      "full-width"
    ),
  ].join("");
}

async function loadPortfolio() {
  const container = document.getElementById("extraResult");
  container.innerHTML = card("Loading", "<p>Preparing portfolio suggestions...</p>");
  const result = await postJSON("/api/portfolio", {
    risk_profile: window.currentRiskProfile,
    amount: Number(document.getElementById("investment_amount").value),
  });

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const d = result.data;
  const funds = d.recommended_funds
    .map((fund) => `<li>${fund.name} | ${fund.category} | min SIP ${fund.min_sip}</li>`)
    .join("");
  const stocks = d.recommended_stocks
    .map((stock) => `<li>${stock.name} (${stock.symbol}) - ${stock.sector}</li>`)
    .join("");

  container.innerHTML = [
    card(
      "Portfolio Mix",
      `<ul>${Object.entries(d.allocation_inr).map(([k, v]) => `<li>${k}: ${currency(v)}</li>`).join("")}</ul>`
    ),
    card("Mutual Fund Suggestions", `<ul>${funds}</ul>`),
    card("Stock Bucket", `<ul>${stocks}</ul>`),
  ].join("");
}

async function loadUndervalued() {
  const container = document.getElementById("extraResult");
  container.innerHTML = card("Scanning", "<p>Checking price position and RSI...</p>");
  const result = await postJSON("/api/undervalued", { risk_profile: "Medium" });

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const rows = result.data
    .map(
      (stock) => `
        <tr>
          <td>${stock.name}</td>
          <td>${stock.symbol}</td>
          <td>${stock.undervalued_score}</td>
          <td>${stock.rsi}</td>
          <td>${stock.verdict}</td>
        </tr>`
    )
    .join("");

  container.innerHTML = card(
    "Undervalued Stocks",
    `<table>
      <thead><tr><th>Name</th><th>Symbol</th><th>Score</th><th>RSI</th><th>Verdict</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>`
  );
}

async function loadExitSignal() {
  const container = document.getElementById("extraResult");
  container.innerHTML = card("Checking", "<p>Building a simple exit signal from momentum...</p>");
  const result = await postJSON("/api/exit-signal", {
    stock_name: document.getElementById("stock_name")?.value || "Reliance Industries",
  });

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const d = result.data;
  container.innerHTML = card(
    "Exit Signal",
    `<p><span class="pill ${statusClass(d.signal)}">${d.signal}</span></p>
     <p>${d.reason}</p>
     <p class="mono">1W: ${d.ret_1w}% | 1M: ${d.ret_1m}% | Score: ${d.proxy_sentiment_score}</p>`
  );
}

async function loadIpo() {
  const container = document.getElementById("ipoResult");
  if (!container) return;

  container.innerHTML = card("Loading IPO Data", "<p>Fetching live IPO GMP, dates, and price bands...</p>");
  const result = await getJSON("/api/ipo");

  if (!result.success) {
    container.innerHTML = card("IPO Data Error", `<p>${result.error}</p>`);
    return;
  }

  if (!result.data || result.data.length === 0) {
    container.innerHTML = card(
      "No Live IPO Data Found",
      `<p>The public IPO GMP sources did not return open IPO data right now. Try refreshing after some time.</p>
       <p class="mono">GMP websites can change layout or temporarily block automated requests.</p>`
    );
    return;
  }

  const renderIpoTable = (title, ipos) => {
    if (!ipos.length) {
      return card(title, "<p>No IPOs found in this category right now.</p>", "full-width");
    }

    const rows = ipos
      .map(
        (ipo) => `
          <tr>
            <td>${ipo.name}</td>
            <td><span class="pill ${statusClass(ipo.status)}">${ipo.status}</span></td>
            <td>${ipo.issue_type}</td>
            <td>${ipo.apply_date}</td>
            <td>${ipo.close_date}</td>
            <td>${ipo.price_band}</td>
            <td>${ipo.gmp}</td>
            <td>${ipo.gmp_pct}</td>
            <td>${ipo.estimated_listing_price}</td>
            <td>${ipo.lot_size}</td>
            <td>${ipo.subscription}</td>
            <td><a href="${ipo.source_url}" target="_blank" rel="noreferrer">${ipo.source}</a></td>
          </tr>`
      )
      .join("");

    return card(
      title,
      `<div class="table-wrap">
        <table>
          <thead>
            <tr><th>IPO</th><th>Status</th><th>Type</th><th>Apply/Open Date</th><th>Close Date</th><th>Price Band</th><th>GMP</th><th>GMP % / Est.</th><th>Estimated Listing</th><th>Lot</th><th>Subscription</th><th>Source</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      </div>`,
      "full-width"
    );
  };

  const mainboardIpos = result.data.filter((ipo) => ipo.category !== "SME");
  const smeIpos = result.data.filter((ipo) => ipo.category === "SME");
  const latest = result.data[0]?.updated_at || "Just now";

  container.innerHTML = [
    renderIpoTable(`Mainboard IPOs (${mainboardIpos.length})`, mainboardIpos),
    renderIpoTable(`SME IPOs (${smeIpos.length})`, smeIpos),
    card(
      "IPO GMP Note",
      `<p class="mono">Last fetched: ${latest}. GMP is unofficial and should not be treated as guaranteed listing gain.</p>`,
      "full-width"
    ),
  ].join("");
}
async function loadInvestmentPlans() {
  const container = document.getElementById("plansResult");
  container.innerHTML = card("Building Plans", "<p>Generating automatic long-term company suggestions...</p>");
  const result = await postJSON("/api/investment-plans", {
    years: Number(document.getElementById("plan_years")?.value || 2),
    risk_profile: document.getElementById("plan_risk")?.value || "Balanced",
    top_n: Number(document.getElementById("plan_count")?.value || 10),
  });

  if (!result.success) {
    container.innerHTML = card("Error", `<p>${result.error}</p>`);
    return;
  }

  const rows = result.data
    .map(
      (plan) => `
        <tr>
          <td>${plan.name}</td>
          <td>${plan.sector}</td>
          <td>${currency(plan.current_price)}</td>
          <td>${currency(plan.target_price)}</td>
          <td>${plan.upside_pct}%</td>
          <td>${plan.annual_return}%</td>
          <td>${plan.score}</td>
          <td>${plan.confidence}</td>
          <td>${plan.time_span}</td>
          <td>${plan.suggestion}</td>
          <td>${plan.model_name}</td>
          <td>${plan.indicators_summary}</td>
        </tr>`
    )
    .join("");

  container.innerHTML = card(
    "Suggested Companies",
    `<div class="table-wrap">
      <table>
        <thead><tr><th>Company</th><th>Sector</th><th>Current</th><th>Target</th><th>Upside</th><th>Annual Return</th><th>Score</th><th>Confidence</th><th>Time Span</th><th>Suggestion</th><th>Model</th><th>Indicator Summary</th></tr></thead>
        <tbody>${rows}</tbody>
      </table>
    </div>
    <p class="mono">Uses multi-indicator scoring and, when available in the runtime, a tree-based ML ensemble for long-term return forecasting.</p>`,
    "full-width"
  );
}

document.getElementById("analyzeBtn")?.addEventListener("click", runFullAnalysis);
document.getElementById("riskOnlyBtn")?.addEventListener("click", runRiskOnly);
document.getElementById("predictBtn")?.addEventListener("click", runPredictionOnly);
document.getElementById("sipBtn")?.addEventListener("click", runSip);
document.getElementById("sipSecondaryBtn")?.addEventListener("click", runSip);
document.getElementById("portfolioBtn")?.addEventListener("click", loadPortfolio);
document.getElementById("undervaluedBtn")?.addEventListener("click", loadUndervalued);
document.getElementById("plansBtn")?.addEventListener("click", loadInvestmentPlans);
document.getElementById("ipoBtn")?.addEventListener("click", loadIpo);
document.getElementById("exitBtn")?.addEventListener("click", loadExitSignal);
if (window.location.pathname === "/ipo") loadIpo();



