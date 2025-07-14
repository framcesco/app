from pathlib import Path
import streamlit as st
import pandas as pd
from pyvis.network import Network
import tempfile
import networkx as nx
import matplotlib.pyplot as plt

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
    for _, row in df.iterrows():
        g.nodes[row[child]].update(row.dropna().to_dict())
    return g

def get_palette(palette_name: str) -> list[str]:
    return PALETTES[palette_name]

def get_node_attrs(node: str, selected: str, mode: str, centrality: dict, partition: dict, palette: list, node_attrs: dict) -> dict:
    title = "ATTRIBUTI NODO:\n" + "\n".join([f"{k}: {v}" for k, v in node_attrs.get(node, {}).items()])
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

def filter_graph(G: nx.DiGraph, selected: str, mode: str, partition: dict, expand_neighbors=False) -> nx.DiGraph:
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

def display_network(G: nx.DiGraph, selected: str, mode: str, centrality: dict, partition: dict, palette: list, hierarchy: bool, direction: str, expand_neighbors: bool, node_attrs: dict) -> None:
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

    st.markdown("""
    **Gestione database della rete**
    - Carica un file Excel della tua rete con colonne: `nome_parent`, `nome_nodo` (almeno queste!).
    - Premi su 'Reset database' per eliminare il file corrente e ripartire da zero.
    """)

    uploaded_file = st.file_uploader("Carica un nuovo file Excel della rete", type=["xlsx"])
    col1, col2 = st.columns([1, 2])
    with col1:
        reset_db = st.button("Reset database", help="Elimina il file corrente e riparti")

    if reset_db:
        if DATA_FILE.exists():
            DATA_FILE.unlink()
            st.success("Database eliminato! Carica un nuovo file per ricominciare.")
            st.stop()
        else:
            st.warning("Nessun database da eliminare.")
            st.stop()

    if uploaded_file:
        with open(DATA_FILE, "wb") as f:
            f.write(uploaded_file.read())
        st.success("File caricato correttamente! Ricarica la pagina per continuare.")
        st.stop()

    if not DATA_FILE.exists():
        st.info("🔼 Carica prima un file Excel per iniziare.")
        st.stop()

    # --- Caricamento rete ---
    try:
        df = load_data(DATA_FILE, PARENT_COL, CHILD_COL)
    except Exception as e:
        st.error(f"Errore nel caricamento del file: {e}")
        st.stop()

    G = build_graph(df, PARENT_COL, CHILD_COL)
    node_attrs = {n: G.nodes[n] for n in G.nodes}
    centrality = nx.betweenness_centrality(G)
    partition = community_louvain.best_partition(G.to_undirected())

    num_nodes = G.number_of_nodes()
    num_edges = G.number_of_edges()
    num_communities = len(set(partition.values()))
    degrees = dict(G.degree())
    max_degree_node = max(degrees, key=degrees.get)
    max_degree = degrees[max_degree_node]
    max_centrality_node = max(centrality, key=centrality.get)
    max_centrality = centrality[max_centrality_node]

    # --- Layout: Infografica + Teoria grafi ---
    col_infog, col_side = st.columns([2, 1])

    with col_infog:
        st.markdown("## 📊 Infografica della rete caricata")
        c1, c2, c3 = st.columns(3)
        c1.metric("Nodi", num_nodes)
        c2.metric("Collegamenti", num_edges)
        c3.metric("Comunità", num_communities)
        st.markdown("### 🔝 Nodo con più collegamenti")
        st.write(f"**{max_degree_node}** ({max_degree} collegamenti)")
        st.markdown("### ⭐ Nodo più centrale (betweenness)")
        st.write(f"**{max_centrality_node}** (Centralità = {max_centrality:.2f})")
        with st.expander("Distribuzione dei gradi dei nodi"):
            fig, ax = plt.subplots()
            ax.hist(list(degrees.values()), bins=15)
            ax.set_xlabel("Grado (numero collegamenti)")
            ax.set_ylabel("Numero nodi")
            st.pyplot(fig)

    with col_side:
        st.markdown("## ℹ️ Teoria dei grafi")
        # Densità
        density = nx.density(G)
        st.metric("Densità", f"{density:.3f}")

        # Diametro (solo se connesso)
        try:
            diameter = nx.diameter(G)
            st.metric("Diametro", diameter)
        except:
            st.metric("Diametro", "Non calcolabile")

        # Lunghezza media cammini
        try:
            avg_path = nx.average_shortest_path_length(G)
            st.metric("Lunghezza media cammino", f"{avg_path:.2f}")
        except:
            st.metric("Lunghezza media cammino", "Non calcolabile")

        # Grado medio
        avg_degree = sum(degrees.values())/num_nodes if num_nodes > 0 else 0
        st.metric("Grado medio", f"{avg_degree:.2f}")

        # Clustering coefficient medio (grafo non orientato)
        try:
            clustering = nx.average_clustering(G.to_undirected())
            st.metric("Clustering coeff. medio", f"{clustering:.2f}")
        except:
            st.metric("Clustering coeff. medio", "-")

        # Percentuale nodi isolati
        num_isolated = len(list(nx.isolates(G)))
        perc_isolated = (num_isolated/num_nodes)*100 if num_nodes > 0 else 0
        st.metric("Nodi isolati", f"{num_isolated} ({perc_isolated:.1f}%)")

        # Nodi foglia (out_degree = 0)
        num_leaf = sum(1 for n, d in G.out_degree() if d == 0)
        st.metric("Nodi foglia (out)", num_leaf)

    # --- Interfaccia standard ---
    all_names = sorted(pd.unique(df[[PARENT_COL, CHILD_COL]].values.ravel("K")))
    selected_node = st.selectbox("Scegli un nodo", all_names)
    view_mode = st.radio(
        "Modalità di visualizzazione",
        [
            "Focus on node & neighbors",
            "Betweenness Centrality",
            "All Communities",
            "Selected Node's Community"
        ]
    )

    palette_name = "Default (bold)"
    if view_mode in ("All Communities", "Selected Node's Community"):
        palette_name = st.selectbox("Palette colori comunità", list(PALETTES), 0)
    palette = get_palette(palette_name)

    hierarchy = st.checkbox("Mostra layout gerarchico", value=True)
    if hierarchy:
        direction_name = st.selectbox(
            "Direzione gerarchica", ["Top-down", "Bottom-up", "Left-right", "Right-left"], 0
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

    H = filter_graph(G, selected_node, view_mode, partition, expand_neighbors)
    display_network(H, selected_node, view_mode, centrality, partition, palette, hierarchy, direction, expand_neighbors, node_attrs)

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

    captions = {
        "Betweenness Centrality": "Node color and size = betweenness centrality.",
        "All Communities": "Nodes colored by community.",
        "Focus on node & neighbors": "Selected node and its direct neighbors only. (Usa il bottone per espandere a 2 salti)",
        "Selected Node's Community": "Only the selected node's community is shown, with chosen palette."
    }
    st.caption(captions[view_mode])

if __name__ == "__main__":
    main()
