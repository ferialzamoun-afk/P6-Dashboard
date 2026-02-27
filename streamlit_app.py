"""
🏪 Dashboard Ventes & Stocks - Application Streamlit Interactive
Conforme au brief : KPIs, Top 20 CA, Analyse stocks, Filtres & Bonus (Pareto, Corrélation)

    # Tableau supplémentaire : articles sans stock et non disponibles web
    st.markdown("### 📋 Articles sans stock et non disponibles web")
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

# ============================================
# CONFIGURATION DE LA PAGE
# ============================================
st.set_page_config(
    page_title="Dashboard Ventes & Stocks",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Fraunces:wght@600;700&family=Manrope:wght@400;500;600&display=swap');

    html, body, [class*="css"] {
        font-family: 'Manrope', sans-serif;
    }
    h1, h2, h3 {
        font-family: 'Fraunces', serif;
        letter-spacing: 0.2px;
    }
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(180deg, #fff8f2 0%, #ffffff 45%, #f6f7fb 100%);
    }
    [data-testid="stSidebar"] {
        background: #f7f3ee;
        border-right: 1px solid #efe6db;
    }
    [data-testid="stMetric"] {
        background: #ffffff;
        border: 1px solid #efe6db;
        border-radius: 10px;
        padding: 10px 12px;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# ============================================
# CHARGEMENT DES DONNÉES
# ============================================

@st.cache_data
def load_data():
    """Charger le fichier df_final.xlsx uniquement"""
    try:
        project_root = Path(__file__).resolve().parent
        data_dir = project_root / 'data'
        # Tableau supplémentaire : articles en surstock (stock > stock moyen global)

        df_path = data_dir / 'df_final.xlsx'
        if not df_path.exists():
            raise FileNotFoundError(f"Fichier introuvable: {df_path}")

        df_final = pd.read_excel(df_path)

        # Normaliser la disponibilite web
        if 'web_disponible' not in df_final.columns:
            if 'onsale_web' in df_final.columns:
                df_final['web_disponible'] = pd.to_numeric(df_final['onsale_web'], errors='coerce').fillna(0).astype(int)
            elif 'id_web' in df_final.columns:
                df_final['web_disponible'] = df_final['id_web'].notna().astype(int)
            else:
                df_final['web_disponible'] = 0

        # Nettoyer les colonnes numériques
        df_final['price'] = pd.to_numeric(df_final.get('price'), errors='coerce').fillna(0)
        df_final['total_sales'] = pd.to_numeric(df_final.get('total_sales'), errors='coerce').fillna(0)
        df_final['purchase_price'] = pd.to_numeric(df_final.get('purchase_price'), errors='coerce').fillna(0)
        df_final['marge_brute'] = pd.to_numeric(df_final.get('marge_brute'), errors='coerce').fillna(0)

        # Calculer CA = prix × total_sales (pour produits web uniquement)
        df_final['ca_par_article'] = df_final['price'] * df_final['total_sales']

        # Calculer ou reutiliser la marge
        if 'taux_marge_pct' in df_final.columns:
            df_final['taux_marge'] = pd.to_numeric(df_final['taux_marge_pct'], errors='coerce')
        else:
            df_final['price_ht'] = df_final['price'] / 1.2
            df_final['taux_marge'] = ((df_final['price_ht'] - df_final['purchase_price']) / df_final['purchase_price'].replace(0, np.nan)) * 100

        return df_final

    except Exception as e:
        st.error(f"❌ Erreur de chargement: {str(e)}")
        return None


def get_analysis_images():
    images_dir = Path(__file__).resolve().parent / 'images'
    image_items = [
        ("Pareto CA", images_dir / 'pareto_ca.png'),
        ("Palmares Quantite", images_dir / 'palmares_quantite.png'),
        ("Pareto Quantite", images_dir / 'pareto_quantite.png'),
        ("Rotation Stock", images_dir / 'stock_rotation_top20.png'),
        ("Rotation par Type", images_dir / 'rotation_par_type.png'),
        ("Histogramme Quantite", images_dir / 'histogramme_quantite_by_product_id_web.png'),
        ("Boxplot Prix", images_dir / 'boxplot_prix.png'),
        ("Distribution Prix", images_dir / 'distribution_prix.png'),
        ("Scatter Stock IPR", images_dir / 'scatter_stock_ipr.png'),
        ("Marge par Type", images_dir / 'marge_par_type.png'),
    ]
    return [(title, path) for title, path in image_items if path.exists()]


def build_pdf_report(kpis, image_items, sections):
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    margin = 2 * cm

    y = height - margin
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(margin, y, "Dashboard Ventes & Stocks")
    y -= 0.8 * cm
    pdf.setFont("Helvetica", 10)
    pdf.drawString(margin, y, f"Synthese automatique - {datetime.now():%Y-%m-%d %H:%M}")

    y -= 1.0 * cm
    pdf.setFont("Helvetica-Bold", 12)
    pdf.drawString(margin, y, "Indicateurs cles")
    y -= 0.6 * cm
    pdf.setFont("Helvetica", 10)
    for label, value in kpis:
        pdf.drawString(margin, y, f"- {label}: {value}")
        y -= 0.45 * cm

    pdf.showPage()

    def draw_sections():
        nonlocal y
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, height - margin, "Synthese produits")
        y = height - margin - 0.8 * cm

        for title, header, rows in sections:
            if y < margin + 3 * cm:
                pdf.showPage()
                y = height - margin
            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(margin, y, title)
            y -= 0.5 * cm
            pdf.setFont("Helvetica", 9)
            if header:
                pdf.drawString(margin, y, header)
                y -= 0.4 * cm
            for row in rows:
                if y < margin + 1.5 * cm:
                    pdf.showPage()
                    y = height - margin
                pdf.drawString(margin, y, row)
                y -= 0.4 * cm
            y -= 0.4 * cm

    if sections:
        draw_sections()
        pdf.showPage()

    for title, path in image_items:
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(margin, height - margin, title)
        if path.exists():
            image = ImageReader(str(path))
            available_w = width - 2 * margin
            available_h = height - 3 * margin
            pdf.drawImage(
                image,
                margin,
                margin,
                width=available_w,
                height=available_h,
                preserveAspectRatio=True,
                anchor='c'
            )
        else:
            pdf.setFont("Helvetica", 10)
            pdf.drawString(margin, height - 2 * margin, "Image manquante")
        pdf.showPage()

    pdf.save()
    buffer.seek(0)
    return buffer

# ============================================
# INTERFACE PRINCIPALE
# ============================================

st.title("📊 Dashboard Ventes & Stocks")
st.markdown("*Analyse des ventes et des stocks en temps reel*")

# Charger les données
df = load_data()

if df is None:
    st.stop()

# ============================================
# SIDEBAR - FILTRES
# ============================================

st.sidebar.header("🧭 Navigation")
page = st.sidebar.selectbox(
    "Aller a",
    ["Dashboard", "Methodologie"],
    index=0
)

if page == "Methodologie":
    st.header("🧪 Methodologie")
    st.markdown(
        """
        **Objectif**
        - Identifier les produits qui tirent le chiffre d'affaires.
        - Detecter les ruptures, les surstocks et les marges faibles.
        - Donner une vision exploitable pour les equipes commerciales et logistiques.

        **Sources de donnees**
        - `df_final.xlsx` : fichier consolide (ERP + Web + Liaison).

        **Preparation**
        - Chargement direct du fichier consolide.
        - Creation de `web_disponible` si absent.
        - Nettoyage des colonnes numeriques et gestion des valeurs manquantes.

        **Indicateurs calcules**
        - CA par article = `price` x `total_sales`.
        - Marge (%) = (prix HT - prix achat) / prix achat.
        - Ruptures = `stock_quantity == 0`.

        **Analyses**
        - Top 10 CA et quantites.
        - Pareto 20/80 sur le CA.
        - Corrélations prix / achat / stock / prix ht/ taux_marge/ ca_par_article.

        **Limites**
        - Le CA est un potentiel (prix x `total_sales`).
        - Les marges extremes peuvent venir de donnees d'achat manquantes.
        """
    )
    st.stop()

st.sidebar.header("🔍 Filtres Interactifs")

# Filtre web_disponible
filtre_web = st.sidebar.radio(
    "Disponibilité Web",
    ["Tous", "Web uniquement", "Non-web uniquement"],
    index=0
)

if filtre_web == "Web uniquement":
    df_filtered = df[df['web_disponible'] == 1].copy()
elif filtre_web == "Non-web uniquement":
    df_filtered = df[df['web_disponible'] == 0].copy()
else:
    df_filtered = df.copy()


# Filtre categorie produits (product_id_web) - toujours toutes les catégories
if 'product_id_web' in df.columns:
    categories_toutes = df['product_id_web'].dropna().unique().tolist()
    if categories_toutes:
        # Par défaut, tout sélectionné
        categories_selectionnees = st.sidebar.multiselect(
            "Categorie produit",
            options=sorted(categories_toutes),
            default=sorted(categories_toutes)
        )
        df_filtered = df_filtered[df_filtered['product_id_web'].isin(categories_selectionnees)]


# Filtre stock_status si disponible
if 'stock_status' in df_filtered.columns:
    statuts_disponibles = df_filtered['stock_status'].dropna().unique().tolist()
    if statuts_disponibles:
        statuts_selectionnes = st.sidebar.multiselect(
            "Statut Stock",
            options=statuts_disponibles,
            default=statuts_disponibles
        )
        df_filtered = df_filtered[df_filtered['stock_status'].isin(statuts_selectionnes)]

# Filtre product_type sous Statut Stock
if 'product_type' in df_filtered.columns:
    types_disponibles = df_filtered['product_type'].dropna().unique().tolist()
    if types_disponibles:
        types_selectionnes = st.sidebar.multiselect(
            "Type de produit",
            options=sorted(types_disponibles),
            default=sorted(types_disponibles)
        )
        df_filtered = df_filtered[df_filtered['product_type'].isin(types_selectionnes)]

# Filtre plage de prix
if df_filtered['price'].max() > 0:
    prix_min = float(df_filtered['price'].min())
    prix_max = float(df_filtered['price'].max())
    if prix_min < prix_max:
        plage_prix = st.sidebar.slider(
            "Plage de prix (€)",
            prix_min, prix_max,
            (prix_min, prix_max)
        )
        df_filtered = df_filtered[(df_filtered['price'] >= plage_prix[0]) & (df_filtered['price'] <= plage_prix[1])]
    else:
        st.sidebar.info(f"Prix unique : {prix_min} €")

st.sidebar.metric("Articles filtrés", f"{len(df_filtered):,}")

# ============================================
# SECTION 1 - KPIs (Priorité ⭐⭐⭐)
# ============================================

def format_eur(value, decimals=0):
    formatted = f"{value:,.{decimals}f}".replace(",", " ")
    return f"{formatted.replace('.', ',')}€"



# KPIs bruts (avant filtrage)
col_brut1, col_brut2 = st.columns(2)
with col_brut1:
    st.metric("Articles totaux (brut)", f"{len(df):,}")
with col_brut2:
    nb_web_brut = df['web_disponible'].sum() if 'web_disponible' in df.columns else 0
    st.metric("Articles web (brut)", f"{int(nb_web_brut):,}")

# KPIs dynamiques selon les filtres appliqués
col_kpi1, col_kpi2 = st.columns(2)
with col_kpi1:
    st.metric("Articles filtrés", f"{len(df_filtered):,}")
with col_kpi2:
    nb_web_filtered = df_filtered['web_disponible'].sum() if 'web_disponible' in df_filtered.columns else 0
    st.metric("Articles web (filtrés)", f"{int(nb_web_filtered):,}")

st.header("📊 Indicateurs Clés (KPIs)")

col1, col2, col3, col4, col5, col6 = st.columns(6)

# KPI 1 : CA Total
ca_total = df_filtered[df_filtered['web_disponible'] == 1]['ca_par_article'].sum()
with col1:
    st.metric(
        label="💰 CA Total Web",
        value=format_eur(ca_total, decimals=0),
        help="Chiffre d'affaires potentiel (prix × total_sales) pour produits web"
    )

# KPI 2 : Nombre de produits
nb_produits = len(df_filtered)
with col2:
    st.metric(
        label="📦 Nombre de Produits",
        value=f"{nb_produits:,}",
        help="Nombre total d'articles après filtres"
    )

# KPI 3 : Marge moyenne
marge_moyenne = df_filtered['taux_marge'].mean()
with col3:
    st.metric(
        label="📈 Marge Moyenne (taux_marge_pct)",
        value=f"{marge_moyenne:.1f}%",
        help="Moyenne de taux_marge_pct. La colonne marge_brute (en €) est aussi disponible dans df_final.xlsx."
    )

# KPI 4 : Marge brute moyenne
marge_brute_moyenne = df_filtered['marge_brute'].mean()
with col4:
    st.metric(
        label="💶 Marge Brute Moyenne",
        value=format_eur(marge_brute_moyenne, decimals=2),
        help="Moyenne de la colonne marge_brute (en €)."
    )

# KPI 5 : Marge brute totale
marge_brute_totale = df_filtered['marge_brute'].sum()
with col5:
    st.metric(
        label="💰 Marge Brute Totale",
        value=format_eur(marge_brute_totale, decimals=0),
        help="Somme de la colonne marge_brute (en €)."
    )

# KPI 6 : Produits en rupture
rupture = len(df_filtered[df_filtered['stock_quantity'] == 0])
with col6:
    st.metric(
        label="⚠️ Produits en Rupture",
        value=f"{rupture:,}",
        delta=f"{(rupture/nb_produits*100):.1f}%" if nb_produits else "0%",
        delta_color="inverse",
        help="Produits avec stock = 0"
    )



# ============================================
# SECTION 2 - TOP 20 CA (Priorité ⭐⭐⭐)
# ============================================

st.header("🏆 Top 20 Articles par CA")

df_web = df_filtered[df_filtered['web_disponible'] == 1].copy()
if len(df_web) > 0:
    images_dir = Path(__file__).resolve().parent / 'images'
    


    # Afficher l'image palmares_ca_top20.png juste sous le Top 20
    palmares_top20_path = images_dir / 'palmares_ca_top20.png'
    if palmares_top20_path.exists():
        st.image(str(palmares_top20_path), use_container_width=True, caption="Palmarès CA Top 20")
    else:
        st.info("Image palmares_ca_top20.png introuvable")
    

    st.header("📊 Analyse de la marge et du CA par produit")
    col_ca, col_marge = st.columns(2)
    image_height = 400
    with col_ca:
        hist_path = images_dir / 'histogramme_ca_by_product_id_web.png'
        st.markdown("<div style='text-align:center; font-weight:600; margin-bottom:8px;'>Distribution du CA par catégorie</div>", unsafe_allow_html=True)
        if hist_path.exists():
            st.markdown(f"<div style='margin-top:40px'></div>", unsafe_allow_html=True)
            st.image(str(hist_path), use_container_width=True, output_format="PNG", width=None)
            st.markdown(f"<style>div[data-testid='column'] img {{height: {image_height}px !important; object-fit: contain;}}</style>", unsafe_allow_html=True)
        else:
            st.info("Image histogramme_ca_by_product_id_web.png introuvable")
    with col_marge:
        marge_path = images_dir / 'marge_par_type.png'
        st.markdown("<div style='text-align:center; font-weight:600; margin-bottom:8px;'>Marge moyenne par type</div>", unsafe_allow_html=True)
        if marge_path.exists():
            st.image(str(marge_path), use_container_width=True, output_format="PNG", width=None)
            st.markdown(f"<style>div[data-testid='column'] img {{height: {image_height}px !important; object-fit: contain;}}</style>", unsafe_allow_html=True)
        else:
            st.info("Image marge_par_type.png introuvable")
    # ============================================
    # SECTION - ANALYSE PARETO (le 20/80)
    # ============================================

    st.header("📊 Analyse Pareto (le 20/80)")
    col_pareto1, col_pareto2 = st.columns(2)
    with col_pareto1:
        pareto_ca_path = images_dir / 'pareto_ca.png'
        if pareto_ca_path.exists():
            st.image(str(pareto_ca_path), use_container_width=True, caption="Courbe de Pareto - CA Cumulé (%)")
        else:
            st.info("Image pareto_ca.png introuvable")
    with col_pareto2:
        pareto_quantite_path = images_dir / 'pareto_quantite.png'
        if pareto_quantite_path.exists():
            st.image(str(pareto_quantite_path), use_container_width=True, caption="Courbe de Pareto - Quantité Cumulée (%)")
        else:
            st.info("Image pareto_quantite.png introuvable")

    # Calcul du nombre d'articles représentant 80% du CA
    if len(df_web) > 0 and 'ca_par_article' in df_web.columns:
        df_pareto = df_web.sort_values('ca_par_article', ascending=False).reset_index(drop=True)
        df_pareto['part_ca_pct'] = (df_pareto['ca_par_article'] / df_pareto['ca_par_article'].sum()) * 100
        df_pareto['cumul_ca_pct'] = df_pareto['part_ca_pct'].cumsum()
        nb_80 = len(df_pareto[df_pareto['cumul_ca_pct'] <= 80])
        st.info(f"💡 {nb_80} articles représentent 80% du chiffre d'affaires web filtré.")
else:
    st.warning("Aucun produit web disponible avec les filtres actuels")

# ============================================
# SECTION 3 - ANALYSE STOCKS (Priorité ⭐⭐)
# ============================================

st.header("📦 Analyse des Stocks")

images_dir = Path(__file__).resolve().parent / 'images'
col_img3, col_img4 = st.columns(2)
with col_img3:
    st.subheader("Gauge IDP")
    gauge_path = images_dir / 'gauge_idp.png'
    if gauge_path.exists():
        st.image(str(gauge_path), use_container_width=True)
    else:
        st.info("Image gauge_idp.png introuvable")
with col_img4:
    st.subheader("Distribution IPR")
    dist_ipr_path = images_dir / 'distribution_ipr.png'
    if dist_ipr_path.exists():
        st.image(str(dist_ipr_path), use_container_width=True)
    else:
        st.info("Image distribution_ipr.png introuvable")

# ============================================
# SECTION BONUS 2 - CORRÉLATION
# ============================================

st.header("🔗 Matrice de Corrélation (Bonus)")


images_dir = Path(__file__).resolve().parent / 'images'
corr_matrix_path = images_dir / 'correlation_matrix.png'
if corr_matrix_path.exists():
    st.image(str(corr_matrix_path), use_container_width=True, caption="Matrice de corrélation")
else:
    st.info("Image correlation_matrix.png introuvable")

# ============================================
# SECTION BONUS 3 - TABLEAU FILTRABLE + EXPORT
# ============================================

st.header("📋 Tableau de Données Filtrable (Bonus)")

if st.checkbox("📊 Afficher les données filtrées"):
    # Créer colonne indicatrice de rupture de stock
    df_filtered['rupture_stock'] = (df_filtered['stock_quantity'] == 0).astype(int)
    
    cols_to_show = [
        'product_id', 'post_name', 'product_id_web', 'sku', 'web_disponible',
        'price', 'purchase_price', 'marge_brute', 'ca_par_article', 'taux_marge',
        'stock_quantity', 'rupture_stock', 'stock_status'
    ]
    cols_disponibles = [c for c in cols_to_show if c in df_filtered.columns]

    display_df = df_filtered[cols_disponibles].head(100).copy()
    currency_cols = [c for c in ['price', 'purchase_price', 'ca_par_article', 'marge_brute'] if c in display_df.columns]
    percent_cols = [c for c in ['taux_marge', 'taux_marge_pct'] if c in display_df.columns]
    style_formats = {col: (lambda v: format_eur(v, decimals=2)) for col in currency_cols}
    style_formats.update({col: (lambda v: f"{v:.1f}%") for col in percent_cols})

    # Fonction pour colorier les lignes en rupture de stock
    def highlight_outofstock(row):
        if row.get('stock_quantity', 1) == 0:
            return ['background-color: #fff3cd'] * len(row)
        return [''] * len(row)

    styled_df = display_df.style.format(style_formats).apply(highlight_outofstock, axis=1)
    st.dataframe(styled_df, width='stretch')
    
    # Export CSV
    csv = df_filtered[cols_disponibles].to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="⬇️ Télécharger CSV (données filtrées)",
        data=csv,
        file_name="bottleneck_export_filtre.csv",
        mime="text/csv"
    )

# ============================================
# SECTION BONUS 4 - ANALYSES VISUELLES (PNG)
# ============================================

st.header("🖼️ Analyses Visuelles (PNG)")
st.caption("Synthese des graphiques generes dans le notebook")

# Graphiques supplémentaires
col1, col2 = st.columns(2)

with col1:
    st.subheader("Répartition par Statut Stock")
    if 'stock_status' in df_filtered.columns:
        status_counts = df_filtered['stock_status'].value_counts()
        fig_pie = px.pie(
            values=status_counts.values,
            names=status_counts.index,
            title="Répartition Stock par Statut",
            hole=0.4  # Donut chart
        )
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("Colonne 'stock_status' non disponible")

with col2:
    st.subheader("Top 10 Articles en Stock")
    df_top_stock = df_filtered.nlargest(10, 'stock_quantity')
    fig_stock = px.bar(
        df_top_stock,
        y='product_id' if 'product_id' in df_top_stock.columns else df_top_stock.index,
        x='stock_quantity',
        orientation='h',
        title='Top 10 Quantités en Stock',
        labels={'stock_quantity': 'Quantité', 'product_id': 'ID Produit'},
        color='stock_quantity',
        color_continuous_scale='Oranges'
    )
    fig_stock.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig_stock, use_container_width=True)

st.divider()

analysis_images = get_analysis_images()
if analysis_images:
    for i in range(0, len(analysis_images), 2):
        cols = st.columns(2)
        for col, item in zip(cols, analysis_images[i:i + 2]):
            title, path = item
            with col:
                st.subheader(title)
                st.image(str(path), use_container_width=True)
else:
    st.info("Aucune image PNG detectee dans le dossier images/")

# ============================================
# SECTION BONUS 5 - EXPORT PDF
# ============================================

st.header("📄 Export PDF (Bonus)")

pdf_kpis = [
    ("CA Total Web", format_eur(ca_total, decimals=0)),
    ("Nombre de Produits", f"{nb_produits:,}"),
    ("Marge Moyenne", f"{marge_moyenne:.1f}%"),
    ("Marge Brute Moyenne", format_eur(marge_brute_moyenne, decimals=2)),
    ("Marge Brute Totale", format_eur(marge_brute_totale, decimals=0)),
    ("Produits en Rupture", f"{rupture:,}"),
]

# Sections detaillees pour le PDF
sections = []

# Produits/categories qui tirent le CA (cumul 30-35% sinon top 20)
driver_rows = []
if 'product_id_web' in df_filtered.columns:
    ca_group = (
        df_filtered.groupby('product_id_web', dropna=True)['ca_par_article']
        .sum()
        .sort_values(ascending=False)
        .reset_index()
    )
    total_ca = ca_group['ca_par_article'].sum()
    if total_ca > 0:
        ca_group['cumul_pct'] = ca_group['ca_par_article'].cumsum() / total_ca * 100
        ca_drivers = ca_group[(ca_group['cumul_pct'] >= 30) & (ca_group['cumul_pct'] <= 35)]
        if ca_drivers.empty:
            ca_drivers = ca_group.head(20)
        else:
            ca_drivers = ca_drivers.head(20)
        for _, row in ca_drivers.iterrows():
            driver_rows.append(
                f"{row['product_id_web']} | CA: {format_eur(row['ca_par_article'], 0)} | Cumul: {row['cumul_pct']:.1f}%"
            )

if driver_rows:
    sections.append((
        "Produits/categories qui tirent le CA",
        "product_id_web | CA | Cumul %",
        driver_rows
    ))

# Ruptures (stock = 0)
rupture_rows = []
rupture_df = df_filtered[df_filtered['stock_quantity'] == 0].copy()
if not rupture_df.empty:
    rupture_df = rupture_df.sort_values('ca_par_article', ascending=False).head(20)
    for _, row in rupture_df.iterrows():
        label = row.get('product_id', row.get('sku', ''))
        rupture_rows.append(
            f"{label} | Stock: 0 | CA: {format_eur(row['ca_par_article'], 0)}"
        )

if rupture_rows:
    sections.append((
        "Ruptures",
        "ID produit | Stock | CA",
        rupture_rows
    ))


# Marges faibles (taux_marge <= 35%)
marge_rows = []
marge_df = df_filtered[df_filtered['taux_marge'] <= 35].copy()
if not marge_df.empty:
    marge_df = marge_df.sort_values('taux_marge', ascending=True).head(20)
    for _, row in marge_df.iterrows():
        label = row.get('product_id', row.get('sku', ''))
        marge_rows.append(
            f"{label} | Marge: {row['taux_marge']:.1f}% | CA: {format_eur(row['ca_par_article'], 0)}"
        )

if marge_rows:
    sections.append((
        "Marges faibles (<= 35%)",
        "ID produit | Marge | CA",
        marge_rows
    ))

pdf_buffer = build_pdf_report(pdf_kpis, analysis_images, sections)
st.download_button(
    label="📥 Telecharger le rapport PDF",
    data=pdf_buffer,
    file_name="dashboard_ventes_stocks.pdf",
    mime="application/pdf"
)

# ============================================
# FOOTER
# ============================================

st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 12px;'>
    🏪 Dashboard Ventes & Stocks | Conforme au brief projet | 
    <a href='https://github.com' target='_blank'>GitHub</a>
    </div>
    """,
    unsafe_allow_html=True
)
