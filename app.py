import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime, date
import plotly.graph_objects as go
import plotly.express as px

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
                """, (ano_atual, mes_num, int(q_dia), q_desc.strip(), cat_final, q_val, q_forma, q_cartao.strip()))
                conn.commit()
                st.success(f"Despesa de R$ {q_val:,.2f} no Dia {int(q_dia):02d} registrada com sucesso!")
                st.rerun()

    st.write("")

    # CARDS PRINCIPAIS
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #3b82f6;">
            <div class="metric-label">Orçamento Livre Inicial</div>
            <div class="metric-num">R$ {saldo_livre_mes:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #f43f5e;">
            <div class="metric-label">Total Gasto Até Agora</div>
            <div class="metric-num">R$ {total_gasto_real:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        cor_cx = "#10b981" if saldo_restante_caixa >= 0 else "#ef4444"
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid {cor_cx};">
            <div class="metric-label">Saldo Disponível em Caixa</div>
            <div class="metric-num">R$ {saldo_restante_caixa:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        regra_nome = "Rebalanceamento" if modo_ajuste == "rebalancear" else "Corte no Fim"
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #8b5cf6;">
            <div class="metric-label">Regra de Ajuste</div>
            <div class="metric-num" style="font-size: 16px; margin-top: 8px;">{regra_nome}</div>
        </div>
        """, unsafe_allow_html=True)

    if dia_negativo:
        st.markdown(f"""
        <div class="danger-box">
            🚨 <b>Atenção:</b> Seu saldo livre ficou negativo no <b>Dia {dia_negativo:02d}</b>! 
            Você já gastou mais do que o planejado para o mês. Saldo restante atual: <b>R$ {saldo_restante_caixa:,.2f}</b>.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="success-box">
            ✅ <b>Dentro do planejado:</b> Você ainda possui <b>R$ {saldo_restante_caixa:,.2f}</b> livres para gastar até o final de {mes_selecionado}.
        </div>
        """, unsafe_allow_html=True)

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
                st.markdown(f"""
                <div class="top-item-box">
                    <div>
                        <span style="background:#232734; color:#38bdf8; padding:2px 8px; border-radius:4px; font-size:11px; font-weight:bold;">Dia {int(r_top['dia']):02d}</span>
                        <b style="margin-left:6px; font-size:14px;">{r_top['descricao']}</b>
                        <div style="font-size:11px; color:#94a3b8; margin-top:2px;">{r_top['categoria']} • {pag_txt}</div>
                    </div>
                    <span style="color:#f43f5e; font-weight:bold; font-size:15px;">R$ {r_top['valor']:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)
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

    # --- SEÇÃO DE CARTÕES DE CRÉDITO E DÉBITO ---
    st.subheader("💳 Raio-X dos Gastos nos Cartões")

    df_cartoes = df_gastos[df_gastos["forma_pagamento"].str.contains("Cartão", na=False)].copy()

    if not df_cartoes.empty:
        df_cartoes["cartao_banco"] = df_cartoes["cartao_banco"].apply(
            lambda x: x.strip() if pd.notna(x) and str(x).strip() != '' else 'Outro / Não Definido'
        )

        total_cartoes = df_cartoes["valor"].sum()
        dias_com_cartao = df_cartoes["dia"].nunique()
        media_dia_uso = (total_cartoes / dias_com_cartao) if dias_com_cartao > 0 else 0.0

        c_c1, c_c2, c_c3 = st.columns(3)
        with c_c1:
            st.markdown(f"""
            <div class="metric-card" style="border-top: 3px solid #8b5cf6;">
                <div class="metric-label">Total Gasto em Cartões</div>
                <div class="metric-num">R$ {total_cartoes:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_c2:
            cartao_top = df_cartoes.groupby("cartao_banco")["valor"].sum().idxmax()
            st.markdown(f"""
            <div class="metric-card" style="border-top: 3px solid #ec4899;">
                <div class="metric-label">Cartão Mais Utilizado</div>
                <div class="metric-num" style="font-size: 19px;">{cartao_top}</div>
            </div>
            """, unsafe_allow_html=True)
        with c_c3:
            st.markdown(f"""
            <div class="metric-card" style="border-top: 3px solid #06b6d4;">
                <div class="metric-label">Média por Dia de Compra</div>
                <div class="metric-num">R$ {media_dia_uso:,.2f}</div>
            </div>
            """, unsafe_allow_html=True)

        col_g1, col_g2 = st.columns(2)

        with col_g1:
            tot_por_cartao = df_cartoes.groupby("cartao_banco")["valor"].sum().reset_index()
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
                title="Total por Cartão / Banco",
                height=320,
                margin=dict(l=10, r=10, t=35, b=10),
                xaxis_title="",
                yaxis_title="Total (R$)",
                showlegend=False
            )
            fig_bar_cartao.update_traces(textposition="outside")
            st.plotly_chart(fig_bar_cartao, use_container_width=True)

        with col_g2:
            dia_cartao = df_cartoes.groupby("dia")["valor"].sum().reset_index()

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
                title="Gastos no Cartão por Dia de Uso",
                height=320,
                margin=dict(l=10, r=10, t=35, b=10),
                xaxis_title="",
                yaxis_title="Reais (R$)",
                showlegend=False
            )
            st.plotly_chart(fig_dia_cartao, use_container_width=True)
    else:
        st.info("💳 Nenhum gasto em cartão registrado neste mês ainda. Ao registrar compras no cartão, os comparativos aparecerão aqui!")

# =========================================================
# TELA 2: CONFIGURAÇÃO DE RENDA, REGRAS & BACKUP
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

    # 4. SEGURANÇA E BACKUP EM CSV
    st.subheader("📥 Backup dos Dados (Exportação para Excel / CSV)")
    st.caption("Baixe uma cópia dos seus lançamentos para garantir que você nunca perca seus registros:")

    df_todos_gastos = pd.read_sql_query("SELECT * FROM gastos_diarios", conn)
    df_todos_fixos = pd.read_sql_query("SELECT * FROM despesas_fixas", conn)

    col_bk1, col_bk2 = st.columns(2)
    with col_bk1:
        if not df_todos_gastos.empty:
            csv_gastos = df_todos_gastos.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 Baixar Todos os Gastos Diários (.csv)",
                data=csv_gastos,
                file_name=f"backup_gastos_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhum gasto diário registrado ainda para exportar.")

    with col_bk2:
        if not df_todos_fixos.empty:
            csv_fixos = df_todos_fixos.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📄 Baixar Despesas Fixas e Parcelas (.csv)",
                data=csv_fixos,
                file_name=f"backup_fixos_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        else:
            st.info("Nenhuma despesa fixa registrada ainda para exportar.")

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
        lista_opcoes_cartao = sorted(list(set(bancos_padrao + usados_g + usados_f)))
        lista_opcoes_cartao.append("✏️ Digitar outro banco / cartão...")

        cartao_escolhido = st.selectbox("Selecione o Cartão / Banco", lista_opcoes_cartao, key="gasto_cartao_sel")
        if "Digitar outro" in cartao_escolhido:
            cartao_banco_final = st.text_input("Escreva o nome do Cartão / Banco (ex: XP, Sicredi):", key="gasto_cartao_outro")
        else:
            cartao_banco_final = cartao_escolhido

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
        df_exibir["Pagamento"] = df_exibir.apply(
            lambda r: f"{r['forma_pagamento']} ({r['cartao_banco']})" if (pd.notna(r.get('cartao_banco')) and str(r.get('cartao_banco')).strip() != '') else r.get('forma_pagamento', '-'),
            axis=1
        )
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
        lista_opcoes_cartao_fix = sorted(list(set(bancos_padrao + usados_g + usados_f)))
        lista_opcoes_cartao_fix.append("✏️ Digitar outro banco / cartão...")

        f_cartao_escolhido = st.selectbox("Selecione o Cartão / Banco", lista_opcoes_cartao_fix, key="fixo_cartao_sel")
        if "Digitar outro" in f_cartao_escolhido:
            f_cartao_banco_final = st.text_input("Escreva o nome do Cartão / Banco:", key="fixo_cartao_outro")
        else:
            f_cartao_banco_final = f_cartao_escolhido

    if st.button("Salvar Despesa Fixa", type="primary", key="btn_salvar_fixo"):
        if f_nome.strip() == "":
            st.warning("Preencha o nome da conta.")
        elif "Cartão" in f_forma_pag and f_cartao_banco_final.strip() == "":
            st.warning("Por favor, informe qual cartão foi utilizado.")
        else:
            tipo_bd = "Parcela" if "Parcelamento" in f_tipo else "Fixo"
            cursor.execute("""
                INSERT INTO despesas_fixas (descricao, valor, tipo, parcela_atual, total_parcelas, forma_pagamento, cartao_banco)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (f_nome, f_val, tipo_bd, int(p_at), int(p_tot), f_forma_pag, f_cartao_banco_final.strip()))
            conn.commit()
            st.success("Conta fixa cadastrada com sucesso!")
            st.rerun()

    st.divider()

    st.subheader("Contas Fixas e Parcelas Cadastradas")
    if not df_fixos.empty:
        df_mostrar_fixos = df_fixos.copy()
        df_mostrar_fixos["Parcelas"] = df_mostrar_fixos.apply(
            lambda r: f"{int(r['parcela_atual'])} / {int(r['total_parcelas'])}" if r["tipo"] == "Parcela" else "Contínuo",
            axis=1
        )
        df_mostrar_fixos["Pagamento"] = df_mostrar_fixos.apply(
            lambda r: f"{r['forma_pagamento']} ({r['cartao_banco']})" if (pd.notna(r.get('cartao_banco')) and str(r.get('cartao_banco')).strip() != '') else r.get('forma_pagamento', '-'),
            axis=1
        )
        tabela_fixos = df_mostrar_fixos[["descricao", "tipo", "valor", "Parcelas", "Pagamento"]].copy()
        tabela_fixos.columns = ["Descrição", "Tipo", "Valor Mensal", "Parcelas", "Forma de Pagamento"]

        st.dataframe(
            tabela_fixos.style.format({"Valor Mensal": "R$ {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### 🗑 Cancelar / Excluir Despesa Lançada Errada")
        st.caption("Selecione um item que você lançou por engano ou que deseja encerrar:")

        opcoes_fixos_excluir = {
            f"{r['descricao']} ({r['tipo']}) — R$ {r['valor']:,.2f}" +
            (f" [{int(r['parcela_atual'])}/{int(r['total_parcelas'])}]" if r['tipo'] == 'Parcela' else "") +
            (f" [{r['cartao_banco']}]" if (pd.notna(r.get('cartao_banco')) and str(r.get('cartao_banco')).strip() != '') else "") +
            f" (Cód #{r['id']})": int(r['id'])
            for _, r in df_fixos.iterrows()
        }

        item_fixo_sel = st.selectbox(
            "Selecione a conta para apagar:",
            options=list(opcoes_fixos_excluir.keys()),
            key="select_apagar_fixo"
        )

        if st.button("Cancelar / Apagar Esta Despesa", type="secondary"):
            id_para_remover = opcoes_fixos_excluir[item_fixo_sel]
            cursor.execute("DELETE FROM despesas_fixas WHERE id = ?", (id_para_remover,))
            conn.commit()
            st.success("Conta removida com sucesso! O orçamento livre foi recalculado.")
            st.rerun()
    else:
        st.info("Nenhuma despesa fixa ou parcelamento cadastrado no momento.")

# =========================================================
# TELA 5: PATRIMÔNIO & PROJEÇÃO
# =========================================================
elif menu == "💰 Patrimônio":
    st.title("Gestão de Patrimônio e Projeção de Reserva")

    cursor.execute("SELECT saldo_inicial FROM patrimonio_base WHERE id = 1")
    row_base = cursor.fetchone()
    patrimonio_inicial = row_base[0] if row_base else 0.0

    df_aportes = pd.read_sql_query("SELECT ano, mes, valor, data_consolidacao FROM aportes_consolidados", conn)
    total_aportado_historico = df_aportes["valor"].sum() if not df_aportes.empty else 0.0
    patrimonio_atual_total = patrimonio_inicial + total_aportado_historico

    cursor.execute("SELECT valor FROM aportes_consolidados WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
    row_aporte_mes = cursor.fetchone()
    aporte_consolidado_mes = row_aporte_mes[0] if row_aporte_mes else None

    c_p1, c_p2, c_p3 = st.columns(3)
    with c_p1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #10b981;">
            <div class="metric-label">Patrimônio Atual Consolidado</div>
            <div class="metric-num">R$ {patrimonio_atual_total:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c_p2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #3b82f6;">
            <div class="metric-label">Patrimônio Inicial Declarado</div>
            <div class="metric-num">R$ {patrimonio_inicial:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c_p3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #8b5cf6;">
            <div class="metric-label">Total Poupado & Consolidado</div>
            <div class="metric-num">R$ {total_aportado_historico:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    st.subheader("1. Definir Patrimônio Inicial")
    st.caption("Informe quanto você já tem guardado/investido hoje (deixe 0 se estiver começando do zero):")

    with st.form("form_patrimonio_base"):
        novo_inicial = st.number_input(
            "Patrimônio Inicial (R$)",
            min_value=0.0,
            value=float(patrimonio_inicial),
            step=100.0
        )
        if st.form_submit_button("Atualizar Patrimônio Inicial"):
            cursor.execute("UPDATE patrimonio_base SET saldo_inicial = ? WHERE id = 1", (novo_inicial,))
            conn.commit()
            st.success("Patrimônio inicial atualizado com sucesso!")
            st.rerun()

    st.divider()

    st.subheader(f"2. Fechamento de {mes_selecionado}/{ano_atual}")
    st.caption("Ao finalizar o mês, transfira o que você realmente conseguiu poupar para somar ao seu patrimônio:")

    if aporte_consolidado_mes is not None:
        st.info(f"✅ O mês de **{mes_selecionado}/{ano_atual}** já foi consolidado com um aporte de **R$ {aporte_consolidado_mes:,.2f}** no patrimônio.")
        if st.button("Desfazer / Remover Consolidação deste Mês"):
            cursor.execute("DELETE FROM aportes_consolidados WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
            conn.commit()
            st.success("Consolidação removida.")
            st.rerun()
    else:
        with st.form("form_consolidar_mes"):
            sugestao_poupanca = float(meta_poupanca)
            valor_consolidar = st.number_input(
                f"Valor poupado em {mes_selecionado}/{ano_atual} a adicionar ao patrimônio (R$)",
                min_value=0.0,
                value=sugestao_poupanca,
                step=50.0
            )
            if st.form_submit_button("Confirmar e Somar ao Patrimônio"):
                data_hoje_str = str(date.today())
                cursor.execute("""
                    INSERT INTO aportes_consolidados (ano, mes, valor, data_consolidacao)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(ano, mes) DO UPDATE SET valor = excluded.valor, data_consolidacao = excluded.data_consolidacao
                """, (ano_atual, mes_num, valor_consolidar, data_hoje_str))
                conn.commit()
                st.success(f"Excelente! R$ {valor_consolidar:,.2f} adicionados ao seu patrimônio!")
                st.rerun()

    st.divider()

    st.subheader(f"3. Projeção Patrimonial — Ano de {ano_atual}")
    st.caption(f"Previsão mês a mês somando o patrimônio inicial com aportes realizados e projetados (Meta base: R$ {meta_poupanca:,.2f}/mês):")

    aportes_ano_map = {}
    if not df_aportes.empty:
        df_ano_atual = df_aportes[df_aportes["ano"] == ano_atual]
        aportes_ano_map = dict(zip(df_ano_atual["mes"], df_ano_atual["valor"]))

    acumulado_proj = patrimonio_inicial
    dados_proj = []

    for m_i, m_n in enumerate(meses_nomes, start=1):
        if m_i in aportes_ano_map:
            val_aporte = aportes_ano_map[m_i]
            tipo_status = "✅ Consolidado"
        else:
            val_aporte = meta_poupanca
            tipo_status = "🔮 Projetado"

        acumulado_proj += val_aporte
        dados_proj.append({
            "Mês": m_n,
            "m_num": m_i,
            "Situação": tipo_status,
            "Poupança / Aporte (R$)": val_aporte,
            "Patrimônio Acumulado (R$)": acumulado_proj
        })

    df_proj_tabela = pd.DataFrame(dados_proj)

    fig_proj = go.Figure()
    fig_proj.add_trace(go.Scatter(
        x=df_proj_tabela["Mês"],
        y=df_proj_tabela["Patrimônio Acumulado (R$)"],
        mode="lines+markers",
        name="Patrimônio Total",
        line=dict(color="#10b981", width=3),
        marker=dict(size=7, color="#38bdf8")
    ))

    fig_proj.update_layout(
        template="plotly_dark",
        height=320,
        margin=dict(l=10, r=10, t=20, b=10),
        xaxis=dict(title="Mês"),
        yaxis=dict(title="Patrimônio Acumulado (R$)")
    )
    st.plotly_chart(fig_proj, use_container_width=True)

    st.dataframe(
        df_proj_tabela[["Mês", "Situação", "Poupança / Aporte (R$)", "Patrimônio Acumulado (R$)"]].style.format({
            "Poupança / Aporte (R$)": "R$ {:,.2f}",
            "Patrimônio Acumulado (R$)": "R$ {:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

    patrimonio_fim_ano = df_proj_tabela.iloc[-1]["Patrimônio Acumulado (R$)"]
    st.markdown(f"""
    <div class="success-box">
        🎯 <b>Projeção Final de {ano_atual}:</b> Mantendo sua meta de poupança, você fechará o ano com 
        <b>R$ {patrimonio_fim_ano:,.2f}</b> acumulados!
    </div>
    """, unsafe_allow_html=True)
