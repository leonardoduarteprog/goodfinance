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

# --- ESTILIZAÇÃO CSS (Dark & Banners de Alerta) ---
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

# Gastos fixos e parcelas
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

# Patrimônio base
cursor.execute("""
CREATE TABLE IF NOT EXISTS patrimonio_base (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    saldo_inicial REAL DEFAULT 0.0
)
""")
cursor.execute("INSERT OR IGNORE INTO patrimonio_base (id, saldo_inicial) VALUES (1, 0.0)")

# Aportes consolidados por mês
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

# Inclusão da nova aba "Patrimônio"
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

df_fixos = pd.read_sql_query("SELECT id, descricao, valor, tipo, parcela_atual, total_parcelas FROM despesas_fixas", conn)
total_fixos = df_fixos["valor"].sum() if not df_fixos.empty else 0.0

saldo_livre_mes = max(0.0, renda_mensal - meta_poupanca - total_fixos)

# Consulta de gastos lançados no mês
df_gastos = pd.read_sql_query(
    "SELECT id, dia, descricao, categoria, valor FROM gastos_diarios WHERE ano = ? AND mes = ? ORDER BY dia ASC, id ASC",
    conn, params=(ano_atual, mes_num)
)
gastos_por_dia = df_gastos.groupby("dia")["valor"].sum().to_dict() if not df_gastos.empty else {}
total_gasto_real = df_gastos["valor"].sum() if not df_gastos.empty else 0.0
saldo_restante_caixa = saldo_livre_mes - total_gasto_real

# =========================================================
# LÓGICA DE SIMULAÇÃO DIA A DIA (DO DIA 1 AO FIM DO MÊS)
# =========================================================
dias_lista = []
teto_lista = []
gasto_lista = []
cores_status = []
cores_grafico = []

dia_negativo = None
saldo_acum_check = saldo_livre_mes

if modo_ajuste == "rebalancear":
    # MODO 1: REBALANCEAMENTO DINÂMICO
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
                hex_c = "#64748b"

        saldo_remanescente -= gasto_dia

        dias_lista.append(f"Dia {d:02d}")
        teto_lista.append(teto_dia)
        gasto_lista.append(gasto_dia)
        cores_status.append(cor)
        cores_grafico.append(hex_c)

else:
    # MODO 2: ABATER DO FIM DO MÊS
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
                hex_c = "#64748b"

        dias_lista.append(f"Dia {d:02d}")
        teto_lista.append(teto_dia)
        gasto_lista.append(gasto_dia)
        cores_status.append(cor)
        cores_grafico.append(hex_c)

df_exibicao = pd.DataFrame({
    "Dia": dias_lista,
    "Teto Permitido (R$)": teto_lista,
    "Gasto Real (R$)": gasto_lista
})

# =========================================================
# TELA 1: CALENDÁRIO ORÇAMENTÁRIO & GRÁFICO
# =========================================================
if menu == "📊 Calendário e Gráfico Diário":
    st.title(f"Acompanhamento — {mes_selecionado} de {ano_atual}")

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

    st.subheader("Desempenho por Dia: Teto Permitido vs. Gasto Real")

    dias_numeros = list(range(1, dias_no_mes + 1))
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=dias_numeros,
        y=teto_lista,
        mode="lines+markers",
        name="Teto Permitido (R$)",
        line=dict(color="#38bdf8", width=2, dash="dot"),
        marker=dict(size=5)
    ))
    fig.add_trace(go.Bar(
        x=dias_numeros,
        y=gasto_lista,
        name="Gasto Registrado (R$)",
        marker_color=cores_grafico
    ))

    fig.update_layout(
        template="plotly_dark",
        height=340,
        margin=dict(l=10, r=10, t=30, b=10),
        xaxis=dict(title="Dia do Mês", tickmode="linear", tick0=1, dtick=1),
        yaxis=dict(title="Reais (R$)"),
        legend=dict(orientation="h", y=1.1, x=0)
    )
    st.plotly_chart(fig, use_container_width=True)

    st.write("")
    st.subheader("Tabela do Dia 1 ao Fim do Mês")

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

# =========================================================
# TELA 2: CONFIGURAÇÃO DE RENDA E REGRAS
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

# =========================================================
# TELA 3: LANÇAMENTO DE GASTOS DIÁRIOS
# =========================================================
elif menu == "💸 Lançar Gasto Diário":
    st.title("Registrar Gasto Diário")

    with st.form("form_lancar", clear_on_submit=True):
        dia_sel = st.number_input(
            "Dia do Mês",
            min_value=1,
            max_value=dias_no_mes,
            value=min(date.today().day, dias_no_mes),
            step=1
        )

        lista_categorias = [
            "🍔 Alimentação",
            "🚗 Transporte",
            "🛒 Supermercado",
            "🍿 Lazer",
            "💊 Saúde",
            "🏠 Moradia / Contas",
            "✏️ Outra / Personalizar"
        ]
        cat_sel = st.selectbox("Categoria", lista_categorias)
        cat_custom = st.text_input("Se selecionou '✏️ Outra / Personalizar', digite o nome da categoria aqui:")

        desc = st.text_input("Descrição do Gasto (ex: Almoço no shopping, Combustível, Farmácia)")
        val = st.number_input("Valor da Despesa (R$)", min_value=0.5, step=5.0)

        if st.form_submit_button("Confirmar Despesa"):
            categoria_final = cat_custom.strip() if ("Personalizar" in cat_sel and cat_custom.strip()) else cat_sel
            
            if desc.strip() == "":
                st.warning("Preencha a descrição do gasto.")
            elif "Personalizar" in cat_sel and cat_custom.strip() == "":
                st.warning("Você selecionou personalizar categoria. Por favor, digite o nome dela no campo correspondente.")
            else:
                cursor.execute("""
                    INSERT INTO gastos_diarios (ano, mes, dia, descricao, categoria, valor)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (ano_atual, mes_num, int(dia_sel), desc, categoria_final, val))
                conn.commit()
                st.success(f"Despesa de R$ {val:,.2f} no Dia {int(dia_sel):02d} registrada na categoria '{categoria_final}'!")
                st.rerun()

    st.subheader("Histórico de Gastos Deste Mês")
    if not df_gastos.empty:
        df_exibir = df_gastos[["dia", "descricao", "categoria", "valor"]].copy()
        df_exibir.columns = ["Dia", "Descrição", "Categoria", "Valor"]
        st.dataframe(
            df_exibir.style.format({"Valor": "R$ {:,.2f}"}),
            use_container_width=True,
            hide_index=True
        )

        st.markdown("#### 🗑️ Excluir Gasto Indevido")
        st.caption("Selecione um lançamento cadastrado por engano para removê-lo da sua base:")

        opcoes_para_excluir = {
            f"Dia {int(r['dia']):02d} | {r['descricao']} ({r['categoria']}) — R$ {r['valor']:,.2f} (Cód #{r['id']})": int(r['id'])
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

# =========================================================
# TELA 5: PATRIMÔNIO & PROJEÇÃO
# =========================================================
elif menu == "💰 Patrimônio":
    st.title("Gestão de Patrimônio e Projeção de Reserva")

    # Recupera patrimônio base inicial
    cursor.execute("SELECT saldo_inicial FROM patrimonio_base WHERE id = 1")
    row_base = cursor.fetchone()
    patrimonio_inicial = row_base[0] if row_base else 0.0

    # Recupera todos os aportes consolidados
    df_aportes = pd.read_sql_query("SELECT ano, mes, valor, data_consolidacao FROM aportes_consolidados", conn)
    total_aportado_historico = df_aportes["valor"].sum() if not df_aportes.empty else 0.0
    patrimonio_atual_total = patrimonio_inicial + total_aportado_historico

    # Recupera status do mês selecionado
    cursor.execute("SELECT valor FROM aportes_consolidados WHERE ano = ? AND mes = ?", (ano_atual, mes_num))
    row_aporte_mes = cursor.fetchone()
    aporte_consolidado_mes = row_aporte_mes[0] if row_aporte_mes else None

    # CARDS PRINCIPAIS DE PATRIMÔNIO
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

    # BLOCO 1: DEFINIR PATRIMÔNIO INICIAL
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

    # BLOCO 2: CONSOLIDAR O MÊS ATUAL
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

    # BLOCO 3: TABELA E GRÁFICO DE PROJEÇÃO ATÉ O FINAL DO ANO
    st.subheader(f"3. Projeção Patrimonial — Ano de {ano_atual}")
    st.caption(f"Previsão mês a mês somando o patrimônio inicial com aportes realizados e projetados (Meta base: R$ {meta_poupanca:,.2f}/mês):")

    # Mapeamento de aportes consolidados deste ano
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

    # GRÁFICO DE CRESCIMENTO DO PATRIMÔNIO
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

    # TABELA FORMATADA DE PROJEÇÃO
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
