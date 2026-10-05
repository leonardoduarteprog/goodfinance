import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Dashboard Finanças",
    page_icon="🟣",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILIZAÇÃO CSS (Dark Glow inspirado na referência) ---
st.markdown("""
<style>
    /* Fundo escuro geral */
    .stApp {
        background-color: #0b0d13;
        color: #f1f5f9;
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
    }
    
    /* Cartões de métricas personalizados */
    .card-metric {
        background: linear-gradient(145deg, #161922, #11131a);
        border: 1px solid #232734;
        border-radius: 12px;
        padding: 16px 20px;
        box-shadow: 0 4px 15px rgba(0, 0, 0, 0.4);
        margin-bottom: 12px;
    }
    .metric-title {
        color: #94a3b8;
        font-size: 13px;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        font-weight: 600;
    }
    .metric-value {
        color: #ffffff;
        font-size: 26px;
        font-weight: bold;
        margin-top: 4px;
    }
    .metric-sub {
        font-size: 11px;
        color: #38bdf8;
        margin-top: 4px;
    }
    .alert-free {
        background: rgba(16, 185, 129, 0.12);
        border-left: 4px solid #10b981;
        padding: 10px 14px;
        border-radius: 6px;
        margin-top: 8px;
        font-size: 13px;
    }
</style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS LOCAL (SQLite) ---
conn = sqlite3.connect("financas.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS receitas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    valor REAL,
    dia_recebimento INTEGER,
    mes INTEGER,
    ano INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas_fixas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    valor REAL,
    tipo TEXT, -- 'fixo_puro', 'parcelamento', 'variavel_media'
    dia_vencimento INTEGER,
    parcela_atual INTEGER,
    total_parcelas INTEGER,
    mes_fim INTEGER,
    ano_fim INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS historico_variavel (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    valor REAL,
    mes INTEGER,
    ano INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas_avulsas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    categoria TEXT,
    valor REAL,
    mes INTEGER,
    ano INTEGER
)
""")
conn.commit()

# --- CARGA INICIAL DE DADOS DE EXEMPLO (se vazio) ---
cursor.execute("SELECT COUNT(*) FROM receitas")
if cursor.fetchone()[0] == 0:
    # Receitas com dias diferentes de entrada
    cursor.executemany("""
        INSERT INTO receitas (descricao, valor, dia_recebimento, mes, ano) 
        VALUES (?, ?, ?, ?, ?)
    """, [
        ("Salário Principal", 6500.0, 5, 10, 2026),
        ("Renda Extra / Plantão", 2200.0, 20, 10, 2026),
        ("Salário Esposa", 4800.0, 10, 10, 2026),
    ])
    
    # Fixos contínuos e parcelamentos com previsão de término
    cursor.executemany("""
        INSERT INTO despesas_fixas (descricao, valor, tipo, dia_vencimento, parcela_atual, total_parcelas, mes_fim, ano_fim)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        ("Aluguel + Condomínio", 2400.0, "fixo_puro", 10, 0, 0, 0, 0),
        ("Internet Fibra", 129.90, "fixo_puro", 15, 0, 0, 0, 0),
        ("Parcela Sofá (10x)", 340.0, "parcelamento", 8, 8, 10, 12, 2026),
        ("Parcela Notebook (12x)", 480.0, "parcelamento", 15, 11, 12, 11, 2026),
    ])
    
    # Histórico de consumo para médias (Energia e Água)
    cursor.executemany("""
        INSERT INTO historico_variavel (descricao, valor, mes, ano)
        VALUES (?, ?, ?, ?)
    """, [
        ("Energia Elétrica", 340.0, 7, 2026),
        ("Energia Elétrica", 380.0, 8, 2026),
        ("Energia Elétrica", 360.0, 9, 2026),
        ("Energia Elétrica", 355.0, 10, 2026),
        ("Água / Saneamento", 110.0, 7, 2026),
        ("Água / Saneamento", 125.0, 8, 2026),
        ("Água / Saneamento", 118.0, 9, 2026),
        ("Água / Saneamento", 120.0, 10, 2026),
    ])
    
    # Gastos avulsos do mês
    cursor.executemany("""
        INSERT INTO despesas_avulsas (descricao, categoria, valor, mes, ano)
        VALUES (?, ?, ?, ?, ?)
    """, [
        ("Supermercado Mensal", "Subsistência", 1650.0, 10, 2026),
        ("Combustível", "Transporte", 450.0, 10, 2026),
        ("Restaurantes & Lazer", "Lazer", 820.0, 10, 2026),
        ("Farmácia", "Saúde", 210.0, 10, 2026),
        ("Streaming / Jogos", "Lazer", 145.0, 10, 2026),
    ])
    conn.commit()

# --- SIDEBAR (NAVEGAÇÃO IGUAL AO DASHBOARD) ---
st.sidebar.markdown("### 🟣 Finanças Pessoais")
ano_selecionado = st.sidebar.selectbox("Ano de Referência", [2025, 2026, 2027], index=1)

meses_nomes = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
mes_nome = st.sidebar.radio("Selecione o Mês", meses_nomes, index=9)
mes_num = meses_nomes.index(mes_nome) + 1

menu = st.sidebar.radio("Menu", ["📊 Dashboard Geral", "➕ Lançamentos & Parcelas"])

# --- CONSULTAS DOS DADOS FILTRADOS ---
# 1. Receitas do mês
df_rec = pd.read_sql_query(
    "SELECT descricao, valor, dia_recebimento FROM receitas WHERE mes = ? AND ano = ? ORDER BY dia_recebimento ASC",
    conn, params=(mes_num, ano_selecionado)
)
total_receitas = df_rec["valor"].sum() if not df_rec.empty else 0.0

# 2. Despesas Fixas & Parcelamentos
df_fixos = pd.read_sql_query(
    "SELECT descricao, valor, tipo, dia_vencimento, parcela_atual, total_parcelas, mes_fim, ano_fim FROM despesas_fixas",
    conn
)
total_fixos_puros = df_fixos[df_fixos["tipo"] == "fixo_puro"]["valor"].sum()
total_parcelamentos = df_fixos[df_fixos["tipo"] == "parcelamento"]["valor"].sum()

# 3. Contas Variáveis com cálculo de média
df_variaveis = pd.read_sql_query(
    "SELECT descricao, AVG(valor) as media_estimada, COUNT(valor) as total_meses FROM historico_variavel GROUP BY descricao",
    conn
)
total_variaveis_estimado = df_variaveis["media_estimada"].sum() if not df_variaveis.empty else 0.0

# 4. Despesas Avulsas do mês
df_avulsos = pd.read_sql_query(
    "SELECT descricao, categoria, valor FROM despesas_avulsas WHERE mes = ? AND ano = ?",
    conn, params=(mes_num, ano_selecionado)
)
total_avulsos = df_avulsos["valor"].sum() if not df_avulsos.empty else 0.0

total_despesas_mes = total_fixos_puros + total_parcelamentos + total_variaveis_estimado + total_avulsos
saldo_mes = total_receitas - total_despesas_mes

# --- TELA 1: DASHBOARD GERAL ---
if menu == "📊 Dashboard Geral":
    st.title(f"Visão Geral — {mes_nome} de {ano_selecionado}")

    # CARDS SUPERIORES
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="card-metric" style="border-top: 3px solid #3b82f6;">
            <div class="metric-title">Saldo Líquido Previsto</div>
            <div class="metric-value">R$ {saldo_mes:,.2f}</div>
            <div class="metric-sub">Receita menos despesas estimadas</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="card-metric" style="border-top: 3px solid #ec4899;">
            <div class="metric-title">Despesas Totais do Mês</div>
            <div class="metric-value">R$ {total_despesas_mes:,.2f}</div>
            <div class="metric-sub">Fixos + Parcelas + Médias + Avulsos</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="card-metric" style="border-top: 3px solid #8b5cf6;">
            <div class="metric-title">Receitas Confirmadas</div>
            <div class="metric-value">R$ {total_receitas:,.2f}</div>
            <div class="metric-sub">{len(df_rec)} entradas programadas</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        pct_comprometido = (total_despesas_mes / total_receitas * 100) if total_receitas > 0 else 0
        st.markdown(f"""
        <div class="card-metric" style="border-top: 3px solid #10b981;">
            <div class="metric-title">Comprometimento de Renda</div>
            <div class="metric-value">{pct_comprometido:.1f}%</div>
            <div class="metric-sub">Taxa de consumo mensal</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # SEÇÃO INTERMEDIÁRIA: DIAS DE ENTRADA & PARCELAS A TERMINAR
    c_rec_dias, c_parc_aviso = st.columns([1, 1])

    with c_rec_dias:
        st.subheader("📅 Entradas por Dia no Mês")
        if not df_rec.empty:
            for _, r in df_rec.iterrows():
                st.markdown(f"""
                <div style="background:#161922; padding:10px 14px; border-radius:8px; margin-bottom:6px; display:flex; justify-content:space-between; align-items:center; border:1px solid #232734;">
                    <div>
                        <span style="background:#3b82f6; color:#fff; padding:2px 8px; border-radius:4px; font-weight:bold; font-size:12px;">Dia {int(r['dia_recebimento']):02d}</span>
                        <strong style="margin-left:10px;">{r['descricao']}</strong>
                    </div>
                    <span style="color:#10b981; font-weight:bold;">+ R$ {r['valor']:,.2f}</span>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Nenhuma receita registrada neste mês.")

    with c_parc_aviso:
        st.subheader("⏳ Parcelamentos & Dinheiro Liberado")
        df_parc = df_fixos[df_fixos["tipo"] == "parcelamento"]
        if not df_parc.empty:
            for _, p in df_parc.iterrows():
                fim_txt = f"{meses_nomes[int(p['mes_fim'])-1]}/{int(p['ano_fim'])}"
                restantes = int(p['total_parcelas']) - int(p['parcela_atual'])
                st.markdown(f"""
                <div style="background:#161922; padding:12px; border-radius:8px; margin-bottom:8px; border:1px solid #232734;">
                    <div style="display:flex; justify-content:space-between;">
                        <strong>{p['descricao']}</strong>
                        <span style="color:#f43f5e; font-weight:bold;">R$ {p['valor']:,.2f}/mês</span>
                    </div>
                    <div style="font-size:12px; color:#94a3b8; margin-top:4px;">
                        Parcela {int(p['parcela_atual'])} de {int(p['total_parcelas'])} ({restantes} restantes)
                    </div>
                    <div class="alert-free">
                        ✅ Acaba em <b>{fim_txt}</b>! A partir daí, sobrará <b>R$ {p['valor']:,.2f}/mês</b> no seu orçamento.
                    </div>
                </div>
                """, unsafe_allow_html=True)
        else:
            st.info("Nenhum parcelamento ativo cadastrado.")

    st.write("")

    # SEÇÃO INFERIOR: GRÁFICOS NO ESTILO DO PAINEL
    g_col1, g_col2 = st.columns([1.2, 1])

    with g_col1:
        st.subheader("📊 Comparativo de Categorias")
        
        # Consolida categorias de todas as despesas
        cat_data = [
            {"Categoria": "Fixos (Aluguel/Net)", "Valor": total_fixos_puros},
            {"Categoria": "Parcelamentos Ativos", "Valor": total_parcelamentos},
            {"Categoria": "Consumo Variável (Média)", "Valor": total_variaveis_estimado},
        ]
        for _, av in df_avulsos.iterrows():
            cat_data.append({"Categoria": av["categoria"], "Valor": av["valor"]})
        
        df_cat = pd.DataFrame(cat_data).groupby("Categoria")["Valor"].sum().reset_index()

        fig_bar = px.bar(
            df_cat,
            x="Valor",
            y="Categoria",
            orientation="h",
            color="Valor",
            color_continuous_scale=["#6366f1", "#ec4899"],
            text_auto=".2s"
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#cbd5e1",
            height=320,
            margin=dict(l=0, r=20, t=10, b=10),
            coloraxis_showscale=False
        )
        fig_bar.update_xaxes(gridcolor="#1e2230")
        fig_bar.update_yaxes(gridcolor="#1e2230")
        st.plotly_chart(fig_bar, use_container_width=True)

    with g_col2:
        st.subheader("🍩 Distribuição das Despesas")
        fig_donut = px.pie(
            df_cat,
            values="Valor",
            names="Categoria",
            hole=0.6,
            color_discrete_sequence=["#3b82f6", "#8b5cf6", "#ec4899", "#10b981", "#f59e0b"]
        )
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font_color="#cbd5e1",
            height=320,
            margin=dict(l=0, r=0, t=10, b=10),
            legend=dict(orientation="h", y=-0.1)
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    st.write("")
    
    # SEÇÃO DE MÉDIAS DE CONSUMO (Água, Energia, etc.)
    st.subheader("⚡ Contas de Consumo com Média Histórica")
    m_cols = st.columns(len(df_variaveis) if not df_variaveis.empty else 1)
    if not df_variaveis.empty:
        for idx, row in df_variaveis.iterrows():
            with m_cols[idx]:
                st.markdown(f"""
                <div class="card-metric" style="border-left: 4px solid #f59e0b;">
                    <div class="metric-title">{row['descricao']}</div>
                    <div class="metric-value">R$ {row['media_estimada']:,.2f}</div>
                    <div class="metric-sub">Média calculada sobre {int(row['total_meses'])} faturas registradas</div>
                </div>
                """, unsafe_allow_html=True)
    else:
        st.info("Cadastre lançamentos de contas variáveis para calcular a média histórica.")

# --- TELA 2: LANÇAMENTOS E CADASTROS ---
else:
    st.title("➕ Cadastrar e Gerenciar Contas")
    
    aba1, aba2, aba3, aba4 = st.tabs([
        "💰 Nova Receita", 
        "⏳ Novo Parcelamento", 
        "⚡ Conta de Consumo (Média)", 
        "🛒 Despesa Avulsa"
    ])

    with aba1:
        st.markdown("##### Registrar Receita Mensal")
        with st.form("form_rec", clear_on_submit=True):
            rec_desc = st.text_input("Descrição (ex: Salário Leonardo, Salário Esposa, Freelance)")
            rec_val = st.number_input("Valor da Entrada (R$)", min_value=1.0, step=50.0)
            rec_dia = st.slider("Dia do Mês em que o dinheiro cai na conta", min_value=1, max_value=31, value=5)
            
            if st.form_submit_button("Salvar Receita"):
                cursor.execute("""
                    INSERT INTO receitas (descricao, valor, dia_recebimento, mes, ano)
                    VALUES (?, ?, ?, ?, ?)
                """, (rec_desc, rec_val, rec_dia, mes_num, ano_selecionado))
                conn.commit()
                st.success("Receita cadastrada com sucesso!")
                st.rerun()

    with aba2:
        st.markdown("##### Cadastrar Compra Parcelada com Previsão de Término")
        with st.form("form_parc", clear_on_submit=True):
            p_desc = st.text_input("Descrição (ex: Financiamento Carro, Celular novo, Móveis)")
            p_val = st.number_input("Valor da Parcela Mensal (R$)", min_value=1.0, step=10.0)
            p_dia = st.slider("Dia de Vencimento da Fatura", 1, 31, 10)
            
            c_p1, c_p2 = st.columns(2)
            p_atual = c_p1.number_input("Parcela Atual (ex: 3)", min_value=1, value=1)
            p_total = c_p2.number_input("Total de Parcelas (ex: 12)", min_value=1, value=12)
            
            c_f1, c_f2 = st.columns(2)
            p_mes_fim = c_f1.selectbox("Mês em que termina", range(1, 13), format_func=lambda x: meses_nomes[x-1], index=mes_num-1)
            p_ano_fim = c_f2.selectbox("Ano em que termina", [2026, 2027, 2028, 2029], index=0)

            if st.form_submit_button("Salvar Parcelamento"):
                cursor.execute("""
                    INSERT INTO despesas_fixas (descricao, valor, tipo, dia_vencimento, parcela_atual, total_parcelas, mes_fim, ano_fim)
                    VALUES (?, ?, 'parcelamento', ?, ?, ?, ?, ?)
                """, (p_desc, p_val, p_dia, p_atual, p_total, p_mes_fim, p_ano_fim))
                conn.commit()
                st.success("Parcelamento salvo com sucesso!")
                st.rerun()

    with aba3:
        st.markdown("##### Registrar Conta de Consumo Variável (para alimentar a média)")
        with st.form("form_var", clear_on_submit=True):
            v_desc = st.selectbox("Tipo de Conta", ["Energia Elétrica", "Água / Saneamento", "Gás", "Combustível Mensal"])
            v_val = st.number_input("Valor da Fatura deste mês (R$)", min_value=1.0, step=10.0)
            
            if st.form_submit_button("Lançar Fatura no Histórico"):
                cursor.execute("""
                    INSERT INTO historico_variavel (descricao, valor, mes, ano)
                    VALUES (?, ?, ?, ?)
                """, (v_desc, v_val, mes_num, ano_selecionado))
                conn.commit()
                st.success("Fatura salva! A média foi atualizada automaticamente.")
                st.rerun()

    with aba4:
        st.markdown("##### Registrar Despesa Avulsa / Diária")
        with st.form("form_avulso", clear_on_submit=True):
            a_desc = st.text_input("Item / Estabelecimento")
            a_cat = st.selectbox("Categoria", ["Subsistência", "Moradia", "Transporte", "Saúde", "Lazer", "Vestuário", "Outros"])
            a_val = st.number_input("Valor Pago (R$)", min_value=0.5, step=5.0)

            if st.form_submit_button("Registrar Despesa"):
                cursor.execute("""
                    INSERT INTO despesas_avulsas (descricao, categoria, valor, mes, ano)
                    VALUES (?, ?, ?, ?, ?)
                """, (a_desc, a_cat, a_val, mes_num, ano_selecionado))
                conn.commit()
                st.success("Despesa avulsa registrada!")
                st.rerun()
