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

def filter_graph(
    G: nx.DiGraph, selected: str, mode: str, partition: dict, expand_neighbors=False
) -> nx.DiGraph:
    if mode == "Focus on node & neighbors":
        neighbors = set(G.successors(selected)) | set(G.predecessors(selected))
        if expand_neighbors:
            # Espandi anche ai vicini dei vicini (2 salti)
            second_neighbors = set()
            for n in neighbors:
                second_neighbors |= set(G.successors(n)) | set(G.predecessors(n))
            nodes = {selected} | neighbors | second_neighbors
        else:
            nodes = {selected} | neighbors
        return G.subgraph(nodes).copy()
    if mode == "Selected Node's Community":
        comm = partition[selected]
        nodes = [n for n in G.nodes if partition[n] == comm]
        return G.subgraph(nodes).copy()
    return G

def display_network(
    G: nx.DiGraph, selected: str, mode: str, centrality: dict, partition: dict, palette: list, hierarchy: bool, direction: str, expand_neighbors: bool, node_attrs: dict
) -> None:
    net = Network(height="600px", width="100%", directed=True)
    for node in G.nodes:
        attrs = get_node_attrs(node, selected, mode, centrality, partition, palette, node_attrs)
        net.add_node(node, label=node, color=attrs["color"], size=attrs["size"], title=attrs["title"])
    for src, dst in G.edges:
        net.add_edge(src, dst)
    if hierarchy:
        net.set_options(f"""
        var options = {{
          "layout": {{
            "hierarchical": {{
              "enabled": true,
              "direction": "{direction}",
              "sortMethod": "directed"
            }}
          }}
        }}
        """)
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".html") as tmp_file:
        net.save_graph(tmp_file.name)
        html = open(tmp_file.name, "r", encoding="utf-8").read()
        st.components.v1.html(html, height=620, scrolling=True)

def main():
    st.title("Interactive Network Explorer")

    df = load_data(DATA_FILE, PARENT_COL, CHILD_COL)
    all_names = sorted(pd.unique(df[[PARENT_COL, CHILD_COL]].values.ravel("K")))
    selected_node = st.selectbox("Select a node:", all_names)
    view_mode = st.radio(
        "Visualization mode:",
        [
            "Focus on node & neighbors",
            "Betweenness Centrality",
            "All Communities",
            "Selected Node's Community"
        ]
    )

    palette_name = "Default (bold)"
    if view_mode in ("All Communities", "Selected Node's Community"):
        palette_name = st.selectbox("Community color palette", list(PALETTES), 0)
    palette = get_palette(palette_name)

    hierarchy = st.checkbox("Show as hierarchical layout", value=True)
    if hierarchy:
        direction_name = st.selectbox(
            "Hierarchy direction", ["Top-down", "Bottom-up", "Left-right", "Right-left"], 0
        )
        direction_map = {
            "Top-down": "UD",
            "Bottom-up": "DU",
            "Left-right": "LR",
            "Right-left": "R
