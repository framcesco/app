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

@st.cache_data(show_spinner=False)
def load_data(filepath: Path, parent: str, child: str) -> pd.DataFrame:
    df = pd.read_excel(filepath)
    df = df.dropna(subset=[parent, child])
    df[parent] = df[parent].astype(str)
    df[child] = df[child].astype(str)
    return df

def build_graph(df: pd.DataFrame, parent: str, child: str) -> nx.DiGraph:
    g = nx.DiGraph()
    g.add_edges_from(df[[parent, child]].values)
    for _, row in df.iterrows():
        attrs = row.dropna().to_dict()
        g.nodes[row[child]].update(attrs)
    return g

def get_palette(palette_name: str) -> list[str]:
    return PALETTES[palette_name]

def get_node_attrs(
    node: str, selected: str, mode: str, centrality: dict, partition: dict, palette: list, node_attrs: dict
) -> dict:
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
    st.title("XXXXXX")

    # 1. File upload e caricamento in memoria
    st.sidebar.header("Carica un nuovo file Excel")
    uploaded_file = st.sidebar.file_uploader(
        "Sostituisci il database (file Excel .xlsx)",
        type=["xlsx"],
        help="Carica un file con almeno le colonne 'nome_parent' e 'nome_nodo'."
    )

    if "df" not in st.session_state:
        st.session_state.df = load_data(DATA_FILE, PARENT_COL, CHILD_COL)
    if uploaded_file:
        st.session_state.df = load_data(uploaded_file, DATA_FILE, PARENT_COL, CHILD_COL)

    df = st.session_state.df

    # 2. Interfaccia AGGIUNTA/MODIFICA NODI E RELAZIONI
    with st.sidebar.expander("Aggiungi o modifica nodi/relazioni"):
        st.write("Aggiungi un nuovo nodo e/o una relazione.")
        nome_parent = st.text_input("Nodo sorgente (parent):", "")
        nome_nodo = st.text_input("Nodo destinazione (child):", "")
        # Altri attributi personalizzati:
        col_extra = [c for c in df.columns if c not in [PARENT_COL, CHILD_COL]]
        extra_data = {}
        for c in col_extra:
            extra_data[c] = st.text_input(f"{c}:", "")
        add_btn = st.button("Aggiungi nodo/relazione")

        if add_btn and nome_parent and nome_nodo:
            new_row = {PARENT_COL: nome_parent, CHILD_COL: nome_nodo}
            new_row.update({k: v for k, v in extra_data.items() if v})
            st.session_state.df = pd.concat([st.session_state.df, pd.DataFrame([new_row])], ignore_index=True)
            st.success(f"Aggiunta relazione: {nome_parent} → {nome_nodo}")

    # 3. Selezioni e visualizzazione grafo
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
        expand_neighbors = st.button("Espandi a vicini dei vicini (2 salti dal nodo selezionato)")

    G = build_graph(df, PARENT_COL, CHILD_COL)
    node_attrs = {n: G.nodes[n] for n in G.nodes}
    centrality = nx.betweenness_centrality(G)
    partition = community_louvain.best_partition(G.to_undirected())
    H = filter_graph(G, selected_node, view_mode, partition, expand_neighbors)

    col1, col2 = st.columns([3, 2])

    with col1:
        display_network(
            H, selected_node, view_mode, centrality, partition, palette,
            hierarchy, direction, expand_neighbors, node_attrs
        )

    with col2:
        st.subheader("Cruscotto grafo generale")
        st.markdown(f"""
        - **Nodi totali:** {G.number_of_nodes()}
        - **Archi totali:** {G.number_of_edges()}
        - **Densità:** {nx.density(G):.3f}
        - **Nodi isolati:** {len(list(nx.isolates(G)))}
        - **Componenti connesse:** {nx.number_weakly_connected_components(G)}
        """)
        try:
            st.markdown(f"- **Diametro (componente principale):** {nx.diameter(G.to_undirected())}")
        except Exception:
            st.markdown("- **Diametro (componente principale):** n/d")
        st.markdown(f"- **Numero community:** {len(set(partition.values()))}")

        if view_mode == "Selected Node's Community" and selected_node in partition:
            comm_id = partition[selected_node]
            comm_nodes = [n for n in G.nodes if partition[n] == comm_id]
            comm_subgraph = G.subgraph(comm_nodes)
            st.markdown("---")
            st.subheader(f"Dettagli Community {comm_id}")
            st.markdown(f"""
            - **Nodi nella community:** {len(comm_nodes)}
            - **Archi nella community:** {comm_subgraph.number_of_edges()}
            - **Nodi isolati:** {len(list(nx.isolates(comm_subgraph)))}
            """)
            sub_centrality = nx.betweenness_centrality(comm_subgraph)
            if sub_centrality:
                hub = max(sub_centrality, key=sub_centrality.get)
                st.markdown(f"- **Nodo più centrale:** {hub}")
        elif view_mode == "All Communities":
            st.markdown("---")
            st.subheader("Distribuzione nodi per community")
            import matplotlib.pyplot as plt
            comm_labels = [partition[n] for n in G.nodes]
            fig, ax = plt.subplots(figsize=(4,2))
            pd.Series(comm_labels).value_counts().sort_index().plot(kind='bar', ax=ax)
            ax.set_xlabel("Community")
            ax.set_ylabel("Numero nodi")
            st.pyplot(fig)

    if selected_node in G.nodes:
        st.subheader(f"Attributi nodo: {selected_node}")
        node_data = G.nodes[selected_node]
        st.json(dict(node_data))
    else:
        st.info("Seleziona un nodo per vedere gli attributi.")

    with st.expander("Mostra dati tabellari del sottografo attuale"):
        current_nodes = list(H.nodes)
        df_sub = df[df[PARENT_COL].isin(current_nodes) | df[CHILD_COL].isin(current_nodes)]
        st.dataframe(df_sub)

    # Download del file attuale aggiornato
    with st.sidebar.expander("Scarica il database attuale (Excel)"):
        towrite = tempfile.NamedTemporaryFile(delete=False, suffix=".xlsx")
        df.to_excel(towrite.name, index=False)
        st.download_button("Scarica file Excel aggiornato", open(towrite.name, "rb"), file_name="network_data_edit.xlsx")

    captions = {
        "Betweenness Centrality": "Node color and size = betweenness centrality.",
        "All Communities": "Nodes colored by community.",
        "Focus on node & neighbors": "Selected node and its direct neighbors only. (Usa il bottone per espandere a 2 salti)",
        "Selected Node's Community": "Solo la community del nodo selezionato viene mostrata e analizzata."
    }
    st.caption(captions[view_mode])

if __name__ == "__main__":
    main()
