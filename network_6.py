from pathlib import Path
import streamlit as st
import pandas as pd
from pyvis.network import Network
import tempfile
import networkx as nx

try:
    import community as community_louvain
except ImportError:
    st.error("Install python-louvain: pip install python-louvain")
    st.stop()

DATA_FILE = Path("network_data.xlsx")
PARENT_COL = "nome_parent"
CHILD_COL = "nome_nodo"

PALETTES = {
    "Default (bold)": [
        "#e6194b","#3cb44b","#ffe119","#4363d8","#f58231","#911eb4","#46f0f0","#f032e6",
        "#bcf60c","#fabebe","#008080","#e6beff","#9a6324","#fffac8","#800000","#aaffc3",
        "#808000","#ffd8b1","#000075","#808080"
    ],
    "Pastel": [
        "#ffd1dc","#b5ead7","#ffdac1","#c7ceea","#ffb7b2","#b2f7ef","#c9c9ff","#f1cbff",
        "#f3ffe3","#ffcbf6","#f0e68c","#b3cde0","#decbe4","#b4e7d9","#fdfd96"
    ],
    "Vivid": [
        "#ff6f69","#ffcc5c","#88d8b0","#96ceb4","#ffeead","#ff6f69","#588c7e","#f2e394",
        "#f2ae72","#d96459","#8c4646","#f9d423","#fc913a","#ff4e50","#1e90ff"
    ]
}

def load_data(filepath: Path, parent: str, child: str) -> pd.DataFrame:
    df = pd.read_excel(filepath)
    df = df.dropna(subset=[parent, child])
    df[parent] = df[parent].astype(str)
    df[child] = df[child].astype(str)
    return df

def build_graph(df: pd.DataFrame, parent: str, child: str) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_edges_from(df[[parent, child]].values)
    # Salva attributi tabellari
    for _, row in df.iterrows():
        g.nodes[row[child]].update(row.dropna().to_dict())
    return g

def get_palette(palette_name: str) -> list[str]:
    return PALETTES[palette_name]

def get_node_attrs(
    node: str, selected: str, mode: str, centrality: dict, partition: dict, palette: list, node_attrs: dict
) -> dict:
    # Tooltip multi-riga (testo, NON HTML)
    title = "ATTRIBUTI NODO:\n" + "\n".join(
        [f"{k}: {v}" for k, v in node_attrs.get(node, {}).items()]
    )
    if mode == "Focus on node & neighbors":
        if node == selected:
            return {"color": "orange", "size": 35, "title": title}
        return {"color": "skyblue", "size": 20, "title": title}
    if mode == "Betweenness Centrality":
        val = centrality.get(node, 0)
        color = f"rgba(255,100,100,{0.2 + 0.8 * val})"
        size = 15 + val * 40
        return {"color": color, "size": size, "title": title}
    if mode in ("All Communities", "Selected Node's Community"):
        comm = partition[node]
        color = palette[comm % len(palette)]
        size = 40 if node == selected and mode == "Selected Node's Community" else 25
        return {"color": color, "size": size, "title": title}
    return {"color": "lightgray", "size": 15, "title": title}

def fi
