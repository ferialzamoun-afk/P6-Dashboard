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
from typing import Optional, Tuple
import shutil
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas


def build_quality_reporting(df_source: pd.DataFrame):
    """Build quality reporting tables and optional Pandera validation results."""
    report = {}
    cols_base = [c for c in ['product_id', 'post_name', 'sku', 'id_web', 'price', 'purchase_price', 'web_disponible'] if c in df_source.columns]

    if 'price' in df_source.columns:
        report['prix_negatifs'] = df_source[df_source['price'] < 0][cols_base].copy()
    else:
        report['prix_negatifs'] = pd.DataFrame()

    if 'purchase_price' in df_source.columns:
        report['prix_achat_negatifs'] = df_source[df_source['purchase_price'] < 0][cols_base].copy()
    else:
        report['prix_achat_negatifs'] = pd.DataFrame()

    if 'sku' in df_source.columns:
        sku_clean = df_source['sku'].fillna('').astype(str).str.strip()
        report['sku_manquants'] = df_source[sku_clean.eq('')][cols_base].copy()
        report['sku_doublons'] = df_source[sku_clean.ne('') & sku_clean.duplicated(keep=False)][cols_base].copy()
    else:
        report['sku_manquants'] = pd.DataFrame()
        report['sku_doublons'] = pd.DataFrame()

    if {'web_disponible', 'id_web'}.issubset(df_source.columns):
        report['id_web_manquants'] = df_source[(df_source['web_disponible'] == 1) & (df_source['id_web'].isna())][cols_base].copy()
    elif 'id_web' in df_source.columns:
        report['id_web_manquants'] = df_source[df_source['id_web'].isna()][cols_base].copy()
    else:
        report['id_web_manquants'] = pd.DataFrame()

    # Validation Pandera (si dispo)
    report['pandera_enabled'] = False
    report['pandera_ok'] = False
    report['pandera_failure_cases'] = pd.DataFrame()
    report['pandera_violations'] = 0
    report['pandera_message'] = ''

    try:
        import pandera.pandas as pa
        from pandera import Check
        from pandera.errors import SchemaErrors

        schema_cols = {}
        if 'price' in df_source.columns:
            schema_cols['price'] = pa.Column(float, Check.ge(0), nullable=True, coerce=True)
        if 'purchase_price' in df_source.columns:
            schema_cols['purchase_price'] = pa.Column(float, Check.ge(0), nullable=True, coerce=True)
        if 'sku' in df_source.columns:
            schema_cols['sku'] = pa.Column(
                object,
                Check(lambda s: s.fillna('').astype(str).str.strip().ne(''), element_wise=False),
                nullable=False,
                coerce=True,
            )

        schema_checks = []
        if {'web_disponible', 'id_web'}.issubset(df_source.columns):
            schema_checks.append(
                Check(
                    lambda d: d.loc[d['web_disponible'] == 1, 'id_web'].notna().all(),
                    element_wise=False,
                    error='id_web manquant pour web_disponible=1',
                )
            )

        schema = pa.DataFrameSchema(schema_cols, checks=schema_checks, strict=False)
        report['pandera_enabled'] = True

        try:
            schema.validate(df_source.copy(), lazy=True)
            report['pandera_ok'] = True
            report['pandera_message'] = 'Validation Pandera OK (aucune violation de regles definies).'
        except SchemaErrors as exc:
            report['pandera_ok'] = False
            report['pandera_failure_cases'] = exc.failure_cases.copy() if hasattr(exc, 'failure_cases') else pd.DataFrame()
            report['pandera_violations'] = int(len(report['pandera_failure_cases'])) if not report['pandera_failure_cases'].empty else 1
            report['pandera_message'] = 'Validation Pandera KO: violations detectees.'
    except Exception as exc:
        report['pandera_message'] = f'Pandera indisponible ou schema non executable: {exc}'

    return report


@st.cache_data
def load_quality_exports_from_notebook():
    """Load quality reporting exports (local dashboard copy first, then notebook source)."""
    project_root = Path(__file__).resolve().parent

    candidate_dirs = [
        project_root / 'data' / 'quality_reporting',
        project_root.parent / 'P13' / 'Partie_1' / 'P6_ameliore_IA' / 'notebooks' / 'output' / 'quality_reporting',
    ]

    src_dir = next((d for d in candidate_dirs if d.exists()), None)
    if src_dir is None:
        return None, None

    mapping = {
        'prix_negatifs': 'erp_price_negatifs.csv',
        'sku_manquants': 'web_sku_manquants.csv',
        'sku_doublons': 'web_sku_doublons.csv',
        'id_web_manquants': 'liaison_id_web_manquants.csv',
        'summary': 'reporting_qualite_summary.csv',
    }

    loaded = {}
    for key, filename in mapping.items():
        path = src_dir / filename
        loaded[key] = pd.read_csv(path) if path.exists() else pd.DataFrame()

    return loaded, src_dir


def sync_quality_exports_to_dashboard():
    """Copy notebook quality reporting exports into dashboard local data folder."""
    project_root = Path(__file__).resolve().parent
    src_dir = project_root.parent / 'P13' / 'Partie_1' / 'P6_ameliore_IA' / 'notebooks' / 'output' / 'quality_reporting'
    dst_dir = project_root / 'data' / 'quality_reporting'
    dst_dir.mkdir(parents=True, exist_ok=True)

    files_to_sync = [
        'erp_price_negatifs.csv',
        'erp_purchase_price_negatifs.csv',
        'erp_stock_negatifs.csv',
        'web_sku_manquants.csv',
        'web_sku_doublons.csv',
        'web_price_negatifs.csv',
        'liaison_id_web_manquants.csv',
        'final_id_web_manquants_web1.csv',
        'reporting_qualite_summary.csv',
    ]

    if not src_dir.exists():
        return 0, files_to_sync, src_dir, dst_dir

    copied = 0
    missing = []
    for filename in files_to_sync:
        src_file = src_dir / filename
        dst_file = dst_dir / filename
        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            copied += 1
        else:
            missing.append(filename)

    return copied, missing, src_dir, dst_dir


@st.cache_data
def load_project_watch_markdown() -> Tuple[Optional[str], Optional[Path]]:
    """Load project watch markdown from known portfolio locations."""
    project_root = Path(__file__).resolve().parent
    candidates = [
        project_root.parent / 'MON-PORTFOLIO-DATA' / 'projets' / 'P13_portfolio' / 'Partie1-Amélioration_P6_IA' / '01_veille_metier_technologique.md',
        project_root.parent / 'P13' / 'Partie_1' / 'P6_ameliore_IA' / 'docs' / '02_veille_technologique_P13_partie_1.md',
    ]

    for path in candidates:
        if path.exists():
            text = path.read_text(encoding='utf-8')
            if text.startswith('---'):
                parts = text.split('---', 2)
                if len(parts) == 3:
                    text = parts[2].lstrip()
            return text, path

    return None, None

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


@st.cache_data
def load_bc05_exports():
    """Charger les exports BC05 depuis le dashboard ou le dossier notebook P13."""
    project_root = Path(__file__).resolve().parent
    candidate_dirs = [
        project_root / 'data',
        project_root.parent / 'P13' / 'Partie_1' / 'P6_ameliore_IA' / 'notebooks' / 'output',
    ]

    selected_dir = next((d for d in candidate_dirs if d.exists()), None)
    if selected_dir is None:
        return None, None, None, None

    summary_path = selected_dir / 'bc05_anomalies_summary.csv'
    actions_path = selected_dir / 'bc05_alertes_actionnables.csv'
    iforest_path = selected_dir / 'bc05_iforest_alerts.csv'

    bc05_summary = pd.read_csv(summary_path) if summary_path.exists() else None
    bc05_actions = pd.read_csv(actions_path) if actions_path.exists() else None
    bc05_iforest = pd.read_csv(iforest_path) if iforest_path.exists() else None
    return bc05_summary, bc05_actions, bc05_iforest, selected_dir


@st.cache_data
def load_bc05_decision_matrix():
    """Load IA decision matrix generated in notebook 9.2bis if available."""
    project_root = Path(__file__).resolve().parent
    candidate_files = [
        project_root / 'data' / 'bc05_matrice_decisionnelle.csv',
        project_root.parent / 'P13' / 'Partie_1' / 'P6_ameliore_IA' / 'notebooks' / 'output' / 'bc05_matrice_decisionnelle.csv',
    ]
    for path in candidate_files:
        if path.exists():
            try:
                return pd.read_csv(path), path
            except Exception:
                continue
    return None, None


def get_bc05_visuals(selected_dir):
    """Return available BC05 PNG visuals generated by the notebook."""
    if selected_dir is None:
        return []

    visuals = [
        ("Heatmap correlations (IF)", selected_dir / 'bc05_iforest_corr_heatmap.png'),
        ("Scatter anomalies (IF)", selected_dir / 'bc05_iforest_scatter_anomalies.png'),
        ("SHAP summary (IF)", selected_dir / 'bc05_iforest_shap_summary.png'),
        ("Scatter K-Means", selected_dir / 'bc05_kmeans_scatter.png'),
        ("Scatter kNN", selected_dir / 'bc05_knn_scatter.png'),
    ]
    return [(title, path) for title, path in visuals if path.exists()]


def build_bc05_decision_table(df_source, bc05_actions, bc05_iforest):
    """Transformer les alertes BC05 en recommandations métier actionnables."""
    if bc05_actions is None or bc05_actions.empty:
        return pd.DataFrame()

    # Seuils de priorisation metier ajustables
    bc05_margin_low_threshold = 25
    bc05_rupture_sales_critical_threshold = 3
    bc05_ca_critical_threshold = 400

    decisions = bc05_actions.copy()

    # Harmoniser l'identifiant produit
    id_candidates = ['product_id', 'id', 'sku']
    id_col = next((c for c in id_candidates if c in decisions.columns), decisions.columns[0])
    decisions = decisions.rename(columns={id_col: 'product_id_ref'})

    join_cols = ['product_id', 'total_sales', 'price', 'stock_quantity', 'taux_marge', 'marge_brute', 'ca_par_article', 'web_disponible']
    available_join_cols = [c for c in join_cols if c in df_source.columns]
    if 'product_id' in available_join_cols:
        decisions = decisions.merge(
            df_source[available_join_cols].drop_duplicates(subset=['product_id']),
            left_on='product_id_ref',
            right_on='product_id',
            how='left',
        )

    decisions['bc05_anomaly_count'] = pd.to_numeric(decisions.get('bc05_anomaly_count', 0), errors='coerce').fillna(0)

    if bc05_iforest is not None and not bc05_iforest.empty:
        if_id_candidates = ['product_id', 'id', 'sku']
        if_id_col = next((c for c in if_id_candidates if c in bc05_iforest.columns), bc05_iforest.columns[0])
        if_flags = bc05_iforest[[if_id_col]].copy()
        if_flags['iforest_flag'] = True
        if_flags = if_flags.rename(columns={if_id_col: 'product_id_ref'})
        decisions = decisions.merge(if_flags, on='product_id_ref', how='left')
    else:
        decisions['iforest_flag'] = False

    decisions['iforest_flag'] = decisions['iforest_flag'].fillna(False)

    def classify_priority(row):
        stock = pd.to_numeric(row.get('stock_quantity', np.nan), errors='coerce')
        sales = pd.to_numeric(row.get('total_sales', np.nan), errors='coerce')
        price = pd.to_numeric(row.get('price', np.nan), errors='coerce')
        margin = pd.to_numeric(row.get('taux_marge', np.nan), errors='coerce')
        ca_article = pd.to_numeric(row.get('ca_par_article', np.nan), errors='coerce')
        anomaly_count = row.get('bc05_anomaly_count', 0)
        iforest_flag = bool(row.get('iforest_flag', False))

        if (price <= 0):
            return 'Critique'
        if (stock == 0 and sales >= bc05_rupture_sales_critical_threshold):
            return 'Critique'
        if (anomaly_count >= 3 and ca_article >= bc05_ca_critical_threshold):
            return 'Critique'
        if iforest_flag or (anomaly_count >= 2) or (margin < bc05_margin_low_threshold) or (stock == 0 and sales > 0):
            return 'Elevee'
        return 'Moyenne'

    def decision_reason(row):
        stock = pd.to_numeric(row.get('stock_quantity', np.nan), errors='coerce')
        sales = pd.to_numeric(row.get('total_sales', np.nan), errors='coerce')
        price = pd.to_numeric(row.get('price', np.nan), errors='coerce')
        margin = pd.to_numeric(row.get('taux_marge', np.nan), errors='coerce')
        ca_article = pd.to_numeric(row.get('ca_par_article', np.nan), errors='coerce')
        anomaly_count = row.get('bc05_anomaly_count', 0)
        iforest_flag = bool(row.get('iforest_flag', False))

        if price <= 0:
            return 'Prix invalide (<= 0)'
        if stock == 0 and sales >= bc05_rupture_sales_critical_threshold:
            return f'Rupture avec demande ({int(sales)} ventes)'
        if anomaly_count >= 3 and ca_article >= bc05_ca_critical_threshold:
            return f'Signal fort + impact CA (>= {bc05_ca_critical_threshold} EUR)'
        if iforest_flag:
            return 'Atypie multivariee (Isolation Forest)'
        if margin < bc05_margin_low_threshold:
            return f'Marge faible (< {bc05_margin_low_threshold}%)'
        if anomaly_count >= 2:
            return 'Multi-alertes statistiques'
        return 'Signal modere a surveiller'

    def action_recommandee(row):
        stock = pd.to_numeric(row.get('stock_quantity', np.nan), errors='coerce')
        sales = pd.to_numeric(row.get('total_sales', np.nan), errors='coerce')
        price = pd.to_numeric(row.get('price', np.nan), errors='coerce')
        margin = pd.to_numeric(row.get('taux_marge', np.nan), errors='coerce')
        if price <= 0:
            return 'Corriger le prix en ERP avant diffusion web'
        if stock == 0 and sales >= bc05_rupture_sales_critical_threshold:
            return 'Reapprovisionnement prioritaire ou suspension marketing'
        if margin < bc05_margin_low_threshold:
            return 'Reviser prix de vente / cout d\'achat avec equipe commerciale'
        if bool(row.get('iforest_flag', False)):
            return 'Audit fiche produit (cas atypique multivarie)'
        return 'Controle metier standard et suivi hebdomadaire'

    def owner(row):
        action = action_recommandee(row)
        if 'prix' in action or 'ERP' in action:
            return 'Data steward'
        if 'Reapprovisionnement' in action:
            return 'Logistique'
        if 'commerciale' in action:
            return 'Achats/Commercial'
        return 'Data + Metier'

    decisions['priorite'] = decisions.apply(classify_priority, axis=1)
    decisions['motif_decision'] = decisions.apply(decision_reason, axis=1)
    decisions['action_recommandee'] = decisions.apply(action_recommandee, axis=1)
    decisions['responsable'] = decisions.apply(owner, axis=1)
    decisions['delai_cible'] = decisions['priorite'].map({
        'Critique': '24-48h',
        'Elevee': 'Semaine en cours',
        'Moyenne': 'Prochain cycle hebdo',
    })

    display_cols = [
        'product_id_ref', 'priorite', 'bc05_anomaly_count', 'iforest_flag',
        'price', 'stock_quantity', 'total_sales', 'taux_marge', 'ca_par_article',
        'motif_decision',
        'action_recommandee', 'responsable', 'delai_cible'
    ]
    display_cols = [c for c in display_cols if c in decisions.columns]
    return decisions[display_cols].sort_values(
        by=['priorite', 'bc05_anomaly_count'],
        ascending=[True, False],
        key=lambda s: s.map({'Critique': 0, 'Elevee': 1, 'Moyenne': 2}) if s.name == 'priorite' else s,
    )


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

bc05_summary, bc05_actions, bc05_iforest, bc05_dir = load_bc05_exports()
bc05_decision_matrix, bc05_decision_path = load_bc05_decision_matrix()

# ============================================
# SIDEBAR - FILTRES
# ============================================

st.sidebar.header("🧭 Navigation")
page = st.sidebar.selectbox(
    "Aller a",
    ["Chiffres cles", "Tableau de bord decisionnel", "Reporting qualite", "Veille metier & techno", "Methodologie"],
    index=0
)

if page == "Veille metier & techno":
    st.header("🧭 Veille metier et technologique du projet")
    st.markdown(
        "<span style='display:inline-block; padding:4px 10px; border-radius:999px; background:#E8F5E9; color:#1B5E20; font-weight:600; font-size:0.85rem;'>Amelioration IA</span>",
        unsafe_allow_html=True,
    )
    st.caption("Lecture metier des choix technologiques utilises pour la qualite, la detection et la priorisation.")

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Qualite", "Pandera + regles metier")
    with c2:
        st.metric("Detection", "Z-score/IQR + Isolation Forest")
    with c3:
        st.metric("Priorisation", "SHAP + K-Means + kNN")

    watch_md, watch_path = load_project_watch_markdown()
    if watch_md:
        st.caption(f"Source: {watch_path.name}")
        st.markdown(watch_md)
    else:
        st.info("Document de veille non trouve. La synthese metier ci-dessus reste disponible.")
    st.stop()

if page == "Methodologie":
    st.header("🧪 Methodologie")
    st.markdown(
        """
        **Finalite metier**
        - Prioriser les produits a traiter en premier selon risque data + impact business.
        - Rendre les decisions actionnables pour les equipes commerce, pricing et logistique.

        **Source unique de reference**
        - df_final.xlsx (consolidation ERP + Web + table de liaison).

        **Etape 1 - Fiabilisation de la donnee**
        - Controles de qualite (prix, SKU, id web, coherence de structure).
        - Validation de schema avec Pandera, restituee en mode metier (sans surcharge technique).

        **Etape 2 - Detection IA multi-signaux**
        - Isolation Forest: atypie globale des produits.
        - kNN: rarete locale dans le voisinage.
        - K-Means: distance au centroide et risque du cluster.
        - SHAP: explicabilite des facteurs dominants.

        **Etape 3 - Scoring decisionnel calibre**
        - Score final = 0.30 IF + 0.20 kNN + 0.15 K-Means + 0.10 SHAP + 0.25 impact business.
        - Seuils dynamiques calibres sur la distribution des scores.
        - Seuils operationnels utilises: Critique >= 0.65, A surveiller >= 0.45.

        **Etape 4 - Priorisation et passage a l'action**
        - Critique: action sous 24-48h.
        - A surveiller: pilotage hebdomadaire.
        - Normal: suivi standard.
        - Regle de surclassement metier: anomalie forte combinee a marge degradee ou risque de rupture.

        **Livrables produits**
        - Matrice decisionnelle complete (score + priorite + lecture strategique).
        - Extrait critique/surveillance pour les comites de decision.
        - Reporting qualite pour tracer les controles et la robustesse du flux.

        **Limites et vigilance**
        - Le CA par article reste un proxy de priorisation.
        - Les biais de stock, de saisonnalite et de prix promotionnels doivent etre interpretes avec contexte metier.
        - Les seuils sont recalibrables selon la strategie commerciale.
        """
    )
    st.stop()

if page == "Reporting qualite":
    st.header("🧪 Reporting qualite data")
    st.markdown(
        "<span style='display:inline-block; padding:4px 10px; border-radius:999px; background:#E8F5E9; color:#1B5E20; font-weight:600; font-size:0.85rem;'>Amelioration IA</span>",
        unsafe_allow_html=True,
    )
    st.caption("Objectif: rendre visible l'apport de Pandera sur les erreurs de saisie et les regles metier critiques.")

    if st.button("🔄 Sync quality exports depuis notebook"):
        copied, missing, src_dir, dst_dir = sync_quality_exports_to_dashboard()
        if copied > 0:
            st.success(f"Sync qualite OK: {copied} fichier(s) copie(s) vers {dst_dir}")
        else:
            st.warning(f"Aucun fichier copie. Verifier la source: {src_dir}")
        if missing:
            st.caption("Fichiers manquants: " + ", ".join(missing))
        load_quality_exports_from_notebook.clear()
        st.rerun()

    quality_exports, quality_src_dir = load_quality_exports_from_notebook()
    if quality_exports is not None:
        quality = {
            'prix_negatifs': quality_exports.get('prix_negatifs', pd.DataFrame()),
            'prix_achat_negatifs': pd.DataFrame(),
            'sku_manquants': quality_exports.get('sku_manquants', pd.DataFrame()),
            'sku_doublons': quality_exports.get('sku_doublons', pd.DataFrame()),
            'id_web_manquants': quality_exports.get('id_web_manquants', pd.DataFrame()),
            'pandera_enabled': True,
            'pandera_ok': True,
            'pandera_failure_cases': pd.DataFrame(),
            'pandera_violations': 0,
            'pandera_message': 'Reporting charge depuis les exports notebook (sources brutes + controles amont).',
        }
        st.caption("Source reporting brute: exports notebook synchronises")
    else:
        quality = build_quality_reporting(df)
        st.caption("Source reporting: controles recalcules depuis df_final dans le dashboard (mode fallback).")

    if 'pandera_violations' not in quality:
        quality['pandera_violations'] = int(len(quality.get('pandera_failure_cases', pd.DataFrame())))

    q1, q2, q3, q4 = st.columns(4)
    with q1:
        st.metric("Prix de vente negatifs", f"{len(quality['prix_negatifs']):,}")
    with q2:
        st.metric("SKU manquants", f"{len(quality['sku_manquants']):,}")
    with q3:
        st.metric("SKU doublons", f"{len(quality['sku_doublons']):,}")
    with q4:
        st.metric("id_web manquants (web=1)", f"{len(quality['id_web_manquants']):,}")

    if quality['pandera_enabled']:
        st.success("Pandera active") if quality['pandera_ok'] else st.warning("Pandera active - violations detectees")
    else:
        st.info("Pandera non active")
    st.metric("Violations Pandera", f"{int(quality['pandera_violations']):,}")
    st.caption(quality['pandera_message'])

    show_details = st.toggle("Afficher les details techniques", value=False)
    if show_details:
        st.subheader("Verification prix negatifs")
        st.dataframe(quality['prix_negatifs'].head(200), width='stretch')

        st.subheader("Verification SKU anomalies")
        col_a, col_b = st.columns(2)
        with col_a:
            st.markdown("**Lignes sans code article (SKU)**")
            st.dataframe(quality['sku_manquants'].head(200), width='stretch')
        with col_b:
            st.markdown("**SKU en doublon**")
            st.dataframe(quality['sku_doublons'].head(200), width='stretch')

        st.subheader("Verification id_web manquants")
        st.dataframe(quality['id_web_manquants'].head(200), width='stretch')
    else:
        st.info("Details techniques masques. Activez le switch pour afficher les tables de controle.")

    report_export = pd.DataFrame({
        'controle': [
            'prix_negatifs',
            'sku_manquants',
            'sku_doublons',
            'id_web_manquants_web1',
            'pandera_ok',
            'pandera_violations',
        ],
        'volume': [
            len(quality['prix_negatifs']),
            len(quality['sku_manquants']),
            len(quality['sku_doublons']),
            len(quality['id_web_manquants']),
            int(bool(quality['pandera_ok'])),
            int(quality['pandera_violations']),
        ]
    })
    st.download_button(
        label="⬇️ Telecharger le reporting qualite (CSV)",
        data=report_export.to_csv(index=False, encoding='utf-8-sig'),
        file_name='bc05_reporting_qualite.csv',
        mime='text/csv'
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


# Filtre categorie produits (sans perte de lignes par defaut)
if 'product_id_web' in df_filtered.columns:
    category_series = df_filtered['product_id_web'].astype('object').where(df_filtered['product_id_web'].notna(), '(Sans categorie)')
    categories_toutes = sorted(category_series.unique().tolist())
    if categories_toutes:
        categories_selectionnees = st.sidebar.multiselect(
            "Categorie produit",
            options=categories_toutes,
            default=categories_toutes,
            help="Par defaut, toutes les categories sont conservees, y compris les valeurs manquantes."
        )
        df_filtered = df_filtered[category_series.isin(categories_selectionnees)]


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
# VUE CODIR - SYNTHÈSE DÉCISIONNELLE
# ============================================

if page == "Tableau de bord decisionnel":
    st.header("🧭 Synthese decisionnelle")
    st.caption("Version courte: detecter, expliquer, prioriser, decider")

    st.info("Source de reference: df_final.xlsx (base unique pour chiffres cles et decisions)")

    if bc05_decision_matrix is not None and not bc05_decision_matrix.empty:
        st.subheader("🚀 Amelioration IA")
        src_name = bc05_decision_path.name if bc05_decision_path else 'bc05_matrice_decisionnelle.csv'
        st.caption(f"Matrice decisionnelle IF + SHAP + impact business chargee depuis: {src_name}")

        matrix_df = bc05_decision_matrix.copy()
        
        # Aligner la matrice IA sur la base de reference du dashboard (df_final filtre)
        if 'product_id' in matrix_df.columns and 'product_id' in df_filtered.columns:
            ref_ids = set(df_filtered['product_id'].astype(str))
            before_rows = len(matrix_df)
            matrix_df = matrix_df[matrix_df['product_id'].astype(str).isin(ref_ids)].copy()
            dropped_rows = before_rows - len(matrix_df)
            if dropped_rows > 0:
                st.caption(f"Alignement source: {before_rows} -> {len(matrix_df)} lignes (base df_final filtrée)")

        if 'priorite_decisionnelle' in matrix_df.columns:
            order = {'Critique': 0, 'A surveiller': 1, 'Normal': 2}
            matrix_df['__ord'] = matrix_df['priorite_decisionnelle'].map(order).fillna(9)
            matrix_df = matrix_df.sort_values(['__ord', 'decision_score'], ascending=[True, False]).drop(columns='__ord')

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("Critiques (IA)", int((matrix_df['priorite_decisionnelle'] == 'Critique').sum()))
            with m2:
                st.metric("A surveiller (IA)", int((matrix_df['priorite_decisionnelle'] == 'A surveiller').sum()))
            with m3:
                st.metric("Normal (IA)", int((matrix_df['priorite_decisionnelle'] == 'Normal').sum()))

            st.metric("Lignes matrice alignees", f"{len(matrix_df):,}")

            strategic_cols = [
                'product_id', 'priorite_decisionnelle', 'decision_score',
                'shap_top_driver', 'lecture_strategique', 'ca_par_article', 'stock_quantity', 'taux_marge'
            ]
            strategic_cols = [c for c in strategic_cols if c in matrix_df.columns]

            watch_df = matrix_df[matrix_df['priorite_decisionnelle'].isin(['Critique', 'A surveiller'])].copy()
            max_default = min(200, len(watch_df)) if len(watch_df) > 0 else 0
            if max_default > 0:
                limit = st.number_input(
                    "Nb lignes a afficher (Critique + A surveiller)",
                    min_value=10,
                    max_value=max(10, len(watch_df)),
                    value=max_default,
                    step=10
                )
            else:
                limit = 0

            st.dataframe(
                watch_df[strategic_cols].head(int(limit)) if limit else watch_df[strategic_cols],
                width='stretch'
            )

            st.markdown("### Decomposition du score IA (produits critiques)")
            component_cols = [
                'if_component',
                'knn_component',
                'kmeans_component',
                'shap_component',
                'impact_component',
            ]
            component_cols = [c for c in component_cols if c in matrix_df.columns]
            crit_df = matrix_df[matrix_df['priorite_decisionnelle'] == 'Critique'].copy()

            if not crit_df.empty and component_cols:
                top_n = int(min(20, len(crit_df)))
                crit_view_cols = ['product_id', 'decision_score'] + component_cols
                crit_view_cols = [c for c in crit_view_cols if c in crit_df.columns]
                crit_view = crit_df[crit_view_cols].head(top_n).copy()
                st.dataframe(crit_view, width='stretch')

                plot_df = crit_view.copy()
                if 'product_id' in plot_df.columns:
                    plot_df['product_id'] = plot_df['product_id'].astype(str)
                    comp_long = plot_df.melt(
                        id_vars=['product_id'],
                        value_vars=component_cols,
                        var_name='composante',
                        value_name='contribution',
                    )
                    fig_components = px.bar(
                        comp_long,
                        x='product_id',
                        y='contribution',
                        color='composante',
                        barmode='stack',
                        title='Top critiques - decomposition des composantes du score',
                        labels={'product_id': 'Produit', 'contribution': 'Contribution', 'composante': 'Composante'},
                    )
                    fig_components.update_layout(height=480, margin=dict(l=30, r=30, t=70, b=40))
                    st.plotly_chart(fig_components, width='stretch')

                st.markdown("### Lecture metier automatique (top critiques)")
                weights = {
                    'if_component': 0.30,
                    'knn_component': 0.20,
                    'kmeans_component': 0.15,
                    'shap_component': 0.10,
                    'impact_component': 0.25,
                }
                labels = {
                    'if_component': 'atypie globale',
                    'knn_component': 'rarete locale',
                    'kmeans_component': 'profil de cluster a risque',
                    'shap_component': 'coherence explicative',
                    'impact_component': 'impact business',
                }

                lines = []
                for _, row in crit_view.head(5).iterrows():
                    contrib = {}
                    for c in component_cols:
                        val = pd.to_numeric(row.get(c, 0), errors='coerce')
                        if pd.notna(val):
                            contrib[c] = float(val) * weights.get(c, 0)
                    top_drivers = sorted(contrib.items(), key=lambda x: x[1], reverse=True)[:2]
                    drivers_txt = ", ".join([labels.get(k, k) for k, _ in top_drivers]) if top_drivers else "signaux combines"

                    score_val = pd.to_numeric(row.get('decision_score', np.nan), errors='coerce')
                    if pd.notna(score_val):
                        score_txt = f"{float(score_val):.2f}"
                    else:
                        score_txt = "n/a"

                    impact_val = pd.to_numeric(row.get('impact_component', np.nan), errors='coerce')
                    if pd.notna(impact_val) and impact_val >= 0.7:
                        impact_txt = "impact business eleve"
                    elif pd.notna(impact_val) and impact_val >= 0.4:
                        impact_txt = "impact business moyen"
                    else:
                        impact_txt = "impact business modere"

                    lines.append(
                        f"- Produit {row.get('product_id', 'n/a')}: score {score_txt} (Critique), alerte tiree principalement par {drivers_txt}, avec {impact_txt}."
                    )

                if lines:
                    st.markdown("\n".join(lines))
            else:
                st.info("Decomposition indisponible: aucun produit critique ou composantes manquantes.")

            st.markdown("### Tableau de priorisation operationnelle")

            strategic_table = watch_df.copy()

            def business_impact_label(row):
                ca = pd.to_numeric(row.get('ca_par_article', 0), errors='coerce')
                score = pd.to_numeric(row.get('decision_score', 0), errors='coerce')
                if ca >= 400 or score >= 0.75:
                    return 'Impact eleve'
                if ca >= 150 or score >= 0.60:
                    return 'Impact moyen'
                return 'Impact modere'

            def priority_action(row):
                lecture = str(row.get('lecture_strategique', '')).lower()
                marge = pd.to_numeric(row.get('taux_marge', np.nan), errors='coerce')
                stock = pd.to_numeric(row.get('stock_quantity', np.nan), errors='coerce')
                if 'marge negative' in lecture or (pd.notna(marge) and marge < 0):
                    return 'Corriger prix/marge sous 24-48h'
                if 'rupture' in lecture or (pd.notna(stock) and stock <= 0):
                    return 'Arbitrage stock prioritaire (logistique)'
                if 'atypie' in lecture:
                    return 'Audit fiche produit et validation metier'
                return 'Surveillance hebdomadaire et recontrole'

            strategic_table['impact_business'] = strategic_table.apply(business_impact_label, axis=1)
            strategic_table['action_prioritaire_operationnelle'] = strategic_table.apply(priority_action, axis=1)

            display_priority_cols = [
                'product_id',
                'impact_business',
                'action_prioritaire_operationnelle',
            ]
            display_priority_cols = [c for c in display_priority_cols if c in strategic_table.columns]

            st.dataframe(
                strategic_table[display_priority_cols].head(int(limit)) if limit else strategic_table[display_priority_cols],
                width='stretch'
            )

            st.markdown("### Definition du scoring utilise")
            st.markdown(
                "Score decisionnel = 0.30 * IF_component + 0.20 * kNN_component + 0.15 * KMeans_component + 0.10 * SHAP_component + 0.25 * Impact_component"
            )
            st.markdown("### Justification metier du scoring")
            st.markdown(
                "- **IF (0.30)**: signal principal de risque global pour capter vite les comportements atypiques a fort potentiel de perte."
            )
            st.markdown(
                "- **kNN (0.20)**: complete IF en detectant les cas rares localement, utiles quand une anomalie est subtile mais operationnellement sensible."
            )
            st.markdown(
                "- **K-Means (0.15)**: ajoute une lecture par profil produit pour prioriser les familles de produits structurellement instables."
            )
            st.markdown(
                "- **SHAP (0.10)**: renforce la confiance de decision en expliquant les facteurs dominants, sans sur-ponderer l'explication face au risque."
            )
            st.markdown(
                "- **Impact (0.25)**: garantit la priorisation business (CA, marge, rupture) pour orienter les actions vers les produits a enjeu concret."
            )
            st.markdown(
                "Regle de priorisation metier: **Traiter en priorite les anomalies combinees : atypie IF + rarete locale kNN + profil K-Means a risque + impact business eleve.**"
            )

            st.download_button(
                label="⬇️ Telecharger la matrice decisionnelle IA (CSV)",
                data=matrix_df.to_csv(index=False, encoding='utf-8-sig'),
                file_name='bc05_matrice_decisionnelle.csv',
                mime='text/csv'
            )

            st.info("Lecture strategique: traiter les 'Critique' en 24-48h, puis les 'A surveiller' sur le cycle hebdomadaire.")
            st.stop()

    if bc05_actions is None or bc05_actions.empty:
        st.warning("Exports BC05 non detectes. Generez les fichiers BC05 depuis le notebook pour activer cette vue.")
        st.stop()

    decision_df = build_bc05_decision_table(df_filtered, bc05_actions, bc05_iforest)
    if decision_df.empty:
        st.info("Aucune action BC05 disponible avec les filtres actuels.")
        st.stop()

    total_cases = len(decision_df)
    crit_cases = int((decision_df['priorite'] == 'Critique').sum()) if 'priorite' in decision_df.columns else 0
    high_cases = int((decision_df['priorite'] == 'Elevee').sum()) if 'priorite' in decision_df.columns else 0
    if_cases = int(decision_df['iforest_flag'].fillna(False).sum()) if 'iforest_flag' in decision_df.columns else 0

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("Cas actionnables", f"{total_cases:,}")
    with k2:
        st.metric("Cas critiques", f"{crit_cases:,}")
    with k3:
        st.metric("Cas eleves", f"{high_cases:,}")
    with k4:
        st.metric("Cas IF", f"{if_cases:,}")

    pri_dist = (
        decision_df['priorite']
        .value_counts()
        .reindex(['Critique', 'Elevee', 'Moyenne'], fill_value=0)
        .reset_index()
    )
    pri_dist.columns = ['priorite', 'nb_cas']

    fig_priorities = px.bar(
        pri_dist,
        x='priorite',
        y='nb_cas',
        color='priorite',
        color_discrete_map={'Critique': '#c0392b', 'Elevee': '#d68910', 'Moyenne': '#2471a3'},
        title='Repartition des priorites BC05'
    )
    fig_priorities.update_layout(showlegend=False, height=320)
    st.plotly_chart(fig_priorities, use_container_width=True)

    st.subheader("Top actions 24-48h")
    top_urgent = decision_df[decision_df['priorite'] == 'Critique'].copy()
    if top_urgent.empty:
        top_urgent = decision_df[decision_df['priorite'].isin(['Critique', 'Elevee'])].copy()

    sort_cols = [c for c in ['bc05_anomaly_count', 'ca_par_article'] if c in top_urgent.columns]
    if sort_cols:
        top_urgent = top_urgent.sort_values(by=sort_cols, ascending=False)

    top_urgent = top_urgent.head(20)

    codir_cols = [
        'product_id_ref', 'priorite', 'motif_decision', 'action_recommandee',
        'responsable', 'delai_cible', 'bc05_anomaly_count', 'ca_par_article'
    ]
    codir_cols = [c for c in codir_cols if c in top_urgent.columns]
    st.dataframe(top_urgent[codir_cols], width='stretch')

    st.markdown("### Definition du scoring utilise")
    st.markdown(
        "Score decisionnel = 0.45 * IF_component + 0.25 * SHAP_component + 0.30 * Impact_component"
    )
    st.markdown(
        "Regle de priorisation metier: **Traiter en priorite les anomalies combinees : score IF faible + marge atypique + faible rotation.**"
    )

    codir_csv = top_urgent[codir_cols].to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="⬇️ Telecharger la short-list CODIR (CSV)",
        data=codir_csv,
        file_name="bc05_shortlist_codir.csv",
        mime="text/csv"
    )

    st.info("Recommandation: traiter d'abord les cas critiques (24-48h), puis les cas eleves dans la semaine.")
    st.stop()

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
