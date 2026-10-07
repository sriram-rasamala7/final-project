def get_risk_profile(age, income, investment_horizon, risk_tolerance_score):
    if age < 18 or age > 100:
        raise ValueError("Age should be between 18 and 100.")
    if income <= 0:
        raise ValueError("Income should be greater than 0.")
    if investment_horizon <= 0:
        raise ValueError("Investment horizon should be at least 1 year.")
    if not 1 <= risk_tolerance_score <= 10:
        raise ValueError("Risk tolerance should be between 1 and 10.")

    score = 0

    if age <= 30:
        score += 3
    elif age <= 45:
        score += 2
    else:
        score += 1

    if income >= 150000:
        score += 3
    elif income >= 70000:
        score += 2
    else:
        score += 1

    if investment_horizon >= 10:
        score += 3
    elif investment_horizon >= 5:
        score += 2
    else:
        score += 1

    if risk_tolerance_score >= 8:
        score += 3
    elif risk_tolerance_score >= 5:
        score += 2
    else:
        score += 1

    if score >= 10:
        profile = "High"
        description = "You can tolerate higher volatility for long-term wealth creation."
        allocation = {"equity": 75, "debt": 10, "gold": 10, "liquid": 5}
        suitable_for = "Growth-focused investors with a long horizon."
        color = "#d64545"
    elif score >= 7:
        profile = "Medium"
        description = "You prefer a balanced strategy that mixes growth with stability."
        allocation = {"equity": 55, "debt": 25, "gold": 10, "liquid": 10}
        suitable_for = "Investors seeking moderate growth with controlled downside."
        color = "#d4a017"
    else:
        profile = "Low"
        description = "You value capital protection and predictable progress toward goals."
        allocation = {"equity": 30, "debt": 45, "gold": 15, "liquid": 10}
        suitable_for = "Conservative investors and near-term goal planning."
        color = "#1f9d55"

    return {
        "profile": profile,
        "score": score,
        "max_score": 12,
        "description": description,
        "allocation": allocation,
        "suitable_for": suitable_for,
        "color": color,
    }
