import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime, date
import plotly.graph_objects as go

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

# --- BARRA LATERAL (FILTROS E NAVEGAÇÃO) ---
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
        "📌 Gastos Fixos & Parcelas"
    ]
)

# --- RECUPERAÇÃO DE CONFIGURAÇÕES ---
cursor.execute("SELECT renda, poupanca, modo_ajuste FROM metas_mensais WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
config_row = cursor.fetchone()
renda_mensal = config_row[0] if config_row else 10000.0
meta_poupanca = config_row[1] if config_row else 1500.0
modo_ajuste = config_row[2] if (config_row and config_row[2]) else "rebalancear"

df_fixos = pd.read_sql_query("SELECT id, descricao, valor, tipo, parcela_atual, total_parcelas FROM despesas_fixas", conn)
total_fixos = df_fixos["valor"].sum() if not df_fixos.empty else 0.0

saldo_livre_mes = max(0.0, renda_mensal - meta_poupanca - total_fixos)

# Consulta de gastos lançados no mês
df_gastos = pd.read_sql_query(
    "SELECT dia, descricao, categoria, valor FROM gastos_diarios WHERE ano = ? AND mes = ? ORDER BY dia ASC",
    conn, params=(ano_atual, mes_num)
)
gastos_por_dia = df_gastos.groupby("dia")["valor"].sum().to_dict() if not df_gastos.empty else {}
total_gasto_real = df_gastos["valor"].sum() if not df_gastos.empty else 0.0
saldo_restante_caixa = saldo_livre_mes - total_gasto_real

# =========================================================
# PROCESSAMENTO DOS DIAS (DO DIA 1 AO ÚLTIMO DIA DO MÊS)
# =========================================================
dias_dados = []

if modo_ajuste == "rebalancear":
    # MODO 1: REBALANCEAMENTO DINÂMICO
    saldo_remanescente = saldo_livre_mes
    for d in range(1, dias_no_mes + 1):
        dias_a_frente = (dias_no_mes - d + 1)
        teto_dia = max(0.0, saldo_remanescente / dias_a_frente) if dias_a_frente > 0 else 0.0
        gasto_dia = gastos_por_dia.get(d, 0.0)

        if gasto_dia > 0:
            if gasto_dia > teto_dia:
                status = "🔴 Estourou o teto"
                cor_hex = "#ef4444"
            elif gasto_dia >= (teto_dia * 0.8):
                status = "🟡 Alerta (Quase no teto)"
                cor_hex = "#f59e0b"
            else:
                status = "🟢 Dentro do teto"
                cor_hex = "#10b981"
        else:
            if saldo_remanescente <= 0:
                status = "🔴 Sem saldo disponível"
                cor_hex = "#ef4444"
            else:
                status = "⚪ Planejado"
                cor_hex = "#64748b"

        saldo_remanescente -= gasto_dia

        dias_dados.append({
            "Dia": f"Dia {d:02d}",
            "dia_num": d,
            "Teto Permitido (R$)": teto_dia,
            "Gasto Real (R$)": gasto_dia,
            "Saldo em Caixa (R$)": saldo_remanescente,
            "Status": status,
            "cor_hex": cor_hex
        })
else:
    # MODO 2: ABATER DO FIM DO MÊS
    teto_base_fixo = saldo_livre_mes / dias_no_mes if dias_no_mes > 0 else 0.0
    saldo_acumulado = saldo_livre_mes

    for d in range(1, dias_no_mes + 1):
        gasto_dia = gastos_por_dia.get(d, 0.0)
        teto_dia = teto_base_fixo if saldo_acumulado >= teto_base_fixo else max(0.0, saldo_acumulado)
        saldo_acumulado -= gasto_dia

        if gasto_dia > 0:
            if gasto_dia > teto_base_fixo:
                status = "🔴 Estourou o teto"
                cor_hex = "#ef4444"
            elif gasto_dia >= (teto_base_fixo * 0.8):
                status = "🟡 Alerta (Quase no teto)"
                cor_hex = "#f59e0b"
            else:
                status = "🟢 Dentro do teto"
                cor_hex = "#10b981"
        else:
            if teto_dia <= 0.0:
                status = "🔴 Zerado (Cortado do mês)"
                cor_hex = "#ef4444"
            else:
                status = "⚪ Planejado"
                cor_hex = "#64748b"

        dias_dados.append({
            "Dia": f"Dia {d:02d}",
            "dia_num": d,
            "Teto Permitido (R$)": teto_dia,
            "Gasto Real (R$)": gasto_dia,
            "Saldo em Caixa (R$)": saldo_acumulado,
            "Status": status,
            "cor_hex": cor_hex
        })

df_calendario = pd.DataFrame(dias_dados)

# =========================================================
# TELA 1: CALENDÁRIO ORÇAMENTÁRIO & GRÁFICO
# =========================================================
if menu == "📊 Calendário e Gráfico Diário":
    st.title(f"Acompanhamento — {mes_selecionado} de {ano_atual}")

    # Cards principais
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Orçamento Livre do Mês", f"R$ {saldo_livre_mes:,.2f}")
    col2.metric("Total Gasto Até Agora", f"R$ {total_gasto_real:,.2f}")
    col3.metric("Saldo Restante em Caixa", f"R$ {saldo_restante_caixa:,.2f}", delta=f"{saldo_restante_caixa:,.2f}")
    regra_nome = "Rebalanceamento" if modo_ajuste == "rebalancear" else "Corte no Fim"
    col4.metric("Regra de Ajuste", regra_nome)

    st.divider()

    # GRÁFICO DIÁRIO
    st.subheader("Desempenho por Dia: Teto Permitido vs. Gasto Real")

    fig = go.Figure()
    # Linha do teto diário
    fig.add_trace(go.Scatter(
        x=df_calendario["dia_num"],
        y=df_calendario["Teto Permitido (R$)"],
        mode="lines+markers",
        name="Teto Permitido (R$)",
        line=dict(color="#38bdf8", width=2, dash="dot"),
        marker=dict(size=5)
    ))
    # Barras coloridas por status
    fig.add_trace(go.Bar(
        x=df_calendario["dia_num"],
        y=df_calendario["Gasto Real (R$)"],
        name="Gasto Registrado (R$)",
        marker_color=df_calendario["cor_hex"]
    ))

    fig.update_layout(
        template="plotly_dark",
        height=360,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="Dia do Mês", tickmode="linear", tick0=1, dtick=1),
        yaxis=dict(title="Reais (R$)"),
        legend=dict(orientation="h", y=1.1, x=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.divider()

    # TABELA NATIVA ROBUSTA
    st.subheader("Tabela do Dia 1 ao Fim do Mês")

    tabela_visual = df_calendario[["Dia", "Teto Permitido (R$)", "Gasto Real (R$)", "Saldo em Caixa (R$)", "Status"]].copy()

    st.dataframe(
        tabela_visual.style.format({
            "Teto Permitido (R$)": "R$ {:,.2f}",
            "Gasto Real (R$)": "R$ {:,.2f}",
            "Saldo em Caixa (R$)": "R$ {:,.2f}"
        }),
        use_container_width=True,
        hide_index=True
    )

# =========================================================
# TELA 2: CONFIGURAÇÃO DE RENDA E REGRAS
# =========================================================
elif menu == "⚙️ Configurar Renda e Regras":
    st.title("Configurar Renda, Poupança e Regras")
    st.write("Defina os valores mensais e como o aplicativo deve recalcular suas despesas.")

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

# =========================================================
# TELA 3: LANÇAMENTO DE GASTOS DIÁRIOS
# =========================================================
elif menu == "💸 Lançar Gasto Diário":
    st.title("Registrar Gasto Diário")

    with st.form("form_lancar", clear_on_submit=True):
        dia_sel = st.slider("Dia do gasto", 1, dias_no_mes, value=min(date.today().day, dias_no_mes))
        desc = st.text_input("Descrição do gasto (ex: Almoço, Supermercado, Combustível)")
        cat = st.selectbox("Categoria", ["Alimentação", "Transporte", "Lazer", "Saúde", "Supermercado", "Outros"])
        val = st.number_input("Valor da Despesa (R$)", min_value=0.5, step=5.0)

        if st.form_submit_button("Confirmar Despesa"):
            if desc.strip() == "":
                st.warning("Preencha a descrição do gasto.")
            else:
                cursor.execute("""
                    INSERT INTO gastos_diarios (ano, mes, dia, descricao, categoria, valor)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ano_atual, mes_num, dia_sel, desc, cat, val))
                conn.commit()
                st.success(f"Despesa de R$ {val:,.2f} no Dia {dia_sel} registrada!")
                st.rerun()

    st.subheader("Histórico de Gastos Deste Mês")
    if not df_gastos.empty:
        df_exibir = df_gastos.copy()
        df_exibir.columns = ["Dia", "Descrição", "Categoria", "Valor"]
        st.dataframe(
            df_exibir.style.format({"Valor": "R$ {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhum gasto avulso registrado neste mês ainda.")

# =========================================================
# TELA 4: GASTOS FIXOS E PARCELAS
# =========================================================
elif menu == "📌 Gastos Fixos & Parcelas":
    st.title("Despesas Fixas e Parcelamentos")

    with st.form("form_fixo", clear_on_submit=True):
        f_nome = st.text_input("Nome da conta (ex: Aluguel, Parcela Sofá)")
        f_val = st.number_input("Valor Mensal (R$)", min_value=1.0, step=10.0)
        f_tipo = st.selectbox("Tipo de Conta", ["Fixo Contínuo", "Parcelamento"])

        c1, c2 = st.columns(2)
        p_at = c1.number_input("Parcela Atual", min_value=1, value=1)
        p_tot = c2.number_input("Total de Parcelas", min_value=1, value=1)

        if st.form_submit_button("Salvar Despesa Fixa"):
            tipo_bd = "Parcela" if "Parcelamento" in f_tipo else "Fixo"
            cursor.execute("""
                INSERT INTO despesas_fixas (descricao, valor, tipo, parcela_atual, total_parcelas)
                VALUES (?, ?, ?, ?, ?)
            """, (f_nome, f_val, tipo_bd, p_at, p_tot))
            conn.commit()
            st.success("Conta fixa cadastrada!")
            st.rerun()

    st.subheader("Contas Cadastradas")
    if not df_fixos.empty:
        st.dataframe(
            df_fixos[["descricao", "valor", "tipo", "parcela_atual", "total_parcelas"]].rename(columns={
                "descricao": "Descrição",
                "valor": "Valor Mensal (R$)",
                "tipo": "Tipo",
                "parcela_atual": "Parcela Atual",
                "total_parcelas": "Total de Parcelas"
            }).style.format({"Valor Mensal (R$)": "R$ {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )

        remover = st.selectbox("Excluir conta quitada:", df_fixos["descricao"].tolist())
        if st.button("Remover Conta"):
            cursor.execute("DELETE FROM despesas_fixas WHERE descricao = ?", (remover,))
            conn.commit()
            st.success(f"Conta '{remover}' removida!")
            st.rerun()
    else:
        st.info("Nenhuma despesa fixa cadastrada.")
