# %%
import numpy as np
import pandas as pd

# ─────────────────────────────────────────────
# STEP 1 — Horizontal → In-plane irradiance
# (Simple fixed tilt correction, no full transposition)
# ─────────────────────────────────────────────

def horizontal_to_inplane(
    ghi: pd.Series,
    tilt_deg: float = 35.0,       # typical optimum tilt for Central Europe (~latitude)
    azimuth_correction: float = 1.0,  # 1.0 = due south, <1 for east/west facing
) -> pd.Series:
    """
    Approximate conversion from Global Horizontal Irradiance (GHI)
    to Global In-Plane Irradiance (GPOA) using a fixed empirical factor.

    For a south-facing panel at 35° tilt in Central Europe (~50°N),
    annual yield is ~10-15% higher than horizontal. We apply a simple
    geometric boost during daylight hours only.

    This is a deliberate simplification. For production use, replace
    with pvlib's `irradiance.get_total_irradiance()` with DHI/DNI decomposition.
    """
    # Simple cosine-based geometric factor: boost when sun is lower
    # Full transposition would need solar zenith angle per hour
    tilt_rad = np.radians(tilt_deg)
    # Empirical scalar for annual energy boost (not hourly geometry)
    # This is honest about what it is: a rough annual mean correction
    tilt_factor = 1.0 + 0.12 * np.sin(tilt_rad) * azimuth_correction

    return ghi * tilt_factor


# ─────────────────────────────────────────────
# STEP 2 — Cell temperature (Faiman model)
# Used by PVGIS, consistent with IEC 61853-3
# ─────────────────────────────────────────────

def cell_temperature_faiman(
    G: pd.Series,           # in-plane irradiance [W/m²]
    T_air: pd.Series,       # ambient air temperature [°C]
    wind_speed: float | pd.Series = 1.0,  # [m/s], default = calm
    U0: float = 25.0,       # constant heat loss coefficient [W/(m²·K)]
    U1: float = 6.84,       # wind-dependent heat loss coefficient [W·s/(m³·K)]
) -> pd.Series:
    """
    Faiman (2008) cell temperature model — used in PVGIS.
    T_cell = T_air + G / (U0 + U1 * wind_speed)

    U0=25, U1=6.84 are empirical defaults for free-standing (open-rack) modules.
    For rooftop (less ventilated): U0=20, U1=0 is a conservative estimate.
    """
    return T_air + G / (U0 + U1 * wind_speed)


# ─────────────────────────────────────────────
# STEP 3 — PV capacity factor (STC formula)
# ─────────────────────────────────────────────

def pv_capacity_factor(
    G: pd.Series,           # in-plane irradiance [W/m²]
    T_cell: pd.Series,      # cell temperature [°C]
    gamma: float = -0.004,  # power temp. coefficient [1/°C], -0.4%/°C for c-Si
    G_stc: float = 1000.0,  # STC irradiance [W/m²]
    T_stc: float = 25.0,    # STC temperature [°C]
    pr: float = 0.82,       # performance ratio (inverter + wiring + soiling losses)
) -> pd.Series:
    """
    Normalized PV output (capacity factor) from in-plane irradiance and cell temp.

    CF = PR * (G / G_STC) * [1 + gamma * (T_cell - T_STC)]

    Parameters
    ----------
    G       : in-plane irradiance [W/m²]
    T_cell  : PV cell temperature [°C]
    gamma   : temperature power coefficient [1/°C]
              c-Si (crystalline): -0.004 (most common, ~85% of market)
              CdTe thin-film   : -0.0025 (better in heat, e.g. First Solar)
              CIGS             : -0.0036
    G_stc   : reference irradiance at STC = 1000 W/m²
    T_stc   : reference temperature at STC = 25°C
    pr      : performance ratio (typical range 0.75–0.90)
    """
    raw_cf = pr * (G / G_stc) * (1.0 + gamma * (T_cell - T_stc))
    return raw_cf.clip(lower=0.0, upper=1.0)  # physical bounds


# ─────────────────────────────────────────────
# STEP 4 — Full pipeline
# ─────────────────────────────────────────────

def solar_to_capacity_factor(
    ghi: pd.Series,              # Global Horizontal Irradiance [W/m²]
    T_air: pd.Series,            # Ambient air temperature [°C]
    wind_speed: float | pd.Series = 1.0,
    tilt_deg: float = 35.0,
    azimuth_correction: float = 1.0,
    gamma: float = -0.004,       # c-Si default
    U0: float = 25.0,
    U1: float = 6.84,
    pr: float = 0.82,
) -> pd.DataFrame:
    """
    Convert hourly GHI [W/m²] + air temperature [°C] to PV capacity factor [0,1].

    This is the PVGIS-compatible physical model chain, simplified for
    use in power system models (e.g. PyPSA `p_max_pu` for solar generators).

    ERA5 note: 'ssrd' (surface solar radiation downwards) is in J/m² accumulated
    per hour — divide by 3600 to convert to W/m² before passing to this function.

    Parameters
    ----------
    ghi          : Global Horizontal Irradiance [W/m²]
    T_air        : ambient air temperature [°C]
    wind_speed   : wind speed at panel level [m/s], default 1 m/s
    tilt_deg     : panel tilt from horizontal [degrees], 35° suits ~50°N latitude
    azimuth_correction: 1.0 = south-facing, reduce for other orientations
    gamma        : PV temperature coefficient [1/°C]
    U0, U1       : Faiman model heat loss coefficients
    pr           : system performance ratio
    """
    # 1) Horizontal → in-plane irradiance
    G_plane = horizontal_to_inplane(ghi, tilt_deg=tilt_deg,
                                     azimuth_correction=azimuth_correction)

    # 2) Cell temperature via Faiman model
    T_cell = cell_temperature_faiman(G_plane, T_air,
                                      wind_speed=wind_speed, U0=U0, U1=U1)

    # 3) Capacity factor
    cf = pv_capacity_factor(G_plane, T_cell, gamma=gamma, pr=pr)

    return pd.DataFrame({
        "ghi_wm2":          ghi,
        "G_inplane_wm2":    G_plane,
        "T_air_C":          T_air,
        "T_cell_C":         T_cell,
        "capacity_factor":  cf,
    }, index=ghi.index)


# ─────────────────────────────────────────────
# Example usage
# ─────────────────────────────────────────────

if __name__ == "__main__":
    rng = pd.date_range("2023-01-01", periods=8760, freq="h")
    np.random.seed(42)

    # Synthetic GHI: seasonal + diurnal pattern (Netherlands / Germany style)
    day_of_year = np.arange(8760) / 24
    hour_of_day = np.arange(8760) % 24

    # Seasonal envelope: peaks ~600 W/m² in June, ~50 W/m² in December
    seasonal = 300 + 250 * np.sin(2 * np.pi * (day_of_year - 80) / 365)

    # Diurnal shape: bell curve peaking at solar noon (hour 12)
    diurnal = np.maximum(np.sin(np.pi * (hour_of_day - 6) / 12), 0) ** 1.5

    # Cloud noise
    cloud_noise = np.abs(np.random.normal(1.0, 0.3, 8760))

    ghi = pd.Series(
        np.maximum(seasonal * diurnal * cloud_noise, 0.0),
        index=rng, name="ghi_wm2"
    )

    # Synthetic temperature (reuse from previous demand model)
    T_annual = 11.5 - 8.5 * np.cos(2 * np.pi * day_of_year / 365)
    T_daily = 3.0 * np.sin(2 * np.pi * np.arange(8760) / 24)
    T_air = pd.Series(T_annual + T_daily, index=rng, name="T_air_C")

    result = solar_to_capacity_factor(
        ghi=ghi,
        T_air=T_air,
        wind_speed=1.5,      # light breeze — cools panels slightly
        tilt_deg=35,         # optimum for ~52°N (Netherlands)
        gamma=-0.004,        # standard c-Si
        pr=0.82,             # typical utility-scale European PV
    )

    annual_cf = result["capacity_factor"].mean()
    print(f"Annual mean capacity factor: {annual_cf:.3f}")  # expect ~0.11-0.13 for NL
    print(result[result["ghi_wm2"] > 0].head(12))

    # ERA5 users: convert ssrd [J/m²] → W/m² first
    # ghi_wm2 = ds["ssrd"].diff("time") / 3600  (hourly accumulation)

    result["capacity_factor"].to_csv("cf_solar_timeseries.csv")

# %%
