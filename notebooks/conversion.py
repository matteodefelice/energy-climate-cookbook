# %% 
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# Degree-Hour functions
# ─────────────────────────────────────────────

def heating_degree_hours(T: pd.Series, T_base: float = 15.5) -> pd.Series:
    """HDH: hours where temperature is below heating balance point."""
    return np.maximum(T_base - T, 0.0)

def cooling_degree_hours(T: pd.Series, T_base: float = 22.0) -> pd.Series:
    """CDH: hours where temperature is above cooling balance point."""
    return np.maximum(T - T_base, 0.0)


# ─────────────────────────────────────────────
# Temperature Response Function (TRF)
# ─────────────────────────────────────────────

def temperature_response_function(
    T: pd.Series,
    T_heat_base: float = 15.5,   # Eurostat heating balance point [°C]
    T_cool_base: float = 22.0,   # Eurostat cooling balance point [°C]
    beta_heat: float = 3.0,      # heating sensitivity [relative units/°C]
    beta_cool: float = 1.0,      # cooling sensitivity [relative units/°C]
    base_load_fraction: float = 0.6,  # share of demand that is temperature-insensitive
) -> pd.Series:
    """
    V-shaped Temperature Response Function for electricity demand.

    The output is a relative demand index, not absolute [MWh].
    It will be scaled and normalized in the next step.

    Parameters
    ----------
    T                  : hourly air temperature time series [°C]
    T_heat_base        : balance point below which heating demand kicks in
    T_cool_base        : balance point above which cooling demand kicks in
    beta_heat          : heating sensitivity (NW Europe: ~3x cooling)
    beta_cool          : cooling sensitivity
    base_load_fraction : fraction [0-1] of peak demand that is always present
    """
    hdh = heating_degree_hours(T, T_heat_base)
    cdh = cooling_degree_hours(T, T_cool_base)

    # Temperature-sensitive component (unnormalized)
    temp_sensitive = beta_heat * hdh + beta_cool * cdh

    # Total demand index
    demand = base_load_fraction + (1.0 - base_load_fraction) * temp_sensitive

    return demand


# ─────────────────────────────────────────────
# Weekly pattern (optional but realistic)
# ─────────────────────────────────────────────

def weekday_multiplier(index: pd.DatetimeIndex) -> pd.Series:
    """
    Apply a simple weekday/weekend demand multiplier.
    Weekdays ~5-10% higher than weekend. Rough EU average.
    """
    multiplier = np.where(index.dayofweek < 5, 1.05, 0.95)  # Mon-Fri vs Sat-Sun
    return pd.Series(multiplier, index=index)


# ─────────────────────────────────────────────
# Diurnal pattern (optional but realistic)
# ─────────────────────────────────────────────

def diurnal_multiplier(index: pd.DatetimeIndex) -> pd.Series:
    """
    Simplified diurnal load shape based on hour of day.
    Peaks around 8-9am and 6-8pm. Trough at 3-4am.
    Derived from typical ENTSO-E European load profiles.
    """
    # Normalized hourly weights (0=midnight ... 23=11pm)
    hourly_shape = np.array([
        0.75, 0.70, 0.67, 0.65, 0.67, 0.73,  # 0-5: night trough
        0.82, 0.92, 1.00, 0.98, 0.96, 0.95,  # 6-11: morning ramp & peak
        0.95, 0.94, 0.93, 0.92, 0.93, 0.97,  # 12-17: midday plateau
        1.00, 0.99, 0.95, 0.90, 0.85, 0.80,  # 18-23: evening peak & decline
    ])
    return pd.Series(hourly_shape[index.hour], index=index)


# ─────────────────────────────────────────────
# Method similar to Demand.ninja (Staffell et al., Nature Energy, 2024)
# ─────────────────────────────────────────────

def temperature_to_demand(
    T: pd.Series,
    T_heat_base: float = 15.5,
    T_cool_base: float = 22.0,
    beta_heat: float = 3.0,
    beta_cool: float = 1.0,
    base_load_fraction: float = 0.6,
    apply_diurnal: bool = True,
    apply_weekly: bool = True,
    normalize: bool = True,
) -> pd.DataFrame:
    """
    Convert hourly air temperature [°C] into normalized electricity demand.

    Output is in [0, 1] if normalize=True — directly usable as
    `p_set` or demand scaling factor in PyPSA or similar power system models.

    Parameters
    ----------
    T                  : pd.Series with DatetimeIndex, temperature [°C]
    T_heat_base        : heating balance point [°C]
    T_cool_base        : cooling balance point [°C]
    beta_heat          : heating sensitivity coefficient
    beta_cool          : cooling sensitivity coefficient
    base_load_fraction : temperature-insensitive load share [0-1]
    apply_diurnal      : add diurnal (time-of-day) demand shape
    apply_weekly       : apply weekday/weekend multiplier
    normalize          : normalize output to [0, 1]
    """
    # 1) Temperature-driven component
    demand = temperature_response_function(
        T,
        T_heat_base=T_heat_base,
        T_cool_base=T_cool_base,
        beta_heat=beta_heat,
        beta_cool=beta_cool,
        base_load_fraction=base_load_fraction,
    )

    # 2) Diurnal shape (optional)
    if apply_diurnal:
        demand = demand * diurnal_multiplier(T.index)

    # 3) Weekday/weekend modulation (optional)
    if apply_weekly:
        demand = demand * weekday_multiplier(T.index)

    # 4) Normalize to [0, 1]
    if normalize:
        demand = (demand - demand.min()) / (demand.max() - demand.min())

    # Build output dataframe
    result = pd.DataFrame({
        "temperature_C": T,
        "hdh": heating_degree_hours(T, T_heat_base),
        "cdh": cooling_degree_hours(T, T_cool_base),
        "demand_normalized": demand,
    }, index=T.index)

    return result

def pv_capacity_factor(G, T_air, gamma=-0.005, NOCT=45.0):
    """
    G      : surface solar irradiance (W/m²)
    T_air  : near-surface air temperature (°C)
    gamma  : temperature power coefficient (/°C), default -0.005
    NOCT   : nominal operating cell temperature (°C), default 45
    """
    G_STC = 1000.0   # W/m²
    T_STC = 25.0     # °C

    T_cell = T_air + ((NOCT - 20.0) / 800.0) * G
    CF = (G / G_STC) * (1 + gamma * (T_cell - T_STC))
    return CF.clip(0, 1)  # Ensure capacity factor is between 0 and 1

def water_cooling_efficiency(T_air):
    """
    Simple linear model for water cooling efficiency based on air temperature.
    Efficiency decreases as air temperature rises, due to reduced heat transfer. 
    From page 35: https://joint-research-centre.ec.europa.eu/document/download/4439ed82-8645-498e-820c-238ce0ff516c_en?filename=pesetaiv_task_4_energy_final_report.pdf
    Parameters:
    T_air : near-surface air temperature (°C)
    Returns:
    efficiency : cooling efficiency (0-1)
    """
    T = np.asarray(T_air)
    return np.where(
        T <= 26, 100,
        np.where(
            T <= 31, 100 - 7 * (T - 26),
            np.where(
                T <= 33, 65 - 32.5 * (T - 31),
                0
            )
        )
    ) / 100

def kaplan_efficiency(q):
    """
    Capture dependency of the turbine efficiency on the inflow

    Source: Yildiz, V., Brown, S. F., & Rougé, C. (2024). 
    Importance of variable turbine efficiency in run-of-river hydropower
    design under deep uncertainty. Water Resources Research
    https://doi.org/10.1029/2023WR035713

    q : relative flow Q/Qd

    Valid approximation range:
    q = 0.20 to 1.05
    """
    eta = (
        -8.51102355 * q**4
        + 24.85302040 * q**3
        - 26.40793000 * q**2
        + 12.07576883 * q
        - 1.11440779
    )
    return eta.clip(0, 1)


def francis_efficiency(q):
    """
    Capture dependency of the turbine efficiency on the inflow

    Source: Yildiz, V., Brown, S. F., & Rougé, C. (2024). 
    Importance of variable turbine efficiency in run-of-river hydropower
    design under deep uncertainty. Water Resources Research
    https://doi.org/10.1029/2023WR035713

    q : relative flow Q/Qd

    Valid approximation range:
    q = 0.35 to 1.05
    """
    eta = (
        -0.67586077 * q**4
        + 1.97865116 * q**3
        - 2.50076784 * q**2
        + 1.79933762 * q
        + 0.31234645
    )
    return eta.clip(0, 1)


def pelton_efficiency(q):
    """
    Capture dependency of the turbine efficiency on the inflow

    Source: Yildiz, V., Brown, S. F., & Rougé, C. (2024). 
    Importance of variable turbine efficiency in run-of-river hydropower
    design under deep uncertainty. Water Resources Research
    https://doi.org/10.1029/2023WR035713

    q : relative flow Q/Qd

    Valid approximation range:
    q = 0.10 to 1.05
    """
    eta = (
        -5.64513659 * q**4
        + 15.31207998 * q**3
        - 14.86220905 * q**2
        + 6.07135176 * q
        + 0.01488507
    )
    return eta.clip(0, 1)


def hydro_turbine_efficiency(q, turbine_type):
    """
    Capture dependency of the turbine efficiency on the inflow
    for different turbine types

    Source: Yildiz, V., Brown, S. F., & Rougé, C. (2024). 
    Importance of variable turbine efficiency in run-of-river hydropower
    design under deep uncertainty. Water Resources Research
    https://doi.org/10.1029/2023WR035713

    q : relative flow Q/Qd
                   where Q is full flow and Qd is design flow
    turbine_type : "Kaplan", "Francis", or "Pelton"
    """

    turbine_type = turbine_type.lower()

    if turbine_type == "kaplan":
        return kaplan_efficiency(q)

    elif turbine_type == "francis":
        return francis_efficiency(q)

    elif turbine_type == "pelton":
        return pelton_efficiency(q)

    else:
        raise ValueError("turbine_type must be 'Kaplan', 'Francis', or 'Pelton'")

# ─────────────────────────────────────────────
# Example usage
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Synthetic hourly temperature: annual sinusoid typical for NL/Germany
    # Jan mean ~3°C, Jul mean ~20°C
    rng = pd.date_range("2023-01-01", periods=8760, freq="h")
    day_of_year = np.arange(8760) / 24
    T_annual = 11.5 - 8.5 * np.cos(2 * np.pi * day_of_year / 365)  # [°C]
    T_daily   = 3.0 * np.sin(2 * np.pi * np.arange(8760) / 24)     # diurnal swing
    T_noise   = np.random.default_rng(42).normal(0, 1.5, 8760)      # day-to-day variability

    T = pd.Series(T_annual + T_daily + T_noise, index=rng, name="temperature_C")

    result = temperature_to_demand(
        T,
        T_heat_base=15.5,
        T_cool_base=22.0,
        beta_heat=3.0,       # NW Europe: heating-dominated
        beta_cool=1.0,
        base_load_fraction=0.6,
        apply_diurnal=True,
        apply_weekly=True,
        normalize=True,
    )

    print(result.head(24))
    print(f"\nPeak demand hour : {result['demand_normalized'].idxmax()}")
    print(f"Min  demand hour : {result['demand_normalized'].idxmin()}")

    # Save for power system model
    result["demand_normalized"].to_csv("demand_timeseries.csv")

# %%
