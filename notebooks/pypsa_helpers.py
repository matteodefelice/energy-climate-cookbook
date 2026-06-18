import pandas as pd
# quick fix for PyPSA Arrow issue
pd.options.future.infer_string = False

import matplotlib.pyplot as plt
import pypsa

from pathlib import Path
from typing import Union

solar_capital_cost=0.04
hydro_capital_cost=1.0
diesel_capital_cost=0.3
fuel_cost=(50/1e5)
battery_capital_cost=2.0

n_max_hours = 24 #24
n_hours_battery = 10


def extract_year(merged_df: pd.DataFrame, year: Union[int, list[int]]) -> pd.DataFrame:
    """
    Extract one or more calendar years from merged_df.

    Assumes merged_df has a datetime-like index.
    """

    df = merged_df.copy()
    df["time"] = pd.to_datetime(df.index)

    years = [year] if isinstance(year, int) else year

    year_df = df[df["time"].dt.year.isin(years)].copy()

    return year_df.reset_index(drop=True)

def build_microgrid(
        df,
        solar_capital_cost=solar_capital_cost,
        hydro_capital_cost=hydro_capital_cost,
        diesel_capital_cost=diesel_capital_cost,
        battery_capital_cost=battery_capital_cost,
        fuel_cost=fuel_cost,        
    ):
    """
    Optimise a model with considering hydro, solar and diesel
    """
    network = pypsa.Network(snapshots = df.index)
    network.add("Bus", "B1")

    network.add("Generator", "PV",
                carrier = "solar",
                bus="B1",
                capital_cost = solar_capital_cost,
                #p_nom_max = 600_000,
                p_max_pu = df["solar"],
                p_nom_extendable = True,
                )

    # a fake generator which represents unserved energy 
    network.add("Generator", "LoadShedding",
                carrier = "shedding",
                bus="B1",
                capital_cost = 0,
                marginal_cost = 100_000,
                p_nom_extendable = True)

    network.add("StorageUnit", "Hydro",
                bus="B1",
                carrier="hydro",
                max_hours = n_max_hours,
                p_max_pu=1.0,  # dispatch
                p_min_pu=0.0,  # store
                capital_cost = hydro_capital_cost,
                inflow = df["hydro"],       
                p_nom_extendable = True,
                efficiency_dispatch=0.9,
                efficiency_store=0.0,
                cyclic_state_of_charge=True)
    
    network.add("Generator", "diesel",
                carrier = "diesel",
                bus="B1",
                capital_cost = diesel_capital_cost,
                # NB nor operational_cost which are summed up with capital costs
                marginal_cost = fuel_cost,
                p_nom_extendable = True,
                )  

    network.add("StorageUnit", "Battery",
            bus="B1",
            carrier="battery",
            max_hours = n_hours_battery,
            capital_cost = battery_capital_cost,     
            p_nom_extendable = True,
            efficiency_dispatch=0.9,
            efficiency_store=0.9,
            cyclic_state_of_charge=True)  

    network.add("Load", "L1",
                bus="B1",
                carrier="el_demand",                
                p_set=df["load"])
    return network

def build_green_microgrid(
        df
    ):
    """
    Optimise a model with considering hydro and solar only
    """
    network = pypsa.Network(snapshots = df.index)
    network.add("Bus", "B1")

    network.add("Generator", "PV",
                carrier = "solar",
                bus="B1",
                capital_cost = solar_capital_cost,
                #p_nom_max = 600_000,
                p_max_pu = df["solar"],
                p_nom_extendable = True,
                )

    # a fake generator which represents unserved energy 
    network.add("Generator", "LoadShedding",
                carrier = "shedding",
                bus="B1",
                capital_cost = 0,
                marginal_cost = 100_000,
                p_nom_extendable = True)

    network.add("StorageUnit", "Hydro",
                bus="B1",
                carrier="hydro",
                max_hours = n_max_hours,
                p_max_pu=1.0,  # dispatch
                p_min_pu=0.0,  # store
                capital_cost = hydro_capital_cost,
                inflow = df["hydro"],       
                p_nom_extendable = True,
                efficiency_dispatch=0.9,
                efficiency_store=0.0,
                cyclic_state_of_charge=True)

    network.add("Load", "L1",
                bus="B1",
                carrier="el_demand",                
                p_set=df["load"])
    return network

# plotting functions ----------------------------------------------------------

#def plot_microgrid(n):
#    """
#    Plot disel + RES microgrid
#    """
#    fig, ax = plt.subplots(figsize=(14, 5))
#
#    dispatch_hourly = pd.DataFrame({
#        "PV": n.generators_t["p"]["PV"],
#        "diesel": n.generators_t["p"]["diesel"],
#        "Hydro": n.storage_units_t["p"]["Hydro"],
#        #"LoadShedding": -1 * n.generators_t["p"]["LoadShedding"],
#    })
#
#    dispatch = dispatch_hourly.resample("D").sum()
#
#    # Stack PV and Hydro
#    dispatch[["PV", "Hydro", "diesel"]].plot.area(
#        ax=ax,
#        linewidth=0,
#        color={
#            "PV": "#FFB347",       # pastel orange
#            "Hydro": "#4DA3FF",    # soft blue
#            "diesel": "gray"
#        },
#    )
#
#    ## Plot LoadShedding as negative reddish line
#    #dispatch["LoadShedding"].plot(
#    #    ax=ax,
#    #    color="#E57373",           # reddish
#    #    linewidth=1.8,
#    #    label="LoadShedding",
#    #)
#
#    #ax.axhline(0, color="black", linewidth=0.8)
#    ax.set_title("Dispatch")
#    ax.set_xlabel("Time")
#    ax.set_ylabel("Power")
#    ax.legend(loc="best")
#
#    plt.tight_layout()

def plot_microgrid(n):
    """
    Plot disel + RES microgrid
    """
    fig, ax = plt.subplots(figsize=(14, 5))

    dispatch_hourly = pd.DataFrame({
        "PV": n.generators_t["p"]["PV"],
        "Diesel": n.generators_t["p"]["Diesel"],
        "Hydro": n.storage_units_t["p"]["Hydro"],
        #"LoadShedding": -1 * n.generators_t["p"]["LoadShedding"],
    })
    dispatch = dispatch_hourly.resample("D").sum()

    # Stack PV and Hydro
    dispatch[["PV", "Hydro", "Diesel"]].plot.area(
        ax=ax,
        linewidth=0,
        color={
            "PV": "#FFB347",       # pastel orange
            "Hydro": "#4DA3FF",    # soft blue
            "Diesel": "gray"
        },
    )

    ## Plot LoadShedding as negative reddish line
    #dispatch["LoadShedding"].plot(
    #    ax=ax,
    #    color="#E57373",           # reddish
    #    linewidth=1.8,
    #    label="LoadShedding",
    #)

    #ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Dispatch")
    ax.set_xlabel("Time")
    ax.set_ylabel("Power")
    ax.legend(loc="best")

    plt.tight_layout()

def plot_microgrid_ax(n, ax):
    """
    Plot disel + RES microgrid
    """
    dispatch_hourly = pd.DataFrame({
        "PV": n.generators_t["p"]["PV"],
        "diesel": n.generators_t["p"]["diesel"],
        "Hydro": n.storage_units_t["p"]["Hydro"],
        "LoadShedding": -1 * n.generators_t["p"]["LoadShedding"],
    })
    dispatch = dispatch_hourly.resample("D").sum()

    # Stack PV and Hydro
    dispatch[["PV", "Hydro", "diesel"]].plot.area(
        ax=ax,
        linewidth=0,
        color={
            "PV": "#FFB347",       # pastel orange
            "Hydro": "#4DA3FF",    # soft blue
            "diesel": "gray"
        },
    )

    # Plot LoadShedding as negative reddish line
    dispatch["LoadShedding"].plot(
        ax=ax,
        color="#E57373",           # reddish
        linewidth=1.8,
        label="LoadShedding",
    )

    #ax.axhline(0, color="black", linewidth=0.8)
    ax.set_title("Dispatch")
    ax.set_xlabel("Time")
    ax.set_ylabel("Power")
    ax.legend(loc="best")

    return ax

def plot_microgrid_facets(networks, titles=None):
    """
    Plot several microgrid dispatch plots as vertical facets.

    Parameters
    ----------
    networks : list
        List of PyPSA networks or network-like objects.
    titles : list[str], optional
        Titles for each facet.
    """
    n_facets = len(networks)

    fig, axes = plt.subplots(
        nrows=n_facets,
        ncols=1,
        figsize=(14, 4 * n_facets),
        squeeze=False,
    )

    axes = axes.ravel()

    if titles is None:
        titles = [f"Dispatch {i + 1}" for i in range(n_facets)]

    for ax, network, title in zip(axes, networks, titles):
        plot_microgrid_ax(network, ax=ax)
        ax.set_title(title)

    axes[-1].set_xlabel("Time")

    for ax in axes[:-1]:
        ax.set_xlabel("")

    plt.tight_layout()
    return fig, axes







def plot_green_microgrid(n):
    """
    Plot hydro + PV microgrid
    """
    fig, ax = plt.subplots(figsize=(14, 5))

    dispatch_hourly = pd.DataFrame({
        "PV": n.generators_t["p"]["PV"],
        "Hydro": n.storage_units_t["p"]["Hydro"],
        "LoadShedding": -1 * n.generators_t["p"]["LoadShedding"],
    })

    dispatch = dispatch_hourly.resample("D").sum()

    dispatch[["PV", "Hydro"]].plot.area(
        ax=ax,
        linewidth=0,
        color={
            "PV": "#FFB347",
            "Hydro": "#4DA3FF",
        },
    )

    dispatch["LoadShedding"].plot(
        ax=ax,
        color="#E57373",
        linewidth=1.8,
        label="LoadShedding",
    )

    #ax.axhline(0, color="black", linewidth=0.8)
    #ax.set_title("Dispatch")
    #ax.set_xlabel("Time")
    #ax.set_ylabel("Power")
    #ax.legend(loc="best")

    plt.tight_layout()
    plt.show()    