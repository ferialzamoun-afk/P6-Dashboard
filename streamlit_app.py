"""
🍷 Dashboard BottleNeck - Application Streamlit Interactive
Conforme au brief : KPIs, Top 10 CA, Analyse stocks, Filtres & Bonus (Pareto, Corrélation)
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

# ============================================
# CONFIGURATION DE LA PAGE
# ============================================
st.set_page_config(
    page_title="Dashboard Ventes & Stocks",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# CHARGEMENT DES DONNÉES
# ============================================

@st.cache_data
def load_data():
    """Charger et fusionner les données ERP + Web + Liaison"""
    try:
        project_root = Path.cwd()
        data_dir = project_root / 'data'
        
        # Charger les 3 fichiers
        df_erp = pd.read_excel(data_dir / 'erp.xlsx')
        df_web = pd.read_excel(data_dir / 'web.xlsx')
        df_liaison = pd.read_excel(data_dir / 'liaison.xlsx')
        
        # Fusion : ERP + Liaison + Web
        df_merged = df_erp.merge(df_liaison, on='product_id', how='left')
        df_final = df_merged.merge(df_web, left_on='id_web', right_on='sku', how='left', suffixes=('', '_web'))
        
        # Créer colonne web_disponible (1 si présent dans web, 0 sinon)
        df_final['web_disponible'] = df_final['id_web'].notna().astype(int)
        
        # Nettoyer les colonnes numériques
        df_final['price'] = pd.to_numeric(df_final['price'], errors='coerce').fillna(0)
        df_final['stock_quantity'] = pd.to_numeric(df_final['stock_quantity'], errors='coerce').fillna(0)
        df_final['purchase_price'] = pd.to_numeric(df_final['purchase_price'], errors='coerce').fillna(0)
        
        # Calculer CA = prix × stock (pour produits web uniquement)
        df_final['ca_par_article'] = df_final['price'] * df_final['stock_quantity']
        
        # Calculer marge
        df_final['price_ht'] = df_final['price'] / 1.2
        df_final['taux_marge'] = ((df_final['price_ht'] - df_final['purchase_price']) / df_final['purchase_price'].replace(0, np.nan)) * 100
        
        return df_final
        
    except Exception as e:
        st.error(f"❌ Erreur de chargement: {str(e)}")
        return None

# ============================================
# INTERFACE PRINCIPALE
# ============================================

st.title("📊 Dashboard Ventes & Stocks")
st.markdown("*Analyse des ventes et des stocks en temps réel*")

# Charger les données
df = load_data()

if df is None:
    st.stop()

# ============================================
# SIDEBAR - FILTRES
# ============================================

st.sidebar.header("🔍 Filtres Interactifs")

# Filtre web_disponible
filtre_web = st.sidebar.radio(
    "Disponibilité Web",
    ["Tous", "Web uniquement", "Non-web uniquement"],
    index=1
)

if filtre_web == "Web uniquement":
    df_filtered = df[df['web_disponible'] == 1].copy()
elif filtre_web == "Non-web uniquement":
    df_filtered = df[df['web_disponible'] == 0].copy()
else:
    df_filtered = df.copy()

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

# Filtre plage de prix
if df_filtered['price'].max() > 0:
    prix_min = float(df_filtered['price'].min())
    prix_max = float(df_filtered['price'].max())
    plage_prix = st.sidebar.slider(
        "Plage de prix (€)",
        prix_min, prix_max,
        (prix_min, prix_max)
    )
    df_filtered = df_filtered[(df_filtered['price'] >= plage_prix[0]) & (df_filtered['price'] <= plage_prix[1])]

st.sidebar.metric("Articles filtrés", f"{len(df_filtered):,}")

# ============================================
# SECTION 1 - KPIs (Priorité ⭐⭐⭐)
# ============================================

st.header("📊 Indicateurs Clés (KPIs)")

col1, col2, col3, col4 = st.columns(4)

# KPI 1 : CA Total
ca_total = df_filtered[df_filtered['web_disponible'] == 1]['ca_par_article'].sum()
with col1:
    st.metric(
        label="💰 CA Total Web",
        value=f"{ca_total:,.0f}€",
        help="Chiffre d'affaires potentiel (prix × stock) pour produits web"
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
        label="📈 Marge Moyenne",
        value=f"{marge_moyenne:.1f}%",
        help="Taux de marge moyen : (prix HT - prix achat) / prix achat"
    )

# KPI 4 : Produits en rupture
rupture = len(df_filtered[df_filtered['stock_quantity'] == 0])
with col4:
    st.metric(
        label="⚠️ Produits en Rupture",
        value=f"{rupture:,}",
        delta=f"{rupture/nb_produits*100:.1f}%",
        delta_color="inverse",
        help="Produits avec stock = 0"
    )

# ============================================
# SECTION 2 - TOP 10 CA (Priorité ⭐⭐⭐)
# ============================================

st.header("🏆 Top 10 Articles par CA")

df_web = df_filtered[df_filtered['web_disponible'] == 1].copy()
if len(df_web) > 0:
    df_top10 = df_web.nlargest(10, 'ca_par_article')
    
    fig_top10 = px.bar(
        df_top10,
        y='product_id' if 'product_id' in df_top10.columns else df_top10.index,
        x='ca_par_article',
        orientation='h',
        title='Top 10 Produits par Chiffre d\'Affaires',
        labels={'ca_par_article': 'CA (€)', 'product_id': 'ID Produit'},
        text='ca_par_article',
        color='ca_par_article',
        color_continuous_scale='Viridis'
    )
    fig_top10.update_traces(texttemplate='%{text:,.0f}€', textposition='outside')
    fig_top10.update_layout(height=400, showlegend=False)
    
    st.plotly_chart(fig_top10, use_container_width=True)
else:
    st.warning("Aucun produit web disponible avec les filtres actuels")

# ============================================
# SECTION 3 - ANALYSE STOCKS (Priorité ⭐⭐)
# ============================================

st.header("📦 Analyse des Stocks")

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

# ============================================
# SECTION BONUS 1 - COURBE PARETO
# ============================================

st.header("📈 Analyse Pareto 20/80 (Bonus)")

if len(df_web) > 0:
    df_pareto = df_web.sort_values('ca_par_article', ascending=False).reset_index(drop=True)
    df_pareto['part_ca_pct'] = (df_pareto['ca_par_article'] / df_pareto['ca_par_article'].sum()) * 100
    df_pareto['cumul_ca_pct'] = df_pareto['part_ca_pct'].cumsum()
    
    fig_pareto = px.bar(
        df_pareto.head(30),
        x=df_pareto.head(30).index,
        y='cumul_ca_pct',
        title='Courbe de Pareto - CA Cumulé (%)',
        labels={'x': 'Classement Produits', 'cumul_ca_pct': 'CA Cumulé (%)'},
        color='cumul_ca_pct',
        color_continuous_scale='RdYlGn_r'
    )
    fig_pareto.add_hline(y=80, line_dash='dash', line_color='red', annotation_text='Seuil 80%')
    fig_pareto.update_layout(height=400)
    
    st.plotly_chart(fig_pareto, use_container_width=True)
    
    nb_80 = len(df_pareto[df_pareto['cumul_ca_pct'] <= 80])
    st.info(f"💡 **{nb_80} articles** ({nb_80/len(df_web)*100:.1f}%) génèrent 80% du CA")

# ============================================
# SECTION BONUS 2 - CORRÉLATION
# ============================================

st.header("🔗 Matrice de Corrélation (Bonus)")

corr_cols = ['price', 'purchase_price', 'stock_quantity']
available_cols = [c for c in corr_cols if c in df_filtered.columns]

if len(available_cols) >= 2:
    corr_df = df_filtered[available_cols].copy()
    for col in available_cols:
        corr_df[col] = pd.to_numeric(corr_df[col], errors='coerce')
    corr_df = corr_df.dropna()
    
    if len(corr_df) > 1:
        corr_matrix = corr_df.corr()
        
        fig_corr = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale='RdBu',
            zmid=0, zmin=-1, zmax=1,
            text=corr_matrix.values.round(2),
            texttemplate='%{text}',
            textfont={"size": 14},
            colorbar=dict(title="Corrélation")
        ))
        fig_corr.update_layout(
            title="Corrélation entre Prix, Prix Achat et Stock",
            height=400
        )
        st.plotly_chart(fig_corr, use_container_width=True)

# ============================================
# SECTION BONUS 3 - TABLEAU FILTRABLE + EXPORT
# ============================================

st.header("📋 Tableau de Données Filtrable (Bonus)")

if st.checkbox("📊 Afficher les données filtrées"):
    cols_to_show = ['product_id', 'sku', 'price', 'stock_quantity', 'ca_par_article', 
                    'web_disponible', 'taux_marge', 'stock_status']
    cols_disponibles = [c for c in cols_to_show if c in df_filtered.columns]
    
    st.dataframe(df_filtered[cols_disponibles].head(100), use_container_width=True)
    
    # Export CSV
    csv = df_filtered[cols_disponibles].to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="⬇️ Télécharger CSV (données filtrées)",
        data=csv,
        file_name="bottleneck_export_filtre.csv",
        mime="text/csv"
    )

# ============================================
# FOOTER
# ============================================

st.divider()
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 12px;'>
    🍷 Dashboard BottleNeck | Conforme au brief projet | 
    <a href='https://github.com' target='_blank'>GitHub</a>
    </div>
    """,
    unsafe_allow_html=True
)
