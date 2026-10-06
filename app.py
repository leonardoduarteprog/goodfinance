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

# Função auxiliar para limpar emojis no PDF
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

# --- BANCO DE DADOS (SQLite) ---
conn = sqlite3.connect("orcamento.db", check_same_thread=False)
cursor = conn.cursor()

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

cursor.execute("""
CREATE TABLE IF NOT EXISTS cartoes_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cartao_banco TEXT UNIQUE,
    dia_fechamento INTEGER DEFAULT 20,
    dia_vencimento INTEGER DEFAULT 27
)
""")

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

# --- MAPA DE CONFIGURAÇÃO DE CARTÕES ---
df_cfg_cartoes = pd.read_sql_query("SELECT cartao_banco, dia_fechamento, dia_vencimento FROM cartoes_config", conn)
cfgs_map = {r["cartao_banco"]: (int(r["dia_fechamento"]), int(r["dia_vencimento"])) for _, r in df_cfg_cartoes.iterrows()}

cursor.execute("SELECT renda, poupanca, modo_ajuste FROM metas_mensais WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
config_row = cursor.fetchone()
renda_mensal = config_row[0] if config_row else 10000.0
meta_poupanca = config_row[1] if config_row else 1500.0
modo_ajuste = config_row[2] if (config_row and config_row[2]) else "rebalancear"

df_fixos = pd.read_sql_query("SELECT id, descricao, valor, tipo, parcela_atual, total_parcelas, forma_pagamento, cartao_banco FROM despesas_fixas", conn)
total_fixos = df_fixos["valor"].sum() if not df_fixos.empty else 0.0

saldo_livre_mes = max(0.0, renda_mensal - meta_poupanca - total_fixos)

df_gastos = pd.read_sql_query(
    "SELECT id, dia, descricao, categoria, valor, forma_pagamento, cartao_banco FROM gastos_diarios WHERE ano = ? AND mes = ? ORDER BY dia ASC, id ASC",
    conn, params=(ano_atual, mes_num)
)
gastos_por_dia = df_gastos.groupby("dia")["valor"].sum().to_dict() if not df_gastos.empty else {}
total_gasto_real = df_gastos["valor"].sum() if not df_gastos.empty else 0.0
saldo_restante_caixa = saldo_livre_mes - total_gasto_real

hoje_dia = date.today().day
mes_eh_atual = (ano_atual == date.today().year and mes_num == date.today().month)

# --- CÁLCULO INTELIGENTE DO TETO DIÁRIO FIXO RESTANTE ---
if mes_eh_atual:
    dias_restantes = max(1, dias_no_mes - hoje_dia + 1)
    teto_diario_restante = max(0.0, saldo_restante_caixa / dias_restantes)
    teto_base_original = (saldo_livre_mes / dias_no_mes) if dias_no_mes > 0 else 0.0
else:
    dias_restantes = dias_no_mes
    teto_diario_restante = (saldo_livre_mes / dias_no_mes) if dias_no_mes > 0 else 0.0
    teto_base_original = teto_diario_restante

# =========================================================
# LÓGICA DE SIMULAÇÃO DIA A DIA (SEM CASCATA CONFUSA)
# =========================================================
dias_lista = []
dias_numeros = []
teto_lista = []
gasto_lista = []
cores_status = []
cores_grafico = []

dia_negativo = None
saldo_acum_check = saldo_livre_mes

if modo_ajuste == "rebalancear":
    for d in range(1, dias_no_mes + 1):
        gasto_dia = gastos_por_dia.get(d, 0.0)
        saldo_acum_check -= gasto_dia
        if saldo_acum_check < 0 and dia_negativo is None:
            dia_negativo = d

        if mes_eh_atual:
            if d < hoje_dia:
                teto_dia = teto_base_original
                if gasto_dia > 0:
                    if gasto_dia > teto_dia:
                        cor = "vermelho"; hex_c = "#ef4444"
                    elif gasto_dia >= (teto_dia * 0.8):
                        cor = "amarelo"; hex_c = "#f59e0b"
                    else:
                        cor = "verde"; hex_c = "#10b981"
                else:
                    cor = "verde"; hex_c = "#10b981"
            else:
                teto_dia = teto_diario_restante
                if gasto_dia > 0:
                    if gasto_dia > teto_dia:
                        cor = "vermelho"; hex_c = "#ef4444"
                    elif gasto_dia >= (teto_dia * 0.8):
                        cor = "amarelo"; hex_c = "#f59e0b"
                    else:
                        cor = "verde"; hex_c = "#10b981"
                else:
                    if saldo_restante_caixa <= 0:
                        cor = "vermelho"; hex_c = "#ef4444"
                    elif d == hoje_dia:
                        cor = "neutro"; hex_c = "#38bdf8"
                    else:
                        cor = "neutro"; hex_c = "rgba(100, 116, 139, 0.25)"
        else:
            teto_dia = teto_base_original
            if gasto_dia > 0:
                if gasto_dia > teto_dia:
                    cor = "vermelho"; hex_c = "#ef4444"
                elif gasto_dia >= (teto_dia * 0.8):
                    cor = "amarelo"; hex_c = "#f59e0b"
                else:
                    cor = "verde"; hex_c = "#10b981"
            else:
                cor = "neutro"; hex_c = "rgba(100, 116, 139, 0.25)"

        tag_hoje = " 📍 (Hoje)" if (mes_eh_atual and d == hoje_dia) else ""
        dias_lista.append(f"Dia {d:02d}{tag_hoje}")
        dias_numeros.append(d)
        teto_lista.append(teto_dia)
        gasto_lista.append(gasto_dia)
        cores_status.append(cor)
        cores_grafico.append(hex_c)

else:
    saldo_acumulado = saldo_livre_mes
    for d in range(1, dias_no_mes + 1):
        gasto_dia = gastos_por_dia.get(d, 0.0)
        teto_dia = teto_base_original if saldo_acumulado >= teto_base_original else max(0.0, saldo_acumulado)

        saldo_acum_check -= gasto_dia
        if saldo_acum_check < 0 and dia_negativo is None:
            dia_negativo = d

        saldo_acumulado -= gasto_dia

        if gasto_dia > 0:
            if gasto_dia > teto_base_original:
                cor = "vermelho"; hex_c = "#ef4444"
            elif gasto_dia >= (teto_base_original * 0.8):
                cor = "amarelo"; hex_c = "#f59e0b"
            else:
                cor = "verde"; hex_c = "#10b981"
        else:
            if teto_dia <= 0.0:
                cor = "vermelho"; hex_c = "#ef4444"
            else:
                cor = "neutro"; hex_c = "rgba(100, 116, 139, 0.25)"

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
            opcoes_q = sorted(list(set(bancos_base + usados_q + list(cfgs_map.keys())))) + ["✏️ Digitar outro banco / cartão..."]
            sel_q_cart = st.selectbox("Cartão / Banco", opcoes_q, key="q_cartao_sel")
            if "Digitar outro" in sel_q_cart:
                q_cartao = st.text_input("Nome do cartão/banco:", key="q_cartao_input")
            else:
                q_cartao = sel_q_cart

            if q_cartao in cfgs_map and "Crédito" in q_forma:
                c_fech, c_venc = cfgs_map[q_cartao]
                if int(q_dia) >= c_fech:
                    st.info(f"💡 **Melhor compra:** Como o gasto é a partir do dia {c_fech:02d}, entrará na **fatura do próximo mês** (vencimento dia {c_venc:02d})!")
                else:
                    st.caption(f"📌 Compra realizada antes do fechamento (dia {c_fech:02d}). Entrará na **fatura deste mês**.")

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
                """, (ano_atual, mes_num, int(q_dia), q_desc.strip(), cat_final, q_val, q_forma, q_cartao.strip()))
                conn.commit()
                st.success(f"Despesa de R$ {q_val:,.2f} no Dia {int(q_dia):02d} registrada com sucesso!")
                st.rerun()

    st.write("")

    # CARDS PRINCIPAIS 100% NATIVOS (COM META DIÁRIA RESTANTE CLARA)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Orçamento Livre Inicial", f"R$ {saldo_livre_mes:,.2f}")
    col2.metric("Total Gasto Até Agora", f"R$ {total_gasto_real:,.2f}")
    col3.metric("Saldo Disponível em Caixa", f"R$ {saldo_restante_caixa:,.2f}")
    col4.metric(
        "Teto Fixo / Dia Restante",
        f"R$ {teto_diario_restante:,.2f}",
        help=f"Saldo em caixa dividido igualmente pelos {dias_restantes} dias restantes no mês"
    )

    # AVISOS DE SALDO NATIVOS
    if dia_negativo:
        st.error(f"🚨 **Atenção:** Seu saldo livre ficou negativo no **Dia {dia_negativo:02d}**! Você já gastou mais do que o planejado para o mês. Saldo restante atual: **R$ {saldo_restante_caixa:,.2f}**.")
    else:
        st.success(f"✅ **Dentro do planejado:** Você possui **R$ {saldo_restante_caixa:,.2f}** em caixa. Dividindo igualmente até o final do mês, você pode gastar até **R$ {teto_diario_restante:,.2f} por dia** ({dias_restantes} dias restantes).")

    st.write("")

    # 2. GRÁFICO DIÁRIO COMPARATIVO
    st.subheader("📊 Comparativo Diário: Teto Permitido vs. Gasto Real")

    visao_grafico = st.radio(
        "Filtrar período no gráfico:",
        ["📅 Mês Completo", "🔍 Apenas Dias com Gastos", "📆 1ª Quinzena (1 a 15)", "📆 2ª Quinzena (16 ao Fim)"],
        horizontal=True
    )

    if visao_grafico == "🔍 Apenas Dias com Gastos":
        df_plot = df_dados_grafico[df_dados_grafico["gasto"] > 0].copy()
        if df_plot.empty:
            df_plot = df_dados_grafico.head(7).copy()
            st.info("Nenhum gasto registrado ainda. Exibindo os primeiros 7 dias para visualização.")
    elif visao_grafico == "📆 1ª Quinzena (1 a 15)":
        df_plot = df_dados_grafico[df_dados_grafico["dia_num"] <= 15].copy()
    elif visao_grafico == "📆 2ª Quinzena (16 ao Fim)":
        df_plot = df_dados_grafico[df_dados_grafico["dia_num"] >= 16].copy()
    else:
        df_plot = df_dados_grafico.copy()

    textos_teto = [f"R$ {t:,.0f}" if t > 0 else "" for t in df_plot["teto"]]
    textos_gasto = [f"R$ {g:,.0f}" if g > 0 else "" for g in df_plot["gasto"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_plot["dia_label"],
        y=df_plot["teto"],
        name="Teto Permitido (R$)",
        marker_color="rgba(56, 189, 248, 0.45)",
        marker_line_color="#38bdf8",
        marker_line_width=1.5,
        text=textos_teto,
        textposition="auto",
        hovertemplate="<b>%{x}</b><br>Teto Permitido: R$ %{y:,.2f}<extra></extra>"
    ))
    fig.add_trace(go.Bar(
        x=df_plot["dia_label"],
        y=df_plot["gasto"],
        name="Gasto Real (R$)",
        marker_color=df_plot["cor"],
        text=textos_gasto,
        textposition="auto",
        hovertemplate="<b>%{x}</b><br>Gasto Real: R$ %{y:,.2f}<extra></extra>"
    ))

    fig.update_layout(
        barmode="group",
        template="plotly_dark",
        height=380,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="", tickangle=0),
        yaxis=dict(title="Reais (R$)", gridcolor="#1e2230"),
        legend=dict(orientation="h", y=1.12, x=0),
        bargap=0.25,
        bargroupgap=0.08
    )
    st.plotly_chart(fig, use_container_width=True)

    st.write("")

    # 3. DISTRIBUIÇÃO POR CATEGORIAS & TOP 3 GASTOS
    st.subheader("🍩 Distribuição por Categorias & Top 3 Maiores Gastos")
    col_cat1, col_cat2 = st.columns([1.2, 1])

    with col_cat1:
        if not df_gastos.empty:
            df_cat = df_gastos.groupby("categoria")["valor"].sum().reset_index()
            fig_donut = px.pie(
                df_cat,
                values="valor",
                names="categoria",
                hole=0.55,
                color_discrete_sequence=["#38bdf8", "#8b5cf6", "#ec4899", "#10b981", "#f59e0b", "#6366f1"]
            )
            fig_donut.update_layout(
                template="plotly_dark",
                height=300,
                margin=dict(l=10, r=10, t=10, b=10),
                legend=dict(orientation="h", y=-0.15)
            )
            st.plotly_chart(fig_donut, use_container_width=True)
        else:
            st.info("Nenhum gasto avulso lançado ainda para gerar a distribuição.")

    with col_cat2:
        st.markdown("##### 🏆 Maiores Despesas Registradas")
        if not df_gastos.empty:
            df_top3 = df_gastos.sort_values(by="valor", ascending=False).head(3)
            for idx, r_top in df_top3.iterrows():
                pag_txt = f"{r_top['forma_pagamento']} ({r_top['cartao_banco']})" if (pd.notna(r_top.get('cartao_banco')) and str(r_top.get('cartao_banco')).strip() != '') else r_top.get('forma_pagamento', '')
                with st.container(border=True):
                    c_t1, c_t2 = st.columns([2, 1])
                    c_t1.write(f"📅 **Dia {int(r_top['dia']):02d}** — {r_top['descricao']}")
                    c_t1.caption(f"{r_top['categoria']} • {pag_txt}")
                    c_t2.subheader(f":red[R$ {r_top['valor']:,.2f}]")
        else:
            st.caption("Ao registrar despesas, as maiores do mês aparecerão aqui.")

    st.write("")

    # TABELA COM FUNDO COLORIDO E MARCAÇÃO DE HOJE
    st.subheader("📋 Tabela do Dia 1 ao Fim do Mês")

    def colorir_linhas(row):
        c = cores_status[row.name]
        if c == "vermelho":
            return ["background-color: rgba(239, 68, 68, 0.35); color: #ffffff; font-weight: 500;"] * len(row)
        elif c == "amarelo":
            return ["background-color: rgba(245, 158, 11, 0.35); color: #ffffff; font-weight: 500;"] * len(row)
        elif c == "verde":
            return ["background-color: rgba(16, 185, 129, 0.35); color: #ffffff; font-weight: 500;"] * len(row)
        return [""] * len(row)

    st.dataframe(
        df_exibicao.style.apply(colorir_linhas, axis=1).format({
            "Teto Permitido (R$)": "R$ {:,.2f}",
            "Gasto Real (R$)": "R$ {:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # --- SEÇÃO INTELIGENTE DE CARTÕES COM STREAMLIT NATIVO ---
    st.subheader("💳 Raio-X dos Cartões & Faturas")

    with st.expander("⚙️ Configurar Fechamento e Vencimento das Faturas", expanded=False):
        st.write("Defina o dia em que a fatura fecha (corte) e o dia em que vence para cada cartão:")
        
        cursor.execute("SELECT DISTINCT cartao_banco FROM gastos_diarios WHERE cartao_banco IS NOT NULL AND cartao_banco != ''")
        usados_g_all = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT cartao_banco FROM despesas_fixas WHERE cartao_banco IS NOT NULL AND cartao_banco != ''")
        usados_f_all = [r[0] for r in cursor.fetchall()]
        bancos_padrao = ["Nubank", "Inter", "Itaú", "Bradesco", "Santander", "C6 Bank", "Banco do Brasil", "Caixa"]
        lista_opcoes_config_cart = sorted(list(set(bancos_padrao + usados_g_all + usados_f_all + list(cfgs_map.keys()))))
        lista_opcoes_config_cart.append("✏️ Digitar outro banco / cartão...")

        c_cfg1, c_cfg2, c_cfg3 = st.columns([2, 1, 1])
        with c_cfg1:
            cart_sel_cfg = st.selectbox("Cartão / Banco a Configurar", lista_opcoes_config_cart, key="cart_sel_cfg")
            nome_cart_final = cart_sel_cfg
            if "Digitar outro" in cart_sel_cfg:
                nome_cart_final = st.text_input("Nome do Cartão:", key="outro_cart_cfg")
        with c_cfg2:
            val_fech_default = cfgs_map.get(nome_cart_final, (20, 27))[0] if nome_cart_final in cfgs_map else 20
            dia_fech_input = st.number_input("Dia Fechamento (Corte)", min_value=1, max_value=31, value=int(val_fech_default), key="dia_fech_input")
        with c_cfg3:
            val_venc_default = cfgs_map.get(nome_cart_final, (20, 27))[1] if nome_cart_final in cfgs_map else 27
            dia_venc_input = st.number_input("Dia Vencimento", min_value=1, max_value=31, value=int(val_venc_default), key="dia_venc_input")

        if st.button("Salvar Regra da Fatura", type="primary", key="btn_salvar_regra_cartao"):
            if nome_cart_final.strip() == "":
                st.warning("Preencha o nome do cartão.")
            else:
                cursor.execute("""
                    INSERT INTO cartoes_config (cartao_banco, dia_fechamento, dia_vencimento)
                    VALUES (?, ?, ?)
                    ON CONFLICT(cartao_banco) DO UPDATE SET
                        dia_fechamento=excluded.dia_fechamento,
                        dia_vencimento=excluded.dia_vencimento
                """, (nome_cart_final.strip(), int(dia_fech_input), int(dia_venc_input)))
                conn.commit()
                st.success(f"Regra da fatura do '{nome_cart_final.strip()}' salva com sucesso!")
                st.rerun()

        if not df_cfg_cartoes.empty:
            st.markdown("###### Cartões com Fechamento Salvo:")
            st.dataframe(
                df_cfg_cartoes.rename(columns={
                    "cartao_banco": "Cartão",
                    "dia_fechamento": "Dia Fechamento",
                    "dia_vencimento": "Dia Vencimento"
                }),
                use_container_width=True,
                hide_index=True
            )

    st.write("")

    # APRESENTAÇÃO DOS CARTÕES ATIVOS NO MÊS
    df_cartoes = df_gastos[df_gastos["forma_pagamento"].str.contains("Cartão", na=False)].copy()

    cartoes_no_mes = sorted(list(set(df_cartoes["cartao_banco"].dropna().tolist() + [r['cartao_banco'] for _, r in df_fixos[df_fixos['forma_pagamento'].str.contains('Cartão', na=False)].iterrows() if r.get('cartao_banco')])))
    cartoes_no_mes = [c for c in cartoes_no_mes if str(c).strip() != '']

    if not cartoes_no_mes and cfgs_map:
        cartoes_no_mes = list(cfgs_map.keys())

    if cartoes_no_mes:
        prev_mes = 12 if mes_num == 1 else mes_num - 1
        prev_ano = ano_atual - 1 if mes_num == 1 else ano_atual

        cols_cards = st.columns(min(len(cartoes_no_mes), 3))
        for idx, c_banco in enumerate(cartoes_no_mes):
            col_target = cols_cards[idx % min(len(cartoes_no_mes), 3)]
            fech_dia, venc_dia = cfgs_map.get(c_banco, (20, 27))
            tem_config = c_banco in cfgs_map

            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0.0) FROM gastos_diarios 
                WHERE ano = ? AND mes = ? AND cartao_banco = ? AND forma_pagamento LIKE '%Crédito%' AND dia >= ?
            """, (prev_ano, prev_mes, c_banco, fech_dia))
            val_prev_pos = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0.0) FROM gastos_diarios 
                WHERE ano = ? AND mes = ? AND cartao_banco = ? AND forma_pagamento LIKE '%Crédito%' AND dia < ?
            """, (ano_atual, mes_num, c_banco, fech_dia))
            val_curr_pre = cursor.fetchone()[0]

            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0.0) FROM despesas_fixas 
                WHERE cartao_banco = ? AND forma_pagamento LIKE '%Crédito%'
            """, (c_banco,))
            val_fixos_cart = cursor.fetchone()[0]

            fatura_mes_total = val_prev_pos + val_curr_pre + val_fixos_cart

            cursor.execute("""
                SELECT COALESCE(SUM(valor), 0.0) FROM gastos_diarios 
                WHERE ano = ? AND mes = ? AND cartao_banco = ? AND forma_pagamento LIKE '%Crédito%' AND dia >= ?
            """, (ano_atual, mes_num, c_banco, fech_dia))
            val_prox_fatura = cursor.fetchone()[0]

            if mes_eh_atual:
                fatura_fechada = hoje_dia >= fech_dia
            else:
                fatura_fechada = (ano_atual < date.today().year) or (ano_atual == date.today().year and mes_num < date.today().month)

            with col_target:
                with st.container(border=True):
                    head1, head2 = st.columns([1.5, 1])
                    head1.subheader(f"💳 {c_banco}")
                    if fatura_fechada:
                        head2.error(f"Fechada (Venc. {venc_dia:02d})")
                    else:
                        head2.success(f"Aberta (Fecha {fech_dia:02d})")

                    if not tem_config:
                        st.caption("⚠️ Usando fechamento padrão (dia 20).")

                    m1, m2 = st.columns(2)
                    m1.metric(
                        label=f"Fatura {mes_selecionado}",
                        value=f"R$ {fatura_mes_total:,.2f}",
                        help=f"Compras antes do dia {fech_dia:02d} + anteriores após fechamento"
                    )
                    m2.metric(
                        label="Próxima Fatura",
                        value=f"R$ {val_prox_fatura:,.2f}",
                        help=f"Compras a partir do dia {fech_dia:02d}"
                    )

                    st.caption(f"⭐ **Melhor dia de compra:** Dia {fech_dia:02d} em diante • Vence dia **{venc_dia:02d}**")

        st.write("")

        # GRÁFICOS COMPARATIVOS DOS CARTÕES
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            tot_por_cartao = df_cartoes.groupby("cartao_banco")["valor"].sum().reset_index() if not df_cartoes.empty else pd.DataFrame(columns=["cartao_banco", "valor"])
            if not tot_por_cartao.empty:
                tot_por_cartao = tot_por_cartao.sort_values(by="valor", ascending=False)
                fig_bar_cartao = px.bar(
                    tot_por_cartao,
                    x="cartao_banco",
                    y="valor",
                    text=tot_por_cartao["valor"].map(lambda x: f"R$ {x:,.2f}"),
                    color="cartao_banco",
                    color_discrete_sequence=["#8b5cf6", "#ec4899", "#38bdf8", "#10b981", "#f59e0b"]
                )
                fig_bar_cartao.update_layout(
                    template="plotly_dark",
                    title="Total Geral Comprado no Cartão este Mês",
                    height=300,
                    margin=dict(l=10, r=10, t=35, b=10),
                    xaxis_title="",
                    yaxis_title="Total (R$)",
                    showlegend=False
                )
                fig_bar_cartao.update_traces(textposition="outside")
                st.plotly_chart(fig_bar_cartao, use_container_width=True)

        with col_g2:
            dia_cartao = df_cartoes.groupby("dia")["valor"].sum().reset_index() if not df_cartoes.empty else pd.DataFrame(columns=["dia", "valor"])
            if not dia_cartao.empty:
                media_dia_uso = dia_cartao["valor"].mean()
                fig_dia_cartao = go.Figure()
                fig_dia_cartao.add_trace(go.Bar(
                    x=dia_cartao["dia"].map(lambda d: f"Dia {d:02d}"),
                    y=dia_cartao["valor"],
                    name="Gasto no Dia",
                    marker_color="#8b5cf6",
                    text=dia_cartao["valor"].map(lambda x: f"R$ {x:,.2f}"),
                    textposition="outside"
                ))
                fig_dia_cartao.add_hline(
                    y=media_dia_uso,
                    line_dash="dash",
                    line_color="#f59e0b",
                    annotation_text=f"Média: R$ {media_dia_uso:,.2f}",
                    annotation_position="top right"
                )
                fig_dia_cartao.update_layout(
                    template="plotly_dark",
                    title="Gastos no Cartão por Dia de Compra",
                    height=300,
                    margin=dict(l=10, r=10, t=35, b=10),
                    xaxis_title="",
                    yaxis_title="Reais (R$)",
                    showlegend=False
                )
                st.plotly_chart(fig_dia_cartao, use_container_width=True)
    else:
        st.info("💳 Nenhum cartão registrado ainda. Configure os dias de fechamento acima ou realize um lançamento no cartão!")

# =========================================================
# TELA 2: CONFIGURAÇÃO DE RENDA, REGRAS & BACKUP (COM PDF)
# =========================================================
elif menu == "⚙️ Configurar Renda e Regras":
    st.title("Configurar Renda, Poupança e Regras")
    st.write("Defina seus valores e selecione como o aplicativo deve recalcular suas despesas.")

    with st.form("form_config"):
        nova_renda = st.number_input("Renda Mensal Total (R$)", min_value=0.0, value=float(renda_mensal), step=100.0)
        nova_poupanca = st.number_input("Meta de Poupança / Reserva (R$)", min_value=0.0, value=float(meta_poupanca), step=50.0)

        opcao_regra = st.radio(
            "Se você estourar o limite de um dia, o que deve acontecer?",
            [
                "Rebalancear Dias Restantes (Reduz o limite diário dos próximos dias para compensar)",
                "Abater do Fim do Mês (Mantém a meta diária fixa, mas os últimos dias do mês ficam sem saldo)"
            ],
            index=0 if modo_ajuste == "rebalancear" else 1
        )

        salvar = st.form_submit_button("Salvar Configurações")
        if salvar:
            modo_bd = "rebalancear" if "Rebalancear" in opcao_regra else "abater_fim"
            cursor.execute("""
                INSERT INTO metas_mensais (ano, mes, renda, poupanca, modo_ajuste)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ano, mes) DO UPDATE SET
                    renda=excluded.renda,
                    poupanca=excluded.poupanca,
                    modo_ajuste=excluded.modo_ajuste
            """, (ano_atual, mes_num, nova_renda, nova_poupanca, modo_bd))
            conn.commit()
            st.success("Configurações salvas!")
            st.rerun()

    st.divider()

    st.subheader("📥 Exportação e Backup dos Dados (PDF & CSV / Excel)")
    st.caption("Baixe relatórios executivos formatados em PDF ou planilhas para backup:")

    df_todos_gastos = pd.read_sql_query("SELECT * FROM gastos_diarios ORDER BY ano DESC, mes DESC, dia ASC", conn)
    df_todos_fixos = pd.read_sql_query("SELECT * FROM despesas_fixas", conn)

    st.markdown("##### 📄 Relatórios Prontos em PDF")

    if not REPORTLAB_DISPONIVEL:
        st.warning("⚠️ Para ativar a geração de relatórios em PDF, certifique-se de que `reportlab` está presente no `requirements.txt` do seu GitHub.")
    else:
        col_pdf1, col_pdf2 = st.columns(2)
        with col_pdf1:
            if not df_gastos.empty:
                pdf_gastos_bytes = gerar_pdf_gastos(df_gastos, mes_selecionado, ano_atual)
                st.download_button(
                    label=f"📄 Baixar PDF de Gastos ({mes_selecionado}/{ano_atual})",
                    data=pdf_gastos_bytes,
                    file_name=f"relatorio_gastos_{mes_selecionado}_{ano_atual}.pdf",
                    mime="application/pdf"
                )
            else:
                st.info(f"Nenhum gasto registrado em {mes_selecionado}/{ano_atual} para gerar PDF.")

        with col_pdf2:
            if not df_todos_fixos.empty:
                pdf_fixos_bytes = gerar_pdf_fixos(df_todos_fixos)
                st.download_button(
                    label="📄 Baixar PDF de Despesas Fixas e Parcelas",
                    data=pdf_fixos_bytes,
                    file_name=f"relatorio_despesas_fixas_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf"
                )
            else:
                st.info("Nenhuma despesa fixa cadastrada para gerar PDF.")

    st.write("")

    st.markdown("##### 📊 Planilhas para Backup (CSV / Excel)")
    col_bk1, col_bk2 = st.columns(2)
    with col_bk1:
        if not df_todos_gastos.empty:
            csv_gastos = df_todos_gastos.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Baixar Todos os Gastos Diários (.csv)",
                data=csv_gastos,
                file_name=f"backup_gastos_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhum gasto registrado para exportar.")

    with col_bk2:
        if not df_todos_fixos.empty:
            csv_fixos = df_todos_fixos.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📊 Baixar Despesas Fixas e Parcelas (.csv)",
                data=csv_fixos,
                file_name=f"backup_fixos_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhuma despesa fixa registrada para exportar.")

# =========================================================
# TELA 3: LANÇAMENTO DE GASTOS DIÁRIOS
# =========================================================
elif menu == "💸 Lançar Gasto Diário":
    st.title("Registrar Gasto Diário")

    st.subheader("Novo Lançamento Diário")
    col_d, col_c = st.columns([1, 2])
    with col_d:
        dia_sel = st.number_input(
            "Dia do Mês",
            min_value=1,
            max_value=dias_no_mes,
            value=min(date.today().day, dias_no_mes),
            step=1,
            key="gasto_dia_num"
        )
    with col_c:
        lista_categorias = [
            "🍔 Alimentação",
            "🚗 Transporte",
            "🛒 Supermercado",
            "🍿 Lazer",
            "💊 Saúde",
            "🏠 Moradia / Contas",
            "✏️ Outra / Personalizar"
        ]
        cat_sel = st.selectbox("Categoria", lista_categorias, key="gasto_cat_sel")

    cat_custom = ""
    if "Personalizar" in cat_sel:
        cat_custom = st.text_input("Digite o nome da categoria personalizada:", key="gasto_cat_custom")

    desc = st.text_input("Descrição do Gasto (ex: Almoço no shopping, Combustível, Farmácia)", key="gasto_desc_input")

    col_v, col_p = st.columns([1, 1])
    with col_v:
        val = st.number_input("Valor da Despesa (R$)", min_value=0.5, step=5.0, key="gasto_val_input")
    with col_p:
        forma_pag = st.selectbox(
            "Forma de Pagamento",
            ["PIX", "Cartão de Crédito", "Cartão de Débito", "Dinheiro"],
            key="gasto_forma_pag_input"
        )

    cartao_banco_final = ""
    if "Cartão" in forma_pag:
        st.markdown("##### 💳 Qual cartão/banco foi utilizado?")
        cursor.execute("SELECT DISTINCT cartao_banco FROM gastos_diarios WHERE cartao_banco IS NOT NULL AND cartao_banco != ''")
        usados_g = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT cartao_banco FROM despesas_fixas WHERE cartao_banco IS NOT NULL AND cartao_banco != ''")
        usados_f = [r[0] for r in cursor.fetchall()]

        bancos_padrao = ["Nubank", "Inter", "Itaú", "Bradesco", "Santander", "C6 Bank", "Banco do Brasil", "Caixa"]
        lista_opcoes_cartao = sorted(list(set(bancos_padrao + usados_g + usados_f + list(cfgs_map.keys()))))
        lista_opcoes_cartao.append("✏️ Digitar outro banco / cartão...")

        cartao_escolhido = st.selectbox("Selecione o Cartão / Banco", lista_opcoes_cartao, key="gasto_cartao_sel")
        if "Digitar outro" in cartao_escolhido:
            cartao_banco_final = st.text_input("Escreva o nome do Cartão / Banco (ex: XP, Sicredi):", key="gasto_cartao_outro")
        else:
            cartao_banco_final = cartao_escolhido

        if cartao_banco_final in cfgs_map and "Crédito" in forma_pag:
            fech_d, venc_d = cfgs_map[cartao_banco_final]
            if int(dia_sel) >= fech_d:
                st.info(f"💡 **Ciclo do Cartão:** Como este lançamento é no dia {int(dia_sel):02d} (a partir do corte dia {fech_d:02d}), entrará na **fatura do próximo mês** (vencimento dia {venc_d:02d})!")
            else:
                st.caption(f"📌 Lançamento antes do fechamento (dia {fech_d:02d}). Entrará na fatura deste mês.")

    if st.button("Confirmar Despesa", type="primary", key="btn_conf_despesa"):
        categoria_final = cat_custom.strip() if ("Personalizar" in cat_sel and cat_custom.strip()) else cat_sel
        if desc.strip() == "":
            st.warning("Preencha a descrição do gasto.")
        elif "Personalizar" in cat_sel and cat_custom.strip() == "":
            st.warning("Por favor, digite o nome da categoria personalizada.")
        elif "Cartão" in forma_pag and cartao_banco_final.strip() == "":
            st.warning("Por favor, informe qual cartão/banco foi utilizado.")
        else:
            cursor.execute("""
                INSERT INTO gastos_diarios (ano, mes, dia, descricao, categoria, valor, forma_pagamento, cartao_banco)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (ano_atual, mes_num, int(dia_sel), desc, categoria_final, val, forma_pag, cartao_banco_final.strip()))
            conn.commit()
            st.success(f"Despesa de R$ {val:,.2f} no Dia {int(dia_sel):02d} registrada com sucesso!")
            st.rerun()

    st.divider()

    st.subheader("Histórico de Gastos Deste Mês")
    if not df_gastos.empty:
        df_exibir = df_gastos.copy()

        def tag_fatura_hist(r):
            forma = str(r.get('forma_pagamento', 'PIX'))
            cartao = str(r.get('cartao_banco', '')).strip() if pd.notna(r.get('cartao_banco')) else ''
            if "Cartão" in forma and cartao:
                if cartao in cfgs_map and "Crédito" in forma:
                    dia_corte = cfgs_map[cartao][0]
                    if int(r['dia']) >= dia_corte:
                        return f"{forma} ({cartao}) ⏩ Próx. Fat."
                    else:
                        return f"{forma} ({cartao}) 📌 Fat. Atual"
                return f"{forma} ({cartao})"
            return forma

        df_exibir["Pagamento"] = df_exibir.apply(tag_fatura_hist, axis=1)
        tabela_gastos = df_exibir[["dia", "descricao", "categoria", "Pagamento", "valor"]].copy()
        tabela_gastos.columns = ["Dia", "Descrição", "Categoria", "Forma de Pagamento", "Valor"]

        st.dataframe(
            tabela_gastos.style.format({"Valor": "R$ {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### 🗑️ Excluir Gasto Indevido")
        st.caption("Selecione um lançamento cadastrado por engano para removê-lo da sua base:")

        opcoes_para_excluir = {
            f"Dia {int(r['dia']):02d} | {r['descricao']} ({r['categoria']})" +
            (f" [{r['cartao_banco']}]" if (pd.notna(r.get('cartao_banco')) and str(r.get('cartao_banco')).strip() != '') else f" [{r.get('forma_pagamento', 'PIX')}]") +
            f" — R$ {r['valor']:,.2f} (Cód #{r['id']})": int(r['id'])
            for _, r in df_gastos.iterrows()
        }

        item_selecionado = st.selectbox(
            "Selecione o gasto a ser apagado:",
            options=list(opcoes_para_excluir.keys()),
            key="select_apagar_gasto"
        )

        if st.button("Remover Este Lançamento", type="secondary"):
            id_remover = opcoes_para_excluir[item_selecionado]
            cursor.execute("DELETE FROM gastos_diarios WHERE id = ?", (id_remover,))
            conn.commit()
            st.success("Lançamento removido com sucesso!")
            st.rerun()
    else:
        st.info("Nenhum gasto avulso registrado neste mês ainda.")

# =========================================================
# TELA 4: GASTOS FIXOS E PARCELAS
# =========================================================
elif menu == "📌 Gastos Fixos & Parcelas":
    st.title("Despesas Fixas e Parcelamentos")

    st.subheader("Novo Lançamento Fixo / Parcela")
    f_nome = st.text_input("Nome da Conta (ex: Aluguel, Parcela Notebook, Academia)", key="fixo_nome_input")

    c1, c2 = st.columns([1, 1])
    with c1:
        f_val = st.number_input("Valor Mensal (R$)", min_value=1.0, step=10.0, key="fixo_val_input")
    with c2:
        f_tipo = st.selectbox("Tipo de Conta", ["Fixo Contínuo", "Parcelamento"], key="fixo_tipo_input")

    p_at = 1
    p_tot = 1
    if "Parcelamento" in f_tipo:
        cp1, cp2 = st.columns(2)
        with cp1:
            p_at = cp1.number_input("Parcela Atual", min_value=1, value=1, key="fixo_pat_input")
        with cp2:
            p_tot = cp2.number_input("Total de Parcelas", min_value=1, value=1, key="fixo_ptot_input")

    f_forma_pag = st.selectbox(
        "Forma de Pagamento",
        ["Boleto / Débito em Conta", "Cartão de Crédito", "PIX", "Dinheiro"],
        key="fixo_forma_pag_input"
    )

    f_cartao_banco_final = ""
    if "Cartão" in f_forma_pag:
        st.markdown("##### 💳 Qual cartão de crédito foi utilizado?")
        cursor.execute("SELECT DISTINCT cartao_banco FROM gastos_diarios WHERE cartao_banco IS NOT NULL AND cartao_banco != ''")
        usados_g = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT cartao_banco FROM despesas_fixas WHERE cartao_banco IS NOT NULL AND cartao_banco != ''")
        usados_f = [r[0] for r in cursor.fetchall()]

        bancos_padrao = ["Nubank", "Inter", "Itaú", "Bradesco", "Santander", "C6 Bank", "Banco do Brasil", "Caixa"]
        lista_opcoes_cartao_fix = sorted(list(set(bancos_padrao + usados_g + usados_f + list(cfgs_map.keys()))))
        lista_opcoes_cartao_fix.append("✏️ Digitar outro banco / cartão...")

        f_cartao_escolhido = st.selectbox("Selecione o Cartão / Banco", lista_opcoes_cartao_fix, key="fixo_cartao_sel")
        if "Digitar outro" in f_cartao_escolhido:
            f_cartao_banco_final = st.text_input("Escreva o nome do Cartão / Banco:", key="fixo_cartao_outro")
        else:
            f_cartao_banco_final = f_cartao_escolhido

    if st.button("Salvar Despesa Fixa", type="primary", key="btn_salvar_fixo"):
        if f_nome.strip() == "":
            st.warning("Preencha o nome da conta.")
