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
    # Aggiungi tutti gli attributi tabellari al nodo 'child'
    for _, row in df.iterrows():
        attrs = row.dropna().to_dict()
        g.nodes[row[child]].update(attrs)
    return g

def get_palette(palette_name: str) -> list[str]:
    return PALETTES[palette_name]

def get_node_attrs(
    node: str, selected: str, mode: str, centrality: dict, partition: dict, palette: list, node_attrs: dict
) -> dict:
    # Tooltip HTML con tutti gli attributi disponibili per questo nodo
    title = "<br>".join([f"<b>{k}:</b> {v}" for k, v in node_attrs.get(node, {}).items()])
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
            # Espandi tutti i nodi degree 1 connessi
            extra = set()
            for n in neighbors:
                deg = G.degree(n)
                if deg == 1:
                    extra |= set(G.successors(n)) | set(G.predecessors(n))
            nodes = {selected} | neighbors | extra
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
            "Right-left": "RL"
        }
        direction = direction_map[direction_name]
    else:
        direction = "UD"

    expand_neighbors = False
    if view_mode == "Focus on node & neighbors":
        expand_neighbors = st.button("Double-click: show all degree 1 neighbors (simulate double click)")

    G = build_graph(df, PARENT_COL, CHILD_COL)
    # Preleva tutti gli attributi disponibili per ogni nodo
    node_attrs = {n: G.nodes[n] for n in G.nodes}
    centrality = nx.betweenness_centrality(G)
    partition = community_louvain.best_partition(G.to_undirected())
    H = filter_graph(G, selected_node, view_mode, partition, expand_neighbors)
    display_network(H, selected_node, view_mode, centrality, partition, palette, hierarchy, direction, expand_neighbors, node_attrs)

    # Attributi del nodo selezionato dalla combo
    if selected_node in G.nodes:
        st.subheader(f"Attributi nodo: {selected_node}")
        node_data = G.nodes[selected_node]
        st.json(dict(node_data))
    else:
        st.info("Seleziona un nodo per vedere gli attributi.")

    # Visualizza dati tabellari del sottografo
    with st.expander("Mostra dati tabellari del sottografo attuale"):
        current_nodes = list(H.nodes)
        df_sub = df[df[PARENT_COL].isin(current_nodes) | df[CHILD_COL].isin(current_nodes)]
        st.dataframe(df_sub)

    captions = {
        "Betweenness Centrality": "Node color and size = betweenness centrality.",
        "All Communities": "Nodes colored by community.",
        "Focus on node & neighbors": "Selected node and its direct neighbors only.",
        "Selected Node's Community": "Only the selected node's community is shown, with chosen palette."
    }
    st.caption(captions[view_mode])

if __name__ == "__main__":
    main()
