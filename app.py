import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime, date
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Controle Orçamentário Diário",
    page_icon="💳",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILIZAÇÃO DARK GLOW ---
st.markdown("""
<style>
    .stApp {
        background-color: #0b0d13;
        color: #f1f5f9;
        font-family: 'Segoe UI', sans-serif;
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
        font-size: 12px;
        text-transform: uppercase;
        font-weight: 600;
    }
    .metric-num {
        color: #ffffff;
        font-size: 24px;
        font-weight: bold;
        margin-top: 4px;
    }
    .danger-box {
        background: rgba(239, 68, 68, 0.15);
        border-left: 4px solid #ef4444;
        padding: 12px 16px;
        border-radius: 6px;
        color: #fca5a5;
        margin: 10px 0;
    }
    .success-box {
        background: rgba(16, 185, 129, 0.15);
        border-left: 4px solid #10b981;
        padding: 12px 16px;
        border-radius: 6px;
        color: #6ee7b7;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# --- BANCO DE DADOS (SQLite) ---
conn = sqlite3.connect("orcamento.db", check_same_thread=False)
cursor = conn.cursor()

# Configuração do mês (Renda e Meta de Poupança)
cursor.execute("""
CREATE TABLE IF NOT EXISTS metas_mensais (
    ano INTEGER,
    mes INTEGER,
    renda REAL,
    poupanca REAL,
    PRIMARY KEY (ano, mes)
)
""")

# Gastos Fixos e Parcelas
cursor.execute("""
CREATE TABLE IF NOT EXISTS despesas_fixas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    valor REAL,
    tipo TEXT, -- 'Fixo' ou 'Parcela'
    parcela_atual INTEGER,
    total_parcelas INTEGER
)
""")

# Gastos Diários / Variáveis
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
conn.commit()

# --- BARRA LATERAL: SELEÇÃO DE DATA E NAVEGAÇÃO ---
st.sidebar.markdown("### 🗓️ Período de Análise")
ano_atual = st.sidebar.selectbox("Ano", [2025, 2026, 2027], index=1)
meses_nomes = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
]
mes_selecionado = st.sidebar.selectbox("Mês", meses_nomes, index=9)
mes_num = meses_nomes.index(mes_selecionado) + 1
dias_no_mes = calendar.monthrange(ano_atual, mes_num)[1]

menu = st.sidebar.radio(
    "Navegação",
    ["📊 Visão Geral & Calendário Diário", "⚙️ Configurar Renda e Poupança", "💸 Lançar Gasto Diário", "📌 Gastos Fixos & Parcelas"]
)

# --- CONSULTA DE PARÂMETROS DO MÊS ---
cursor.execute("SELECT renda, poupanca FROM metas_mensais WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
config_row = cursor.fetchone()
renda_mensal = config_row[0] if config_row else 10000.0
meta_poupanca = config_row[1] if config_row else 1500.0

# Despesas Fixas e Parcelas Totais
df_fixos = pd.read_sql_query("SELECT id, descricao, valor, tipo, parcela_atual, total_parcelas FROM despesas_fixas", conn)
total_fixos = df_fixos["valor"].sum() if not df_fixos.empty else 0.0

# Orçamento livre total para os dias
saldo_livre_mes = renda_mensal - meta_poupanca - total_fixos
meta_diaria = saldo_livre_mes / dias_no_mes if dias_no_mes > 0 else 0.0

# Gastos Diários Lançados
df_gastos = pd.read_sql_query(
    "SELECT id, dia, descricao, categoria, valor FROM gastos_diarios WHERE ano = ? AND mes = ? ORDER BY dia ASC",
    conn, params=(ano_atual, mes_num)
)
total_gasto_variavel = df_gastos["valor"].sum() if not df_gastos.empty else 0.0
saldo_restante_real = saldo_livre_mes - total_gasto_variavel

# =========================================================
# TELA 1: DASHBOARD GERAL E PROJEÇÃO DIÁRIA
# =========================================================
if menu == "📊 Visão Geral & Calendário Diário":
    st.title(f"Acompanhamento Diário — {mes_selecionado}/{ano_atual}")
    
    # Linha de Métricas Principais
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #3b82f6;">
            <div class="metric-label">Renda Mensal</div>
            <div class="metric-num">R$ {renda_mensal:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #10b981;">
            <div class="metric-label">Poupança / Reserva</div>
            <div class="metric-num">R$ {meta_poupanca:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #f59e0b;">
            <div class="metric-label">Fixos & Parcelas</div>
            <div class="metric-num">R$ {total_fixos:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #8b5cf6;">
            <div class="metric-label">Disponível p/ Mês</div>
            <div class="metric-num">R$ {saldo_livre_mes:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c5:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #06b6d4;">
            <div class="metric-label">Teto Sugerido / Dia</div>
            <div class="metric-num">R$ {meta_diaria:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)

    # Construção da tabela do Dia 1 ao último dia do mês
    tabela_dias = []
    saldo_acumulado = saldo_livre_mes
    dia_negativo = None

    gastos_por_dia = df_gastos.groupby("dia")["valor"].sum().to_dict() if not df_gastos.empty else {}

    for d in range(1, dias_no_mes + 1):
        gasto_do_dia = gastos_por_dia.get(d, 0.0)
        saldo_acumulado -= gasto_do_dia
        
        if saldo_acumulado < 0 and dia_negativo is None:
            dia_negativo = d

        tabela_dias.append({
            "Dia": d,
            "Teto Diário": meta_diaria,
            "Gasto Real": gasto_do_dia,
            "Diferença Dia": meta_diaria - gasto_do_dia,
            "Saldo Restante": saldo_acumulado
        })

    df_calendario = pd.DataFrame(tabela_dias)

    # Avisos de Saldo
    if dia_negativo:
        st.markdown(f"""
        <div class="danger-box">
            🚨 <b>Atenção:</b> Seu saldo livre ficou negativo no <b>Dia {dia_negativo}</b>! 
            Você já gastou mais do que o planejado para o mês. Saldo restante atual: <b>R$ {saldo_restante_real:,.2f}</b>.
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="success-box">
            ✅ <b>Dentro do planejado:</b> Você ainda possui <b>R$ {saldo_restante_real:,.2f}</b> livres para gastar até o final de {mes_selecionado}.
        </div>
        """, unsafe_allow_html=True)

    # GRÁFICO: CURVA DO DIA 1 AO ÚLTIMO DIA DO MÊS
    st.subheader(f"📈 Curva de Saldo do Dia 1 ao {dias_no_mes}")

    fig = go.Figure()

    # Linha de Saldo Restante
    fig.add_trace(go.Scatter(
        x=df_calendario["Dia"],
        y=df_calendario["Saldo Restante"],
        mode="lines+markers",
        name="Saldo Disponível",
        line=dict(color="#38bdf8", width=3),
        marker=dict(size=6)
    ))

    # Linha zero de corte
    fig.add_hline(
        y=0, 
        line_dash="dash", 
        line_color="#ef4444", 
        annotation_text="Limite Zero (Orçamento Esgotado)", 
        annotation_position="bottom right"
    )

    fig.update_layout(
        paper_bgcolor="#11131a",
        plot_bgcolor="#161922",
        font_color="#cbd5e1",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(title="Dia do Mês", tickmode="linear", tick0=1, dtick=2, gridcolor="#232734"),
        yaxis=dict(title="Saldo Restante (R$)", gridcolor="#232734")
    )
    st.plotly_chart(fig, use_container_width=True)

    # TABELA DETALHADA DIA A DIA
    st.subheader("📋 Tabela Orçamentária por Dia")
    
    # Formatação visual para a tabela
    df_exibicao = df_calendario.copy()
    df_exibicao["Teto Diário"] = df_exibicao["Teto Diário"].map(lambda x: f"R$ {x:,.2f}")
    df_exibicao["Gasto Real"] = df_exibicao["Gasto Real"].map(lambda x: f"R$ {x:,.2f}" if x > 0 else "-")
    df_exibicao["Diferença Dia"] = df_exibicao["Diferença Dia"].map(lambda x: f"R$ {x:,.2f}")
    df_exibicao["Saldo Restante"] = df_exibicao["Saldo Restante"].map(lambda x: f"R$ {x:,.2f}")

    st.dataframe(df_exibicao, use_container_width=True, hide_index=True)

# =========================================================
# TELA 2: CONFIGURAR RENDA E POUPANÇA (ALTERAÇÃO DIRETA NO APP)
# =========================================================
elif menu == "⚙️ Configurar Renda e Poupança":
    st.title(f"Ajustar Valores de {mes_selecionado}/{ano_atual}")
    st.write("Atualize sua renda mensal e meta de economia diretamente aqui sem precisar mexer em código.")

    with st.form("form_config"):
        nova_renda = st.number_input("Renda Mensal Total (R$)", min_value=0.0, value=float(renda_mensal), step=100.0)
        nova_poupanca = st.number_input("Quanto deseja Poupar / Investir neste mês? (R$)", min_value=0.0, value=float(meta_poupanca), step=50.0)
        
        salvar_cfg = st.form_submit_button("Salvar Configurações")
        if salvar_cfg:
            cursor.execute("""
                INSERT INTO metas_mensais (ano, mes, renda, poupanca)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(ano, mes) DO UPDATE SET
                    renda=excluded.renda,
                    poupanca=excluded.poupanca
            """, (ano_atual, mes_num, nova_renda, nova_poupanca))
            conn.commit()
            st.success("Valores atualizados com sucesso!")
            st.rerun()

# =========================================================
# TELA 3: LANÇAR GASTO DIÁRIO
# =========================================================
elif menu == "💸 Lançar Gasto Diário":
    st.title("Registrar Despesa do Dia")
    
    with st.form("form_gasto_dia", clear_on_submit=True):
        dia_gasto = st.slider("Dia do mês em que o gasto ocorreu", 1, dias_no_mes, value=min(date.today().day, dias_no_mes))
        desc_gasto = st.text_input("Descrição (ex: Almoço, Farmácia, Combustível, Jantar)")
        cat_gasto = st.selectbox("Categoria", ["Alimentação", "Transporte", "Lazer", "Saúde", "Supermercado", "Outros"])
        val_gasto = st.number_input("Valor da Despesa (R$)", min_value=0.5, step=5.0)

        salvar_gasto = st.form_submit_button("Lançar Despesa")
        if salvar_gasto:
            if desc_gasto.strip() == "":
                st.warning("Preencha a descrição do gasto.")
            else:
                cursor.execute("""
                    INSERT INTO gastos_diarios (ano, mes, dia, descricao, categoria, valor)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ano_atual, mes_num, dia_gasto, desc_gasto, cat_gasto, val_gasto))
                conn.commit()
                st.success(f"Gasto de R$ {val_gasto:,.2f} no Dia {dia_gasto} lançado!")
                st.rerun()

    st.subheader("Histórico de Gastos Diários Deste Mês")
    if not df_gastos.empty:
        df_show = df_gastos[["dia", "descricao", "categoria", "valor"]].copy()
        df_show["valor"] = df_show["valor"].map(lambda x: f"R$ {x:,.2f}")
        df_show.columns = ["Dia", "Descrição", "Categoria", "Valor"]
        st.dataframe(df_show, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhum gasto avulso lançado ainda neste mês.")

# =========================================================
# TELA 4: GASTOS FIXOS E PARCELAS
# =========================================================
elif menu == "📌 Gastos Fixos & Parcelas":
    st.title("Gastos Fixos e Parcelamentos Contínuos")

    with st.form("form_fixos", clear_on_submit=True):
        st.subheader("Adicionar Nova Despesa Fixa ou Parcelamento")
        nome_fixo = st.text_input("Nome da Conta (ex: Aluguel, Condomínio, Parcela TV)")
        valor_fixo = st.number_input("Valor Mensal (R$)", min_value=1.0, step=10.0)
        tipo_fixo = st.selectbox("Tipo de Despesa", ["Fixo (Contínuo)", "Parcelamento"])
        
        c_p1, c_p2 = st.columns(2)
        p_atual = c_p1.number_input("Parcela Atual (se for parcelamento)", min_value=1, value=1)
        p_total = c_p2.number_input("Total de Parcelas (se for parcelamento)", min_value=1, value=1)

        salvar_fixo = st.form_submit_button("Cadastrar Despesa Fixa")
        if salvar_fixo:
            tipo_bd = "Parcela" if "Parcelamento" in tipo_fixo else "Fixo"
            cursor.execute("""
                INSERT INTO despesas_fixas (descricao, valor, tipo, parcela_atual, total_parcelas)
                VALUES (?, ?, ?, ?, ?)
            """, (nome_fixo, valor_fixo, tipo_bd, p_atual, p_total))
            conn.commit()
            st.success("Despesa cadastrada!")
            st.rerun()

    st.subheader("Contas Cadastradas que Abatem da Renda")
    if not df_fixos.empty:
        st.dataframe(df_fixos[["descricao", "valor", "tipo", "parcela_atual", "total_parcelas"]], use_container_width=True, hide_index=True)
        
        # Opção de remover
        item_para_remover = st.selectbox("Selecione uma conta para excluir se já foi quitada:", df_fixos["descricao"].tolist())
        if st.button("Excluir Conta Selecionada"):
            cursor.execute("DELETE FROM despesas_fixas WHERE descricao = ?", (item_para_remover,))
            conn.commit()
            st.success(f"Conta '{item_para_remover}' removida!")
            st.rerun()
    else:
        st.info("Nenhuma despesa fixa cadastrada.")
