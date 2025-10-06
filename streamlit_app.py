
import streamlit as st
import pandas as pd, numpy as np
from datetime import date, timedelta
import yfinance as yf
import plotly.graph_objects as go
from b3_utils import load_b3_tickers, ensure_sa_suffix, is_known_b3_ticker, search_b3

st.set_page_config(page_title="Análise B3 Didática", page_icon="📊", layout="wide")

@st.cache_data(ttl=3600)
def fetch_data(ticker, start, end):
    df = yf.download(ensure_sa_suffix(ticker), start=start, end=end, auto_adjust=True, progress=False)
    if df.empty: return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    for c in ["Open","High","Low","Close","Volume"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["Close"]).reset_index()
    return df

def sma(s, w): return s.rolling(window=w, min_periods=w).mean()
def rsi(s, w=14):
    delta = s.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.rolling(w).mean()
    ma_down = down.rolling(w).mean()
    rs = ma_up / ma_down.replace(0, np.nan)
    return 100 - (100 / (1 + rs))

def add_indicators(df, want_sma50=False, want_sma200=False):
    if df.empty: return df
    df = df.copy()
    df["SMA20"]=sma(df["Close"],20)
    if want_sma50:
        df["SMA50"]=sma(df["Close"],50)
    if want_sma200:
        df["SMA200"]=sma(df["Close"],200)
    df["RSI14"]=rsi(df["Close"])
    return df

def plot_price(df, t, show_sma50, show_sma200):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=df["Date"], open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        name="Preço",
        hovertext=[
            f"Data: {d.strftime('%Y-%m-%d')}<br>Abertura: {o:.2f}<br>Máxima: {h:.2f}<br>Mínima: {l:.2f}<br" +
            f">Fechamento: {c:.2f}" for d,o,h,l,c in zip(df['Date'], df['Open'], df['High'], df['Low'], df['Close'])
        ],
        hoverinfo="text"
    ))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA20"], name="SMA20"))
    if show_sma50 and "SMA50" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA50"], name="SMA50"))
    if show_sma200 and "SMA200" in df.columns:
        fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA200"], name="SMA200"))
    fig.update_layout(title=f"{t} - Preço e Médias", xaxis_title="Data", yaxis_title="Preço (R$)")
    st.plotly_chart(fig, use_container_width=True)

def plot_rsi(df, t):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI14"], name="RSI(14)"))
    fig.add_hline(y=70, line_dash="dash")
    fig.add_hline(y=30, line_dash="dash")
    fig.update_layout(title=f"{t} - RSI(14)", xaxis_title="Data", yaxis_title="RSI")
    st.plotly_chart(fig, use_container_width=True)

# Sidebar
b3 = load_b3_tickers()
st.sidebar.header("⚙️ Configurações")
q = st.sidebar.text_input("Buscar empresa ou ticker", "", help="Você pode digitar o código (ex.: PETR4) ou o nome (ex.: Petrobras).")
res = search_b3(q) if q else b3
ticker = st.sidebar.selectbox("Selecione o ticker", res["ticker"], help="A lista mostra apenas tickers da B3 (.SA).")
start = st.sidebar.date_input("Início", date.today()-timedelta(days=365))
end = st.sidebar.date_input("Fim", date.today())

st.sidebar.markdown("---")
st.sidebar.markdown("**Médias opcionais no gráfico:**")
show_sma50 = st.sidebar.checkbox("Mostrar SMA50 (médio prazo)", value=False)
show_sma200 = st.sidebar.checkbox("Mostrar SMA200 (longo prazo)", value=False)

st.title("📊 Análise Didática de Ações da B3")
st.markdown("> Ferramenta educacional para leitura de indicadores técnicos da B3 🇧🇷")

st.caption("Somente tickers da B3 (.SA) — dados do Yahoo Finance")

if not is_known_b3_ticker(ticker):
    st.error("Ticker fora da lista da B3.")
    st.stop()

with st.spinner("Baixando dados..."):
    df = fetch_data(ticker, start, end)
if df.empty:
    st.warning("Sem dados disponíveis.")
    st.stop()

df = add_indicators(df, want_sma50=show_sma50, want_sma200=show_sma200)
price = float(df["Close"].iloc[-1])
sma20 = float(df["SMA20"].iloc[-1])
rsi_val = float(df["RSI14"].iloc[-1])
delta20 = (price/sma20-1)*100 if sma20 else np.nan

# KPI header
c1,c2,c3 = st.columns(3)
c1.metric("Ticker", ticker)
c2.metric("Fechamento", f"R$ {price:,.2f}".replace(",", "X").replace(".", ",").replace("X","."))
c3.metric("Δ vs SMA20", f"{delta20:+.2f}%" if not np.isnan(delta20) else "—")

# Conditional tone blocks
if not np.isnan(delta20):
    if delta20 < -5:
        st.error("Preço bem abaixo da média (SMA20). Curto prazo pressionado.")
    elif -5 <= delta20 <= 5:
        st.warning("Preço perto da média (SMA20). Curto prazo em equilíbrio.")
    else:
        st.success("Preço acima da média (SMA20). Curto prazo com força.")

if rsi_val < 30:
    st.success("RSI em sobrevenda (≤30). Queda forte recente; pode reagir.")
elif 30 <= rsi_val <= 70:
    st.info("RSI em zona neutra (30–70). Mercado equilibrado.")
else:
    st.warning("RSI em sobrecompra (≥70). Subida forte recente; pode corrigir.")

# Charts
plot_price(df, ticker, show_sma50, show_sma200)
plot_rsi(df, ticker)

# Tip
st.info("Dica: você pode colar PETR4, VALE3, ITUB4, etc. Se digitar sem .SA, a aplicação adiciona automaticamente.")

# --- Tooltip: Como ler candles ---
with st.expander("🕯️ Como ler candles (clique para ver)"):
    st.markdown("""
- **Corpo**: faixa entre **Abertura** e **Fechamento** (grossa).
- **Pavio superior**: até onde o preço **subiu** no período (**Máxima**).
- **Pavio inferior**: até onde o preço **desceu** (**Mínima**).
- **Candle de alta**: fechamento **acima** da abertura.
- **Candle de baixa**: fechamento **abaixo** da abertura.
Passe o mouse nos candles para ver **Abertura, Máxima, Mínima, Fechamento**.
""")

# --- Friendly, conversational explanation ---
st.markdown("---")
st.subheader("💡 O que o gráfico está tentando te contar")

# 1) SMA20 – a linha da média
st.markdown("### 🪜 1. Entendendo a SMA20 — “a linha da média”")
st.markdown(
    "A **SMA20** é como a média dos **últimos 20 preços de fechamento** — a linha de equilíbrio que mostra a **direção geral do preço**."
)
st.markdown("""
- 📈 Se o preço está **acima** da linha, há **força** (tendência de alta).
- 📉 Se está **abaixo**, há **fraqueza** (tendência de queda).
""")
st.markdown(f"👉 No caso de **{ticker}**, o preço atual é **R$ {price:,.2f}**, cerca de **{delta20:+.2f}%** em relação à média dos últimos 20 dias.")
if delta20 < -5:
    st.markdown("🔴 **A ação vem caindo há várias semanas e o mercado está mais pessimista no curto prazo.**")
elif -5 <= delta20 <= 5:
    st.markdown("🟡 **O preço está próximo da média — o mercado está em equilíbrio.**")
else:
    st.markdown("🟢 **O preço está acima da média — o papel mostra força no curto prazo.**")

st.markdown("📉 É como se o preço pudesse ficar **“afastado da linha”** por um tempo; quando isso acontece, pode haver **exagero** — como uma corda muito esticada.")

# 2) RSI – o termômetro da força
st.markdown("---")
st.markdown("### ⚖️ 2. Entendendo o RSI(14) — “o termômetro da força”")
st.markdown("Pense no **RSI** como um **termômetro de energia do mercado**. Vai de **0 a 100** e mostra quem está dominando: **compradores** ou **vendedores**.")
df_rsi = pd.DataFrame({
    "Faixa": ["70 a 100", "50", "0 a 30"],
    "Situação": ["Sobrecompra", "Neutro", "Sobrevenda"],
    "O que significa": [
        "Subiu rápido demais — pode corrigir pra baixo.",
        "Equilíbrio entre compra e venda.",
        "Caiu rápido demais — pode reagir pra cima."
    ]
}).set_index("Faixa")
st.table(df_rsi)
st.markdown(f"No caso de **{ticker}**, o RSI(14) está em **{rsi_val:.1f}**.")
if rsi_val < 30:
    st.markdown("🟢 **Está na zona de sobrevenda — o papel caiu muito e pode reagir em breve.**")
elif 30 <= rsi_val <= 70:
    st.markdown("🟡 **Está em zona neutra — o mercado está equilibrado.**")
else:
    st.markdown("🔴 **Está na zona de sobrecompra — o preço subiu demais e pode corrigir.**")

# 3) Juntando tudo
st.markdown("---")
st.markdown("### 🧩 3. Juntando as duas informações")
st.markdown("""Quando o **preço está bem abaixo da SMA20** e o **RSI está perto de 30**, é como se o mercado dissesse:

🗣️ “Essa ação caiu bastante, está cansada de cair e pode dar um respiro em breve.”

Mas lembre: isso **não garante** que vai subir agora. É só um **sinal de que a pressão de venda está diminuindo**.
""")

# 4) Comportamento de mercado
st.markdown("---")
st.markdown("### 🔍 4. Pensando em comportamento de mercado")
st.code("""Preço ↓↓↓↓↓
SMA20 → uma linha que ficou lá em cima
RSI ↓ até 30""")
st.markdown("""Isso mostra que:
- A **queda foi rápida**;
- O **preço ficou longe da média**;
- E o **RSI sinaliza vendedores perdendo força**.

💡 É o que muitos chamam de **“ponto de atenção”**: se aparecer **volume de compra** nos próximos dias e o preço começar a subir, → pode ser um **repique** (subida temporária após muita queda).
""")

# 5) Resumo final + Glossário
st.markdown("---")
st.markdown("### 💬 Em resumo:")
summary = pd.DataFrame({
    "Indicador":[ "SMA20", "RSI(14)", "Conclusão geral" ],
    "O que está mostrando":[
        "Preço comparado à média de 20 dias",
        "Energia do mercado (0–100)",
        "Combinação de média e força (preço + RSI)"
    ],
    "Significado prático":[
        ("O preço está bem abaixo da média — ação pressionada." if delta20 < -5 else
         "Preço perto da média — mercado em equilíbrio." if -5 <= delta20 <= 5 else
         "Preço acima da média — curto prazo com força."),
        ("Quase no limite da queda — pode surgir oportunidade." if rsi_val < 35 else
         "Equilíbrio; sem sinal claro." if 35 <= rsi_val <= 65 else
         "Pode haver realização/correção."),
        ("Fraca, mas pode estar perto de uma pausa/leve recuperação." if (delta20 < -5 and rsi_val <= 35) else
         "Neutra; acompanhar próximos movimentos." if (-5 <= delta20 <= 5 and 30 <= rsi_val <= 70) else
         "Com força; atenção a exageros se RSI muito alto.")
    ]
})
st.table(summary)

with st.expander("📚 Glossário rápido (clique para abrir)"):
    st.markdown("""
- **Candle**: barra que representa um período; mostra **Abertura, Máxima, Mínima, Fechamento**.
- **SMA (Média Móvel Simples)**: média dos fechamentos de um período, ajuda a ver a tendência.
- **RSI (Índice de Força Relativa)**: mede a velocidade das altas e quedas recentes (0 a 100).
- **Suporte/Resistência**: regiões onde o preço costuma **parar** de cair/subir.
- **Repique**: subida temporária após uma queda forte.
""")
