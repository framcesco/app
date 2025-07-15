import streamlit as st
import pandas as pd
from streamlit_vis_network import vis_network

# Carica il tuo DataFrame come già fai
df = load_data(DATA_FILE, PARENT_COL, CHILD_COL)

# Costruzione lista nodi e archi in formato streamlit-vis-network
all_nodes = pd.unique(df[[PARENT_COL, CHILD_COL]].values.ravel("K"))
nodes = []
for n in all_nodes:
    # Tooltip dettagliato con attributi (puoi personalizzare)
    attr = df[df[PARENT_COL]==n].to_dict("records") + df[df[CHILD_COL]==n].to_dict("records")
    tooltip = "<br>".join([f"{k}: {v}" for d in attr for k,v in d.items() if pd.notnull(v)])
    nodes.append({"id": n, "label": n, "title": tooltip if tooltip else n})

edges = [
    {"from": row[PARENT_COL], "to": row[CHILD_COL]}
    for _, row in df.iterrows()
]

# Visualizzazione grafo interattivo
res = vis_network(
    nodes=nodes,
    edges=edges,
    options={"height": "600px"},
    key="visgraph"
)

st.markdown("**Clicca un nodo per vedere dettagli e lanciare analisi**")

# Analisi/azioni sul nodo selezionato!
if res["last_clicked_node"]:
    selected = res["last_clicked_node"]
    st.success(f"Hai selezionato il nodo: **{selected}**")
    # Attributi del nodo dal DataFrame:
    node_data = df[(df[PARENT_COL]==selected) | (df[CHILD_COL]==selected)]
    st.write("Dati associati:")
    st.dataframe(node_data)
    # Qui puoi lanciare la tua funzione di analisi sul tronco selezionato
    # ad esempio: visualizzare sottografo, lanciare metriche, ecc...
else:
    st.info("Clicca un nodo nella rete per mostrare dettagli.")

# NB: vis_network supporta anche il drag & drop e i tooltip al volo!

