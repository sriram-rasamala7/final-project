def calculate_sip(monthly_salary, goal_amount, years, expected_return_pct=12.0):
    if monthly_salary <= 0:
        raise ValueError("Monthly salary should be greater than 0.")
    if goal_amount <= 0:
        raise ValueError("Goal amount should be greater than 0.")
    if years <= 0:
        raise ValueError("Years should be greater than 0.")

    monthly_rate = expected_return_pct / 100 / 12
    total_months = years * 12

    if monthly_rate == 0:
        monthly_sip = goal_amount / total_months
    else:
        monthly_sip = goal_amount * monthly_rate / (
            ((1 + monthly_rate) ** total_months - 1) * (1 + monthly_rate)
        )

    total_invested = monthly_sip * total_months
    estimated_gain = goal_amount - total_invested
    salary_percentage = (monthly_sip / monthly_salary) * 100

    affordability = "Comfortable"
    if salary_percentage > 35:
        affordability = "Stretch"
    elif salary_percentage > 20:
        affordability = "Moderate"

    return {
        "monthly_sip": round(monthly_sip, 2),
        "total_invested": round(total_invested, 2),
        "total_returns": round(estimated_gain, 2),
        "goal_amount": round(goal_amount, 2),
        "years": years,
        "expected_return_pct": expected_return_pct,
        "salary_percentage": round(salary_percentage, 2),
        "affordability": affordability,
        "suggested_sip_conservative": round(monthly_salary * 0.10, 2),
        "suggested_sip_moderate": round(monthly_salary * 0.20, 2),
        "suggested_sip_aggressive": round(monthly_salary * 0.30, 2),
    }


def get_sip_milestones(monthly_sip, expected_return_pct=12.0, years=20):
    monthly_rate = expected_return_pct / 100 / 12
    milestones = {}

    for year in range(1, years + 1):
        months = year * 12
        if monthly_rate == 0:
            future_value = monthly_sip * months
        else:
            future_value = monthly_sip * (((1 + monthly_rate) ** months - 1) / monthly_rate) * (
                1 + monthly_rate
            )
        if year in {1, 3, 5, 10, 15, 20} or year == years:
            milestones[f"{year}Y"] = round(future_value, 2)

    return milestones
