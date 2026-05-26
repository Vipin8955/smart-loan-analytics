import numpy as np
import pandas as pd
from repo_test import fetch_repo_history

# EMI Formula
def calculate_emi(P, annual_rate, years):
    r = annual_rate / (12 * 100)
    n = years * 12
    return (P * r * (1 + r)**n) / ((1 + r)**n - 1)

# Generate realistic bank rates
def generate_bank_rates(repo_series):
    spreads = np.random.uniform(2, 4, len(repo_series))
    return repo_series + spreads

if __name__ == "__main__":
    df_repo = fetch_repo_history()

    if df_repo is None or df_repo.empty:
        print("[ERROR] Could not load repo rate data. Exiting.")
        exit(1)

    repo_rates = df_repo["RepoRate"]
    bank_rates = generate_bank_rates(repo_rates)

    data = []

    for rate in bank_rates:
        # Vary principal randomly
        principal = np.random.uniform(800000, 1500000)

        # Vary tenure randomly
        years = np.random.uniform(5, 20)

        # Calculate EMI
        emi = calculate_emi(principal, rate, years)

        # Add stronger market noise
        noise = np.random.normal(0, 500)
        emi = emi + noise

        data.append([principal, rate, years, emi])

    df = pd.DataFrame(data, columns=["Principal", "Interest", "Tenure", "EMI"])

    print("\n✅ Empirical Dataset Created")
    print(df.head())
    print("\nEMI Mean:", round(df["EMI"].mean(), 2))
    print("EMI Std Dev:", round(df["EMI"].std(), 2))