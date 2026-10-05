import streamlit as st
import pandas as pd
import sqlite3
import calendar
from datetime import datetime, date
import plotly.graph_objects as go

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Gestão Orçamentária Diária",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILIZAÇÃO CSS (Dark UI & Status Semafórico) ---
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
    /* Estilos das Badges de Status */
    .badge-verde {
        background-color: rgba(16, 185, 129, 0.15);
        color: #10b981;
        border: 1px solid #10b981;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-amarelo {
        background-color: rgba(245, 158, 11, 0.15);
        color: #f59e0b;
        border: 1px solid #f59e0b;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-vermelho {
        background-color: rgba(239, 68, 68, 0.15);
        color: #ef4444;
        border: 1px solid #ef4444;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: 600;
        display: inline-block;
    }
    .badge-neutro {
        background-color: rgba(148, 163, 184, 0.1);
        color: #94a3b8;
        border: 1px solid #334155;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 12px;
        display: inline-block;
    }
    /* Tabela Customizada */
    .custom-table {
        width: 100%;
        border-collapse: collapse;
        margin-top: 15px;
        font-size: 14px;
    }
    .custom-table th {
        background-color: #161922;
        color: #94a3b8;
        padding: 10px 12px;
        text-align: left;
        border-bottom: 2px solid #232734;
        font-weight: 600;
    }
    .custom-table td {
        padding: 10px 12px;
        border-bottom: 1px solid #1e2230;
    }
    .custom-table tr:hover {
        background-color: #131620;
    }
</style>
""", unsafe_allow_html=True)

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

# Garante a coluna modo_ajuste em caso de base já criada
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

# --- SIDEBAR: CONTROLES DE NAVEGAÇÃO ---
st.sidebar.markdown("### 🗓️ Período de Gestão")
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
    ["📊 Calendário Orçamentário", "⚙️ Configurar Renda e Regras", "💸 Lançar Gasto Diário", "📌 Gastos Fixos & Parcelas"]
)

# --- RECUPERAÇÃO DE PARÂMETROS DO BANCO ---
cursor.execute("SELECT renda, poupanca, modo_ajuste FROM metas_mensais WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
config_row = cursor.fetchone()
renda_mensal = config_row[0] if config_row else 10000.0
meta_poupanca = config_row[1] if config_row else 1500.0
modo_ajuste = config_row[2] if (config_row and config_row[2]) else "rebalancear"

df_fixos = pd.read_sql_query("SELECT id, descricao, valor, tipo, parcela_atual, total_parcelas FROM despesas_fixas", conn)
total_fixos = df_fixos["valor"].sum() if not df_fixos.empty else 0.0

saldo_livre_mes = max(0.0, renda_mensal - meta_poupanca - total_fixos)

# Gastos lançados agrupados por dia
df_gastos = pd.read_sql_query(
    "SELECT dia, descricao, categoria, valor FROM gastos_diarios WHERE ano = ? AND mes = ? ORDER BY dia ASC",
    conn, params=(ano_atual, mes_num)
)
gastos_por_dia = df_gastos.groupby("dia")["valor"].sum().to_dict() if not df_gastos.empty else {}
total_gasto_real = df_gastos["valor"].sum() if not df_gastos.empty else 0.0

# =========================================================
# LÓGICA DE SIMULAÇÃO DIA A DIA (DO DIA 1 AO ÚLTIMO DIA)
# =========================================================
dias_dados = []
saldo_remanescente = saldo_livre_mes

if modo_ajuste == "rebalancear":
    # MODO 1: REBALANCEAMENTO DINÂMICO
    for d in range(1, dias_no_mes + 1):
        dias_a_frente = (dias_no_mes - d + 1)
        teto_dia = max(0.0, saldo_remanescente / dias_a_frente) if dias_a_frente > 0 else 0.0
        gasto_dia = gastos_por_dia.get(d, 0.0)
        
        # Determina a cor do dia
        if gasto_dia > 0:
            if gasto_dia > teto_dia:
                status = "Estourou"
                cor_badge = "badge-vermelho"
                cor_hex = "#ef4444"
            elif gasto_dia >= (teto_dia * 0.8):
                status = "Alerta (Quase no teto)"
                cor_badge = "badge-amarelo"
                cor_hex = "#f59e0b"
            else:
                status = "Dentro do teto"
                cor_badge = "badge-verde"
                cor_hex = "#10b981"
        else:
            if saldo_remanescente <= 0:
                status = "Sem saldo disponível"
                cor_badge = "badge-vermelho"
                cor_hex = "#ef4444"
            else:
                status = "Planejado"
                cor_badge = "badge-neutro"
                cor_hex = "#475569"

        saldo_remanescente -= gasto_dia

        dias_dados.append({
            "dia": d,
            "teto": teto_dia,
            "gasto": gasto_dia,
            "saldo_apos": saldo_remanescente,
            "status": status,
            "cor_badge": cor_badge,
            "cor_hex": cor_hex
        })

else:
    # MODO 2: ABATER DO FIM DO MÊS (Meta Fixa com corte de dias)
    teto_base_fixo = saldo_livre_mes / dias_no_mes if dias_no_mes > 0 else 0.0
    saldo_acumulado = saldo_livre_mes

    for d in range(1, dias_no_mes + 1):
        gasto_dia = gastos_por_dia.get(d, 0.0)
        
        # O teto é o teto base ou o que resta no caixa
        teto_dia = teto_base_fixo if saldo_acumulado >= teto_base_fixo else max(0.0, saldo_acumulado)
        saldo_acumulado -= gasto_dia

        if gasto_dia > 0:
            if gasto_dia > teto_base_fixo:
                status = "Estourou"
                cor_badge = "badge-vermelho"
                cor_hex = "#ef4444"
            elif gasto_dia >= (teto_base_fixo * 0.8):
                status = "Alerta (Quase no teto)"
                cor_badge = "badge-amarelo"
                cor_hex = "#f59e0b"
            else:
                status = "Dentro do teto"
                cor_badge = "badge-verde"
                cor_hex = "#10b981"
        else:
            if teto_dia <= 0.0:
                status = "Zerado (Cortado do mês)"
                cor_badge = "badge-vermelho"
                cor_hex = "#ef4444"
            else:
                status = "Planejado"
                cor_badge = "badge-neutro"
                cor_hex = "#475569"

        dias_dados.append({
            "dia": d,
            "teto": teto_dia,
            "gasto": gasto_dia,
            "saldo_apos": saldo_acumulado,
            "status": status,
            "cor_badge": cor_badge,
            "cor_hex": cor_hex
        })

df_simulacao = pd.DataFrame(dias_dados)

# =========================================================
# TELA 1: CALENDÁRIO ORÇAMENTÁRIO (VISÃO GERAL)
# =========================================================
if menu == "📊 Calendário Orçamentário":
    st.title(f"Acompanhamento Diário — {mes_selecionado}/{ano_atual}")

    # CARDS DE MÉTRICAS
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #3b82f6;">
            <div class="metric-label">Orçamento Livre Inicial</div>
            <div class="metric-num">R$ {saldo_livre_mes:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c2:
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #f43f5e;">
            <div class="metric-label">Total Gasto Até Agora</div>
            <div class="metric-num">R$ {total_gasto_real:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c3:
        saldo_atual_restante = saldo_livre_mes - total_gasto_real
        cor_borda = "#10b981" if saldo_atual_restante >= 0 else "#ef4444"
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid {cor_borda};">
            <div class="metric-label">Saldo Disponível em Caixa</div>
            <div class="metric-num">R$ {saldo_atual_restante:,.2f}</div>
        </div>
        """, unsafe_allow_html=True)
    with c4:
        txt_modo = "Rebalanceamento Dinâmico" if modo_ajuste == "rebalancear" else "Corte no Fim do Mês"
        st.markdown(f"""
        <div class="metric-card" style="border-top: 3px solid #8b5cf6;">
            <div class="metric-label">Regra Ativa</div>
            <div class="metric-num" style="font-size: 16px; margin-top: 8px;">{txt_modo}</div>
        </div>
        """, unsafe_allow_html=True)

    st.write("")

    # GRÁFICO DIÁRIO COM CORES POR STATUS
    st.subheader(f"📊 Desempenho Diário: Teto Previsto vs. Gasto Real")

    fig = go.Figure()

    # Linha do Teto Permitido para cada dia
    fig.add_trace(go.Scatter(
        x=df_simulacao["dia"],
        y=df_simulacao["teto"],
        mode="lines+markers",
        name="Teto Permitido (R$)",
        line=dict(color="#38bdf8", width=2, dash="dot"),
        marker=dict(size=5)
    ))

    # Barras de Gastos com cores condicionais (Verde, Amarelo, Vermelho)
    fig.add_trace(go.Bar(
        x=df_simulacao["dia"],
        y=df_simulacao["gasto"],
        name="Gasto Registrado (R$)",
        marker_color=df_simulacao["cor_hex"]
    ))

    fig.update_layout(
        paper_bgcolor="#11131a",
        plot_bgcolor="#161922",
        font_color="#cbd5e1",
        height=380,
        margin=dict(l=20, r=20, t=30, b=20),
        xaxis=dict(title="Dia do Mês", tickmode="linear", tick0=1, dtick=1, gridcolor="#232734"),
        yaxis=dict(title="Valor (R$)", gridcolor="#232734"),
        legend=dict(orientation="h", y=1.1, x=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.write("")

    # TABELA COM BADGES SEMAFÓRICAS
    st.subheader("📋 Tabela Orçamentária do Dia 1 ao Fim do Mês")
    
    # Montagem da tabela em HTML estilizada
    tabela_html = """
    <table class="custom-table">
        <thead>
            <tr>
                <th>Dia</th>
                <th>Teto Permitido</th>
                <th>Gasto Real</th>
                <th>Saldo Restante no Caixa</th>
                <th>Diagnóstico</th>
            </tr>
        </thead>
        <tbody>
    """
    for _, row in df_simulacao.iterrows():
        gasto_str = f"R$ {row['gasto']:,.2f}" if row['gasto'] > 0 else "-"
        tabela_html += f"""
        <tr>
            <td><b>Dia {int(row['dia']):02d}</b></td>
            <td>R$ {row['teto']:,.2f}</td>
            <td><b>{gasto_str}</b></td>
            <td>R$ {row['saldo_apos']:,.2f}</td>
            <td><span class="{row['cor_badge']}">{row['status']}</span></td>
        </tr>
        """
    tabela_html += "</tbody></table>"

    st.markdown(tabela_html, unsafe_allow_html=True)

# =========================================================
# TELA 2: CONFIGURAÇÃO DE RENDA E REGRAS DE COMPENSAÇÃO
# =========================================================
elif menu == "⚙️ Configurar Renda e Regras":
    st.title("Ajustes Orçamentários e Regras")
    st.write("Defina seus valores e selecione como o aplicativo deve se comportar quando você ultrapassar o teto diário.")

    with st.form("form_config"):
        nova_renda = st.number_input("Renda Mensal Líquida (R$)", min_value=0.0, value=float(renda_mensal), step=100.0)
        nova_poupanca = st.number_input("Poupança / Investimento Mensal (R$)", min_value=0.0, value=float(meta_poupanca), step=50.0)
        
        st.markdown("---")
        st.subheader("Como você quer que o app reaja se você estourar o limite diário?")
        
        modo_escolhido = st.radio(
            "Selecione o comportamento da tabela:",
            [
                "Rebalancear Dias Restantes (Diminui a meta diária dos dias futuros para compensar)",
                "Abater do Fim do Mês (Mantém a meta diária fixa, mas zera os últimos dias do mês)"
            ],
            index=0 if modo_ajuste == "rebalancear" else 1
        )

        salvar = st.form_submit_button("Salvar Preferências")
        if salvar:
            modo_bd = "rebalancear" if "Rebalancear" in modo_escolhido else "abater_fim"
            cursor.execute("""
                INSERT INTO metas_mensais (ano, mes, renda, poupanca, modo_ajuste)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(ano, mes) DO UPDATE SET
                    renda=excluded.renda,
                    poupanca=excluded.poupanca,
                    modo_ajuste=excluded.modo_ajuste
            """, (ano_atual, mes_num, nova_renda, nova_poupanca, modo_bd))
            conn.commit()
            st.success("Configurações atualizadas com sucesso!")
            st.rerun()

# =========================================================
# TELA 3: LANÇAMENTO DE GASTOS DIÁRIOS
# =========================================================
elif menu == "💸 Lançar Gasto Diário":
    st.title("Registrar Despesa do Dia")

    with st.form("form_lancar", clear_on_submit=True):
        dia_sel = st.slider("Dia do gasto", 1, dias_no_mes, value=min(date.today().day, dias_no_mes))
        desc = st.text_input("Descrição do gasto (ex: Almoço, Farmácia, Combustível)")
        cat = st.selectbox("Categoria", ["Alimentação", "Transporte", "Lazer", "Saúde", "Supermercado", "Outros"])
        val = st.number_input("Valor Pago (R$)", min_value=0.5, step=5.0)

        if st.form_submit_button("Confirmar Lançamento"):
            if desc.strip() == "":
                st.warning("Preencha a descrição do gasto.")
            else:
                cursor.execute("""
                    INSERT INTO gastos_diarios (ano, mes, dia, descricao, categoria, valor)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ano_atual, mes_num, dia_sel, desc, cat, val))
                conn.commit()
                st.success(f"Despesa de R$ {val:,.2f} adicionada no Dia {dia_sel}!")
                st.rerun()

    st.subheader("Despesas Já Registradas Neste Mês")
    if not df_gastos.empty:
        df_view = df_gastos.copy()
        df_view["valor"] = df_view["valor"].map(lambda x: f"R$ {x:,.2f}")
        df_view.columns = ["Dia", "Descrição", "Categoria", "Valor"]
        st.dataframe(df_view, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma despesa lançada neste mês.")

# =========================================================
# TELA 4: GASTOS FIXOS E PARCELAS
# =========================================================
elif menu == "📌 Gastos Fixos & Parcelas":
    st.title("Despesas Fixas e Parcelamentos")

    with st.form("form_fixo_add", clear_on_submit=True):
        f_nome = st.text_input("Nome da despesa (ex: Aluguel, Academia, Parcela Celular)")
        f_val = st.number_input("Valor Mensal (R$)", min_value=1.0, step=10.0)
        f_tipo = st.selectbox("Tipo", ["Fixo Contínuo", "Parcelamento"])

        c_p1, c_p2 = st.columns(2)
        p_at = c_p1.number_input("Parcela Atual", min_value=1, value=1)
        p_tot = c_p2.number_input("Total de Parcelas", min_value=1, value=1)

        if st.form_submit_button("Cadastrar Despesa Fixa"):
            tipo_bd = "Parcela" if "Parcelamento" in f_tipo else "Fixo"
            cursor.execute("""
                INSERT INTO despesas_fixas (descricao, valor, tipo, parcela_atual, total_parcelas)
                VALUES (?, ?, ?, ?, ?)
            """, (f_nome, f_val, tipo_bd, p_at, p_tot))
            conn.commit()
            st.success("Despesa fixa cadastrada!")
            st.rerun()

    st.subheader("Contas Cadastradas que Abatem da Renda")
    if not df_fixos.empty:
        st.dataframe(df_fixos[["descricao", "valor", "tipo", "parcela_atual", "total_parcelas"]], use_container_width=True, hide_index=True)
        
        remover = st.selectbox("Excluir conta:", df_fixos["descricao"].tolist())
        if st.button("Remover Conta"):
            cursor.execute("DELETE FROM despesas_fixas WHERE descricao = ?", (remover,))
            conn.commit()
            st.success(f"Conta '{remover}' removida!")
            st.rerun()
    else:
        st.info("Nenhuma conta fixa cadastrada.")
