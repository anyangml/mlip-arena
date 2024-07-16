from pathlib import Path

import numpy as np
import pandas as pd
import plotly.colors as pcolors
import plotly.graph_objects as go
import streamlit as st
from ase.data import chemical_symbols
from plotly.subplots import make_subplots
from scipy.interpolate import CubicSpline

from mlip_arena.models import REGISTRY

st.markdown(
"""
# Homonuclear Diatomics

Homonuclear diatomics are molecules composed of two atoms of the same element.
The potential energy curves of homonuclear diatomics are the most fundamental interactions between atoms in quantum chemistry.
"""
)

st.markdown("### Methods")
container = st.container(border=True)
valid_models = [model for model, metadata in REGISTRY.items() if Path(__file__).stem in metadata.get("gpu-tasks", [])]
methods = container.multiselect("MLIPs", valid_models, ["MACE-MP(M)", "EquiformerV2(OC22)", "CHGNet", "eSCN(OC20)", "ALIGNN"])
dft_methods = container.multiselect("DFT Methods", ["GPAW"], [])

st.markdown("### Settings")
vis = st.container(border=True)
energy_plot = vis.checkbox("Show energy curves", value=True)
force_plot = vis.checkbox("Show force curves", value=False)
ncols = vis.select_slider("Number of columns", options=[1, 2, 3, 4], value=2)

# Get all attributes from pcolors.qualitative
all_attributes = dir(pcolors.qualitative)
color_palettes = {attr: getattr(pcolors.qualitative, attr) for attr in all_attributes if isinstance(getattr(pcolors.qualitative, attr), list)}
color_palettes.pop("__all__", None)

palette_names = list(color_palettes.keys())
palette_colors = list(color_palettes.values())

palette_name = vis.selectbox(
    "Color sequence",
    options=palette_names, index=22
)

color_sequence = color_palettes[palette_name] # type: ignore

DATA_DIR = Path("mlip_arena/tasks/diatomics")
if not methods:
    st.stop()
dfs = [pd.read_json(DATA_DIR / REGISTRY[method]["family"] /  "homonuclear-diatomics.json") for method in methods]

dfs.extend([pd.read_json(DATA_DIR / method.lower() /  "homonuclear-diatomics.json") for method in dft_methods])



df = pd.concat(dfs, ignore_index=True)
df.drop_duplicates(inplace=True, subset=["name", "method"])

method_color_mapping = {method: color_sequence[i % len(color_sequence)] for i, method in enumerate(df["method"].unique())}

for i, symbol in enumerate(chemical_symbols[1:]):

    if i % ncols == 0:
        cols = st.columns(ncols)

    rows = df[df["name"] == symbol + symbol]

    if rows.empty:
        continue

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    elo, flo = float("inf"), float("inf")

    for j, method in enumerate(rows["method"].unique()):
        row = rows[rows["method"] == method].iloc[0]

        rs = np.array(row["R"])
        es = np.array(row["E"])
        fs = np.array(row["F"])

        rs = np.array(rs)
        ind = np.argsort(rs)
        es = np.array(es)
        fs = np.array(fs)

        rs = rs[ind]
        es = es[ind]
        if "GPAW" not in method:
            es = es - es[-1]
        else:
            pass

        if "GPAW" not in method:
            fs = fs[ind]

        if "GPAW" in method:
            xs = np.linspace(rs.min()*0.99, rs.max()*1.01, int(5e2))
        else:
            xs = rs

        if energy_plot:
            if "GPAW" in method:
                cs = CubicSpline(rs, es)
                ys = cs(xs)
            else:
                ys = es

            elo = min(elo, max(ys.min()*1.2, -15), -1)

            fig.add_trace(
                go.Scatter(
                    x=xs, y=ys,
                    mode="lines",
                    line=dict(
                        color=method_color_mapping[method],
                        width=3,
                    ),
                    name=method,
                ),
                secondary_y=False,
            )

        if force_plot and "GPAW" not in method:
            ys = fs

            flo = min(flo, max(ys.min()*1.2, -50))

            fig.add_trace(
                go.Scatter(
                    x=xs, y=ys,
                    mode="lines",
                    line=dict(
                        color=method_color_mapping[method],
                        width=2,
                        dash="dashdot",
                    ),
                    name=method,
                    showlegend=not energy_plot,
                ),
                secondary_y=True,
            )

    name = f"{symbol}-{symbol}"

    fig.update_layout(
        showlegend=True,
        title_text=f"{name}",
        title_x=0.5,
    )

    # Set x-axis title
    fig.update_xaxes(title_text="Distance [Å]")

    # Set y-axes titles
    if energy_plot:

        fig.update_layout(
            yaxis=dict(
                title=dict(text="Energy [eV]"),
                side="left",
                range=[elo, 2*(abs(elo))],
            )
        )

    if force_plot:

        fig.update_layout(
            yaxis2=dict(
                title=dict(text="Force [eV/Å]"),
                side="right",
                range=[flo, 1.5*abs(flo)],
                overlaying="y",
                tickmode="sync",
            ),
        )

    cols[i % ncols].plotly_chart(fig, use_container_width=True)
