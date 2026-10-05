import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime, date
import plotly.graph_objects as go
import plotly.express as px
import re
from io import BytesIO

# Importação segura do ReportLab para geração de PDF
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib import colors
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False

# Função auxiliar para limpar emojis no PDF e garantir tipografia nítida
def limpar_emojis(texto):
    if not isinstance(texto, str):
        return str(texto)
    emoji_pattern = re.compile(
        "["
        "\U00010000-\U0010ffff"
        "\u2600-\u27bf"
        "\u2300-\u23ff"
        "\u2b50-\u2b55"
        "\u200d"
        "\ufe0f"
        "]+",
        flags=re.UNICODE
    )
    return emoji_pattern.sub(r'', texto).strip()

# Função geradora do PDF de Gastos Diários
def gerar_pdf_gastos(df_dados, mes_nome, ano):
    if not REPORTLAB_DISPONIVEL or df_dados.empty:
        return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=14
    )

    elements.append(Paragraph(f"Relatório de Despesas Diárias — {mes_nome} de {ano}", title_style))
    data_emissao = datetime.now().strftime("%d/%m/%Y às %H:%M")
    total_val = df_dados['valor'].sum()
    elements.append(Paragraph(f"Emitido em: {data_emissao} | <b>Total Lançado: R$ {total_val:,.2f}</b>", subtitle_style))

    cabecalho = ["Dia", "Descrição", "Categoria", "Forma Pagamento", "Valor (R$)"]
    dados = [cabecalho]

    for _, r in df_dados.iterrows():
        dia_txt = f"Dia {int(r['dia']):02d}"
        desc_txt = str(r['descricao'])[:32]
        cat_txt = limpar_emojis(str(r['categoria']))[:25]
        pag_txt = str(r.get('forma_pagamento', 'PIX'))
        cartao = str(r.get('cartao_banco', '')).strip()
        if cartao:
            pag_txt += f" ({cartao})"
        pag_txt = pag_txt[:25]
        val_txt = f"R$ {r['valor']:,.2f}"
        dados.append([dia_txt, desc_txt, cat_txt, pag_txt, val_txt])

    dados.append(["", "", "", "TOTAL GERAL:", f"R$ {total_val:,.2f}"])

    t = Table(dados, colWidths=[55, 160, 115, 125, 90], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-2, -1), 'LEFT'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8.5),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9.5),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#0f172a')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
    ]))

    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

# Função geradora do PDF de Despesas Fixas e Parcelas
def gerar_pdf_fixos(df_dados):
    if not REPORTLAB_DISPONIVEL or df_dados.empty:
        return None
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )
    styles = getSampleStyleSheet()
    elements = []

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#0f172a'),
        spaceAfter=4
    )
    subtitle_style = ParagraphStyle(
        'DocSub',
        parent=styles['Normal'],
        fontSize=9.5,
        leading=13,
        textColor=colors.HexColor('#64748b'),
        spaceAfter=14
    )

    elements.append(Paragraph("Relatório de Despesas Fixas & Parcelamentos", title_style))
    data_emissao = datetime.now().strftime("%d/%m/%Y às %H:%M")
    total_val = df_dados['valor'].sum()
    elements.append(Paragraph(f"Emitido em: {data_emissao} | <b>Total Comprometido: R$ {total_val:,.2f} / mês</b>", subtitle_style))

    cabecalho = ["Descrição", "Tipo", "Parcelas", "Forma Pagamento", "Valor Mensal (R$)"]
    dados = [cabecalho]

    for _, r in df_dados.iterrows():
        desc_txt = str(r['descricao'])[:30]
        tipo_txt = str(r['tipo'])
        parc_txt = f"{int(r['parcela_atual'])} / {int(r['total_parcelas'])}" if tipo_txt == "Parcela" else "Contínuo"
        pag_txt = str(r.get('forma_pagamento', 'Boleto'))
        cartao = str(r.get('cartao_banco', '')).strip()
        if cartao:
            pag_txt += f" ({cartao})"
        pag_txt = pag_txt[:25]
        val_txt = f"R$ {r['valor']:,.2f}"
        dados.append([desc_txt, tipo_txt, parc_txt, pag_txt, val_txt])

    dados.append(["", "", "", "TOTAL MENSAL:", f"R$ {total_val:,.2f}"])

    t = Table(dados, colWidths=[160, 80, 80, 135, 90], repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('ALIGN', (0, 0), (-2, -1), 'LEFT'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#e2e8f0')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f8fafc')]),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 8.5),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 9.5),
        ('LINEABOVE', (0, -1), (-1, -1), 1.5, colors.HexColor('#0f172a')),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#f1f5f9')),
    ]))

    elements.append(t)
    doc.build(elements)
    return buffer.getvalue()

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Controle Orçamentário",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILIZAÇÃO CSS (Dark UI & Banners) ---
st.markdown("""
<style>
    .stApp {
        background-color: #0b0d13;
        color: #f1f5f9;
        font-family: 'Segoe UI', Tahoma, sans-serif;
    }
    .metric-card {
        background: linear-gradient(145deg, #161922, #11131a);
        border: 1px solid #232734;
        border-radius: 10px;
        padding: 14px 18px;
        margin-bottom: 10px;
    }
    .metric-label {
        color: #94a3b8;
        font-size: 11px;
        text-transform: uppercase;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    .metric-num {
        color: #ffffff;
        font-size: 22px;
        font-weight: bold;
        margin-top: 4px;
    }
    .danger-box {
        background: rgba(239, 68, 68, 0.15);
        border-left: 4px solid #ef4444;
        padding: 12px 16px;
        border-radius: 6px;
        color: #fca5a5;
        margin: 12px 0;
        font-size: 14px;
    }
    .success-box {
        background: rgba(16, 185, 129, 0.15);
        border-left: 4px solid #10b981;
        padding: 12px 16px;
        border-radius: 6px;
        color: #6ee7b7;
        margin: 12px 0;
        font-size: 14px;
    }
    .top-item-box {
        background: #161922;
        border: 1px solid #232734;
        padding: 10px 14px;
        border-radius: 8px;
        margin-bottom: 8px;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS (SQLite) ---
conn = sqlite3.connect("orcamento.db", check_same_thread=False)
cursor = conn.cursor()

# Metas mensais
cursor.execute("""
CREATE TABLE IF NOT EXISTS metas_mensais (
    ano INTEGER,
    mes INTEGER,
    renda REAL,
    poupanca REAL,
    modo_ajuste TEXT,
    PRIMARY KEY (ano, mes)
)
""")

try:
    cursor.execute("ALTER TABLE metas_mensais ADD COLUMN modo_ajuste TEXT DEFAULT 'rebalancear'")
    conn.commit()
except sqlite3.OperationalError:
    pass

# Despesas fixas e parcelas
cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas_fixas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    valor REAL,
    tipo TEXT,
    parcela_atual INTEGER,
    total_parcelas INTEGER
)
""")

for col_def in [("forma_pagamento", "TEXT DEFAULT 'Boleto / Débito'"), ("cartao_banco", "TEXT DEFAULT ''")]:
    try:
        cursor.execute(f"ALTER TABLE despesas_fixas ADD COLUMN {col_def[0]} {col_def[1]}")
        conn.commit()
    except sqlite3.OperationalError:
        pass

# Gastos diários
cursor.execute("""
CREATE TABLE IF NOT EXISTS gastos_diarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ano INTEGER,
    mes INTEGER,
    dia INTEGER,
    descricao TEXT,
    categoria TEXT,
    valor REAL
)
""")

for col_def in [("forma_pagamento", "TEXT DEFAULT 'PIX'"), ("cartao_banco", "TEXT DEFAULT ''")]:
    try:
        cursor.execute(f"ALTER TABLE gastos_diarios ADD COLUMN {col_def[0]} {col_def[1]}")
        conn.commit()
    except sqlite3.OperationalError:
        pass

# Patrimônio
cursor.execute("""
CREATE TABLE IF NOT EXISTS patrimonio_base (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    saldo_inicial REAL DEFAULT 0.0
)
""")
cursor.execute("INSERT OR IGNORE INTO patrimonio_base (id, saldo_inicial) VALUES (1, 0.0)")

cursor.execute("""
CREATE TABLE IF NOT EXISTS aportes_consolidados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ano INTEGER,
    mes INTEGER,
    valor REAL,
    data_consolidacao TEXT,
    UNIQUE(ano, mes)
)
""")
conn.commit()

# --- BARRA LATERAL (NAVEGAÇÃO) ---
st.sidebar.title("🎯 Menu")

ano_atual = st.sidebar.selectbox("Ano", [2025, 2026, 2027], index=1)
meses_nomes = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
mes_atual_idx = datetime.now().month - 1
mes_selecionado = st.sidebar.selectbox("Mês", meses_nomes, index=mes_atual_idx)
mes_num = meses_nomes.index(mes_selecionado) + 1
dias_no_mes = calendar.monthrange(ano_atual, mes_num)[1]

menu = st.sidebar.radio(
    "Ir para:",
    [
        "📊 Calendário e Gráfico Diário",
        "⚙️ Configurar Renda e Regras",
        "💸 Lançar Gasto Diário",
        "📌 Gastos Fixos & Parcelas",
        "💰 Patrimônio"
    ]
)

# --- RECUPERAÇÃO DE CONFIGURAÇÕES ---
cursor.execute("SELECT renda, poupanca, modo_ajuste FROM metas_mensais WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
config_row = cursor.fetchone()
renda_mensal = config_row[0] if config_row else 10000.0
meta_poupanca = config_row[1] if config_row else 1500.0
modo_ajuste = config_row[2] if (config_row and config_row[2]) else "rebalancear"

df_fixos = pd.read_sql_query("SELECT id, descricao, valor, tipo, parcela_atual, total_parcelas, forma_pagamento, cartao_banco FROM despesas_fixas", conn)
total_fixos = df_fixos["valor"].sum() if not df_fixos.empty else 0.0

saldo_livre_mes = max(0.0, renda_mensal - meta_poupanca - total_fixos)

# Consulta de gastos diários
df_gastos = pd.read_sql_query(
    "SELECT id, dia, descricao, categoria, valor, forma_pagamento, cartao_banco FROM gastos_diarios WHERE ano = ? AND mes = ? ORDER BY dia ASC, id ASC",
    conn, params=(ano_atual, mes_num)
)
gastos_por_dia = df_gastos.groupby("dia")["valor"].sum().to_dict() if not df_gastos.empty else {}
total_gasto_real = df_gastos["valor"].sum() if not df_gastos.empty else 0.0
saldo_restante_caixa = saldo_livre_mes - total_gasto_real

# =========================================================
# LÓGICA DE SIMULAÇÃO DIA A DIA
# =========================================================
dias_lista = []
dias_numeros = []
teto_lista = []
gasto_lista = []
cores_status = []
cores_grafico = []

dia_negativo = None
saldo_acum_check = saldo_livre_mes
hoje_dia = date.today().day
mes_eh_atual = (ano_atual == date.today().year and mes_num == date.today().month)

if modo_ajuste == "rebalancear":
    saldo_remanescente = saldo_livre_mes
    for d in range(1, dias_no_mes + 1):
        dias_a_frente = (dias_no_mes - d + 1)
        teto_dia = max(0.0, saldo_remanescente / dias_a_frente) if dias_a_frente > 0 else 0.0
        gasto_dia = gastos_por_dia.get(d, 0.0)

        saldo_acum_check -= gasto_dia
        if saldo_acum_check < 0 and dia_negativo is None:
            dia_negativo = d

        if gasto_dia > 0:
            if gasto_dia > teto_dia:
                cor = "vermelho"
                hex_c = "#ef4444"
            elif gasto_dia >= (teto_dia * 0.8):
                cor = "amarelo"
                hex_c = "#f59e0b"
            else:
                cor = "verde"
                hex_c = "#10b981"
        else:
            if saldo_remanescente <= 0:
                cor = "vermelho"
                hex_c = "#ef4444"
            else:
                cor = "neutro"
                hex_c = "rgba(100, 116, 139, 0.25)"

        saldo_remanescente -= gasto_dia

        tag_hoje = " 📍 (Hoje)" if (mes_eh_atual and d == hoje_dia) else ""
        dias_lista.append(f"Dia {d:02d}{tag_hoje}")
        dias_numeros.append(d)
        teto_lista.append(teto_dia)
        gasto_lista.append(gasto_dia)
        cores_status.append(cor)
        cores_grafico.append(hex_c)

else:
    teto_base_fixo = saldo_livre_mes / dias_no_mes if dias_no_mes > 0 else 0.0
    saldo_acumulado = saldo_livre_mes

    for d in range(1, dias_no_mes + 1):
        gasto_dia = gastos_por_dia.get(d, 0.0)
        teto_dia = teto_base_fixo if saldo_acumulado >= teto_base_fixo else max(0.0, saldo_acumulado)

        saldo_acum_check -= gasto_dia
        if saldo_acum_check < 0 and dia_negativo is None:
            dia_negativo = d

        saldo_acumulado -= gasto_dia

        if gasto_dia > 0:
            if gasto_dia > teto_base_fixo:
                cor = "vermelho"
                hex_c = "#ef4444"
            elif gasto_dia >= (teto_base_fixo * 0.8):
                cor = "amarelo"
                hex_c = "#f59e0b"
            else:
                cor = "verde"
                hex_c = "#10b981"
        else:
            if teto_dia <= 0.0:
                cor = "vermelho"
                hex_c = "#ef4444"
            else:
                cor = "neutro"
                hex_c = "rgba(100, 116, 139, 0.25)"

        tag_hoje = " 📍 (Hoje)" if (mes_eh_atual and d == hoje_dia) else ""
        dias_lista.append(f"Dia {d:02d}{tag_hoje}")
        dias_numeros.append(d)
        teto_lista.append(teto_dia)
        gasto_lista.append(gasto_dia)
        cores_status.append(cor)
        cores_grafico.append(hex_c)

df_exibicao = pd.DataFrame({
    "Dia": dias_lista,
    "Teto Permitido (R$)": teto_lista,
    "Gasto Real (R$)": gasto_lista
})

df_dados_grafico = pd.DataFrame({
    "dia_num": dias_numeros,
    "dia_label": [f"D{d:02d}" for d in dias_numeros],
    "teto": teto_lista,
    "gasto": gasto_lista,
    "cor": cores_grafico
})

# =========================================================
# TELA 1: CALENDÁRIO ORÇAMENTÁRIO & GRÁFICOS
# =========================================================
if menu == "📊 Calendário e Gráfico Diário":
    st.title(f"Acompanhamento — {mes_selecionado} de {ano_atual}")

    # 1. LANÇAMENTO RÁPIDO NA TELA INICIAL
    with st.expander("⚡ Novo Lançamento Rápido (Sem trocar de aba)", expanded=False):
        col_q1, col_q2, col_q3 = st.columns([1, 1.5, 1.5])
        with col_q1:
            q_dia = st.number_input("Dia", min_value=1, max_value=dias_no_mes, value=min(date.today().day, dias_no_mes), step=1, key="q_dia")
        with col_q2:
            q_cat = st.selectbox("Categoria", ["🍔 Alimentação", "🚗 Transporte", "🛒 Supermercado", "🍿 Lazer", "💊 Saúde", "🏠 Moradia / Contas", "✏️ Outra / Personalizar"], key="q_cat")
        with col_q3:
            q_forma = st.selectbox("Pagamento", ["PIX", "Cartão de Crédito", "Cartão de Débito", "Dinheiro"], key="q_forma")

        q_cat_custom = ""
        if "Personalizar" in q_cat:
            q_cat_custom = st.text_input("Qual a categoria?", key="q_cat_custom")

        q_cartao = ""
        if "Cartão" in q_forma:
            cursor.execute("SELECT DISTINCT cartao_banco FROM gastos_diarios WHERE cartao_banco IS NOT NULL AND cartao_banco != ''")
            usados_q = [r[0] for r in cursor.fetchall()]
            bancos_base = ["Nubank", "Inter", "Itaú", "Bradesco", "Santander", "C6 Bank", "Banco do Brasil", "Caixa"]
            opcoes_q = sorted(list(set(bancos_base + usados_q))) + ["✏️ Digitar outro banco / cartão..."]
            sel_q_cart = st.selectbox("Cartão / Banco", opcoes_q, key="q_cartao_sel")
            if "Digitar outro" in sel_q_cart:
                q_cartao = st.text_input("Nome do cartão/banco:", key="q_cartao_input")
            else:
                q_cartao = sel_q_cart

        col_qd, col_qv = st.columns([2, 1])
        with col_qd:
            q_desc = st.text_input("Descrição do gasto", placeholder="Ex: Café, Farmácia, Combustível", key="q_desc")
        with col_qv:
            q_val = st.number_input("Valor (R$)", min_value=0.5, step=5.0, key="q_val")

        if st.button("Salvar Registro Rápido", type="primary", key="btn_salvar_rapido"):
            cat_final = q_cat_custom.strip() if ("Personalizar" in q_cat and q_cat_custom.strip()) else q_cat
            if q_desc.strip() == "":
                st.warning("Preencha a descrição do gasto.")
            elif "Personalizar" in q_cat and q_cat_custom.strip() == "":
                st.warning("Informe o nome da categoria personalizada.")
            elif "Cartão" in q_forma and q_cartao.strip() == "":
                st.warning("Informe o cartão utilizado.")
            else:
                cursor.execute("""
                    INSERT INTO gastos_diarios (ano, mes, dia, descricao, categoria, valor, forma_pagamento, cartao_banco)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (ano_atual, mes_num, int(q_dia), q_desc.strip(), cat_final,
