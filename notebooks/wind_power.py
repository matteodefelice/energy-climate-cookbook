# %%
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# STEP 1 — Wind height extrapolation
# ─────────────────────────────────────────────

def extrapolate_wind_speed(
    v10: pd.Series,
    hub_height: float = 100.0,
    method: str = "log",
    z0: float = 0.03,       # roughness length [m]: 0.03=open sea, 0.1=farmland, 0.5=suburbs
    alpha: float = 1 / 7,  # power law exponent (Hellmann exponent)
    ref_height: float = 10.0,
) -> pd.Series:
    """Extrapolate wind speed from reference height to hub height."""
    if method == "log":
        # Logarithmic wind profile (neutral atmospheric stability)
        return v10 * (np.log(hub_height / z0) / np.log(ref_height / z0))
    elif method == "power":
        # Power law (simpler, use when z0 is unknown)
        return v10 * (hub_height / ref_height) ** alpha
    else:
        raise ValueError("method must be 'log' or 'power'")


# ─────────────────────────────────────────────
# STEP 2 — Air density correction
# ─────────────────────────────────────────────

def air_density(
    temperature_K: float | pd.Series = 288.15,  # [K]
    pressure_Pa: float | pd.Series = 101325.0,  # [Pa]
) -> float | pd.Series:
    """Compute actual air density via ideal gas law. ρ = P / (R_d * T)"""
    R_d = 287.058  # specific gas constant for dry air [J/(kg·K)]
    return pressure_Pa / (R_d * temperature_K)


def density_correct_wind(
    v_hub: pd.Series,
    rho: float | pd.Series = 1.225,
    rho_ref: float = 1.225,  # ISA standard density
) -> pd.Series:
    """Density-correct hub-height wind speed (IEC 61400-12-1 approach)."""
    return v_hub * (rho / rho_ref) ** (1 / 3)


# ─────────────────────────────────────────────
# STEP 3 — Generic turbine power curve
# ─────────────────────────────────────────────

def generic_power_curve(
    v: np.ndarray,
    v_ci: float = 3.0,    # cut-in speed [m/s]
    v_r: float = 12.0,    # rated speed [m/s]
    v_co: float = 25.0,   # cut-out speed [m/s]
    smoothing: bool = True,
    k_smooth: float = 2.0,  # sigmoid steepness at transitions
) -> np.ndarray:
    """
    Generic IEC-style normalized power curve (output in [0, 1]).

    Uses a smooth sigmoid blend at transitions to avoid discontinuities
    that cause problems in gradient-based power system optimizers (e.g. PyPSA-Opt).

    Parameters
    ----------
    v        : wind speed array at hub height [m/s]
    v_ci     : cut-in speed [m/s]
    v_r      : rated speed [m/s]  
    v_co     : cut-out speed [m/s]
    smoothing: use sigmoid transitions (True) or hard step (False)
    k_smooth : sigmoid width parameter (larger = sharper)
    """
    v = np.asarray(v, dtype=float)
    
    # Core cubic ramp: normalized power in the ramp region
    p_ramp = np.clip((v**3 - v_ci**3) / (v_r**3 - v_ci**3), 0.0, 1.0)
    
    if smoothing:
        # Smooth sigmoid transitions — avoids numerical artifacts in solvers
        def sigmoid(x, center, k):
            return 1.0 / (1.0 + np.exp(-k * (x - center)))
        
        # Turn on smoothly at cut-in
        on_cutin  = sigmoid(v, v_ci, k_smooth)
        # Flatten at rated (cap cubic at 1.0)
        on_rated  = 1.0 - sigmoid(v, v_r, k_smooth)
        # Shut down at cut-out
        on_cutout = 1.0 - sigmoid(v, v_co, k_smooth)
        
        power = (p_ramp * on_rated + (1.0 - on_rated)) * on_cutin * on_cutout
    else:
        # Hard piecewise — clean but discontinuous
        power = np.where(
            v < v_ci,  0.0,
            np.where(
                v < v_r,  p_ramp,
                np.where(v <= v_co, 1.0, 0.0)
            )
        )
    
    return np.clip(power, 0.0, 1.0)


# ─────────────────────────────────────────────
# STEP 4 — Full pipeline: 10m wind → CF time series
# ─────────────────────────────────────────────

def wind_to_capacity_factor(
    v10: pd.Series,
    hub_height: float = 100.0,
    height_method: str = "log",
    z0: float = 0.03,
    alpha: float = 1 / 7,
    temperature_K: float | pd.Series = 288.15,
    pressure_Pa: float | pd.Series = 101325.0,
    v_ci: float = 3.0,
    v_r: float = 12.0,
    v_co: float = 25.0,
    smoothing: bool = True,
) -> pd.DataFrame:
    """
    Convert 10m wind speed time series to wind turbine capacity factor.

    Parameters
    ----------
    v10         : pd.Series with DatetimeIndex, wind speed at 10m [m/s]
    hub_height  : turbine hub height [m], default 100m (modern onshore)
    height_method: 'log' (default) or 'power'
    z0          : surface roughness length [m] for log-law (ignored for 'power')
    alpha       : power-law exponent (ignored for 'log')
    temperature_K: air temperature [K], scalar or matching Series
    pressure_Pa : air pressure [Pa], scalar or matching Series
    v_ci / v_r / v_co: turbine cut-in, rated, cut-out speeds [m/s]
    smoothing   : use sigmoid-smoothed transitions

    Returns
    -------
    pd.DataFrame with columns: v_10m, v_hub, v_hub_density_corrected, capacity_factor
    """
    # 1) Height extrapolation
    v_hub = extrapolate_wind_speed(
        v10, hub_height=hub_height,
        method=height_method, z0=z0, alpha=alpha
    )
    
    # 2) Air density correction
    rho = air_density(temperature_K, pressure_Pa)
    v_corrected = density_correct_wind(v_hub, rho=rho)
    
    # 3) Power curve → capacity factor
    cf = generic_power_curve(
        v_corrected.values, v_ci=v_ci, v_r=v_r, v_co=v_co, smoothing=smoothing
    )
    
    return pd.DataFrame({
        "v_10m": v10,
        "v_hub": v_hub,
        "v_hub_density_corrected": v_corrected,
        "capacity_factor": cf,
    }, index=v10.index)


# ─────────────────────────────────────────────
# Example usage
# ─────────────────────────────────────────────

if __name__ == "__main__":
    # Synthetic hourly time series (8760 hours)
    rng = pd.date_range("2023-01-01", periods=8760, freq="h")
    rng_seed = np.random.default_rng(42)
    v10_synthetic = pd.Series(
        np.abs(rng_seed.normal(loc=7.0, scale=3.5, size=8760)),
        index=rng, name="wind_speed_10m"
    )

    result = wind_to_capacity_factor(
        v10_synthetic,
        hub_height=100,         # m — onshore generic
        height_method="log",
        z0=0.03,                # open terrain / light coast
        temperature_K=283.15,   # ~10°C, typical NL annual mean
        pressure_Pa=101325.0,
        v_ci=3.0, v_r=12.0, v_co=25.0,
        smoothing=True,
    )

    annual_cf = result["capacity_factor"].mean()
    print(f"Annual mean capacity factor: {annual_cf:.3f}")
    print(result.head(10))
    # Save for power system model ingestion
    result["capacity_factor"].to_csv("cf_wind_timeseries.csv")

# %%
