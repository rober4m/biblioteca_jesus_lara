import pandas as pd
import streamlit as st
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

# Paths
root = Path(__file__).resolve().parent
logo = root /'src'/'img'/'escudos-color-horizontal-02.png'
# Main 
st.image(logo, width=300)  
st.title('Biblioteca Municipal Jesús Lara')
st.markdown('Catálogo en línea · busca por autor o título 📚')

# st.set_page_config(page_title="Biblioteca Jesús Lara", page_icon="📚", layout="wide")

# st.markdown("# 📚 Biblioteca Jesús Lara")
# st.caption("Catálogo en línea · busca por autor o título")

# Sidebar head
# st.sidebar.image('src/img/escudos-color-horizontal-02.png', width=200)   
# st.sidebar.title('Buscador de libros')

# Functions
@st.cache_data(persist=True)
def load_data():
    df = pd.read_csv('src/data/books_jl_processed_cc.csv')
    # Normalize once (cached), not on every keystroke.
    df.columns = df.columns.str.strip().str.lower()
    df["_autor"] = df["autor"].map(normalize)
    df["_titulo"] = df["titulo"].map(normalize)
    return df

def normalize(text):
    """lowercase, strip accents, collapse spaces: 'García  Márquez' -> 'garcia marquez'"""
    text = unicodedata.normalize("NFKD", str(text))
    text = "".join(c for c in text if not unicodedata.combining(c))
    return " ".join(text.lower().split())

def search(df, field, query, fuzzy=True, cutoff=0.8):
    q = normalize(query)
    if not q:
        return df.iloc[0:0]
    words = q.split()
    key = df[f"_{field}"]

    # 1) every word must appear, in any order
    match = key.map(lambda t: all(w in t for w in words))
    if match.any() or not fuzzy:
        hits = df[match].copy()
        hits["_score"] = key[match].str.startswith(words[0]).astype(int)  # starts-with first
        return hits.sort_values("_score", ascending=False)

    # 2) nothing found -> tolerate typos
    def score(t):
        tw = t.split()
        if not tw:
            return 0
        return min(max(SequenceMatcher(None, w, x).ratio() for x in tw) for w in words)

    s = key.map(score)
    return df[s >= cutoff].assign(_score=s[s >= cutoff]).sort_values("_score", ascending=False)

@st.cache_resource
def get_client():
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])

def increment_visits():
    try:
        res = get_client().rpc("increment_counter", {"counter_name": "visits"}).execute()
        return int(res.data)
    except Exception:
        return None
# Counter functions
try:
    from supabase import create_client
except ImportError:
    create_client = None
import json
import urllib.error
import urllib.request
def increment_visits():
    """Add 1 to the 'visits' counter in Supabase and return the new total (None if it fails)."""
    try:
        url = st.secrets["SUPABASE_URL"].rstrip("/")
        key = st.secrets["SUPABASE_KEY"]
        headers = {"apikey": key, "Content-Type": "application/json"}
        if key.startswith("eyJ"):                      # older JWT-style keys also go in Authorization
            headers["Authorization"] = f"Bearer {key}"
        req = urllib.request.Request(
            f"{url}/rest/v1/rpc/increment_counter",
            data=json.dumps({"counter_name": "visits"}).encode(),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            return int(json.loads(r.read()))
    except urllib.error.HTTPError as e:
        st.session_state["counter_error"] = f"HTTP {e.code}: {e.read().decode()[:150]}"
    except Exception as e:
        st.session_state["counter_error"] = f"{type(e).__name__}: {e}"
    return None

### App funcionalities
# search by
field = st.radio('Buscar por:', ('Autor', 'Titulo'),  horizontal=True, label_visibility='collapsed')
query = st.text_input("Buscar: ", key="query", placeholder=f"{field} ")
st.button('Buscar', key='buscar')

books = load_data()
results = search(books, field.lower(), query)

# Show results
SHOW = ["autor", "titulo", "c", "dewey", "cutter"]   
# st.caption(f"{len(results)} resultados")

# st.table(results[SHOW].rename(columns=str.capitalize).reset_index(drop=True))
if not query.strip():
    st.info("Escribe un autor o título para buscar.")
else:
    shown = len(results)
    st.caption(f"{shown} resultados" + (" (mostrando los primeros 200)" if shown == 200 else ""))
    st.table(results[SHOW].rename(columns=str.capitalize).reset_index(drop=True))

# Counter
if "counter_tried" not in st.session_state:
    st.session_state.counter_tried = True
    st.session_state.total = increment_visits()

if st.session_state.get("total") is not None:
    st.caption(f"Visitas totales: {st.session_state.total:,}")
elif "counter_error" in st.session_state:
    st.caption(f"Contador no disponible: {st.session_state['counter_error']}")

# Footnotes
st.divider()
st.markdown("Developed by [Rober Mamani](https://robermamani.com)")
