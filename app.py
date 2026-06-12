import streamlit as st
from google import genai
from google.genai import types
import time
import datetime
import os
import json
import pathlib

# ── Configuração da página ──────────────────────────────────────────────────
st.set_page_config(
    page_title="Consultor ITR – Geoperícias",
    page_icon="🌾",
    layout="centered",
)

# ── Constantes ───────────────────────────────────────────────────────────────
SESSION_DURATION_MINUTES = 30
MAX_MESSAGES = 20  # segurança extra além do tempo

# ── Senhas dos municípios (edite aqui ou carregue de secrets) ────────────────
# Formato: "CÓDIGO": "Nome do Município"
# No Streamlit Cloud, coloque em st.secrets["municipios"] como TOML
def load_municipios():
    # Tenta carregar de st.secrets (produção)
    try:
        return dict(st.secrets["municipios"])
    except Exception:
        pass
    # Fallback local para desenvolvimento
    return {
        "ITR2024MT": "Município de Tapurah/MT",
        "ITR2024MS": "Município de Campo Grande/MS",
        "DEMO2024":  "Acesso Demonstração",
    }

MUNICIPIOS = load_municipios()

# ── System prompt (adicione seus documentos aqui) ────────────────────────────
SYSTEM_PROMPT = """Você é um consultor técnico especializado em ITR (Imposto Territorial Rural) da Geoperícias Avaliações e Tecnologia Ltda.

Seu papel é auxiliar fiscais e técnicos municipais conveniados com a Receita Federal na fiscalização do ITR, respondendo dúvidas sobre:

- Legislação ITR: CF/1988 art. 153 VI §4º, CTN arts. 29–31, Lei 9.393/1996, Decreto 4.382/2002
- Procedimentos fiscais: TIF, TCIF, NL, lançamento de ofício, DITR, malha fiscal
- Áreas não tributáveis: APP, Reserva Legal, Floresta Nativa, áreas alagadas
- VTN e laudos técnicos: NBR 14653-3, IN RFB 256/2002, método comparativo direto
- Impugnações e PAF: Decreto 70.235/1972, prazos, PRDI, Despacho Decisório
- Convênio ITR: Lei 11.250/2005, IN RFB 1.640/2016, NE COFIS 02/2013
- CAR e georreferenciamento: Lei 12.651/2012, SIGEF, INCRA

REGRAS DE CONDUTA:
1. Responda sempre em português, de forma técnica mas clara
2. Cite a base legal sempre que possível
3. Se não souber com certeza, diga explicitamente e oriente a consultar a RFB
4. Não forneça pareceres sobre casos individuais de contribuintes específicos
5. Não divulgue dados sigilosos (CTN art. 198)
6. Mantenha foco em ITR municipal — redirecione perguntas fora do escopo

=== DOCUMENTOS DE REFERÊNCIA ===
Os documentos técnicos de referência (legislação, manuais, NE COFIS, laudos, etc.)
são fornecidos diretamente como arquivos PDF em cada sessão via Gemini Files API.
Utilize o conteúdo desses documentos como base prioritária nas suas respostas.
===============================
"""

# ── CSS customizado ──────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main-header {
        background: linear-gradient(135deg, #1a5276 0%, #2e86ab 100%);
        padding: 1.5rem 2rem;
        border-radius: 12px;
        color: white;
        margin-bottom: 1.5rem;
    }
    .main-header h1 { margin: 0; font-size: 1.6rem; }
    .main-header p  { margin: 0.3rem 0 0; opacity: 0.85; font-size: 0.9rem; }

    .session-info {
        background: #2e86ab;
        border-left: 4px solid #1a5276;
        padding: 0.6rem 1rem;
        border-radius: 6px;
        font-size: 0.85rem;
        margin-bottom: 1rem;
        color: #ffffff !important;
    }
    .session-expired {
        background: #fdecea;
        border-left: 4px solid #e74c3c;
        padding: 0.6rem 1rem;
        border-radius: 6px;
        font-size: 0.9rem;
    }
    .stChatMessage { border-radius: 10px; }
    .footer {
        text-align: center;
        font-size: 0.75rem;
        color: #888;
        margin-top: 2rem;
        padding-top: 1rem;
        border-top: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# ── Inicialização do estado ──────────────────────────────────────────────────
def init_state():
    defaults = {
        "authenticated": False,
        "municipio_nome": "",
        "session_start": None,
        "messages": [],
        "gemini_history": [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_state()

# ── Helpers ──────────────────────────────────────────────────────────────────
def tempo_restante():
    if not st.session_state.session_start:
        return 0
    elapsed = (datetime.datetime.now() - st.session_state.session_start).total_seconds()
    remaining = SESSION_DURATION_MINUTES * 60 - elapsed
    return max(0, remaining)

def sessao_expirada():
    return st.session_state.authenticated and tempo_restante() <= 0

def formatar_tempo(segundos):
    m = int(segundos // 60)
    s = int(segundos % 60)
    return f"{m:02d}:{s:02d}"

@st.cache_resource(show_spinner="Carregando documentos de referência ITR...")
def get_itr_files():
    """Faz upload dos PDFs da pasta docs/ para a Gemini Files API (uma vez por instância)."""
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        return []

    client = genai.Client(api_key=api_key)
    docs_dir = pathlib.Path(__file__).parent / "docs"
    if not docs_dir.exists():
        return []

    pdf_files = sorted(docs_dir.glob("*.pdf"))
    if not pdf_files:
        return []

    uploaded = []
    for pdf in pdf_files:
        try:
            f = client.files.upload(file=str(pdf), config={"mime_type": "application/pdf"})
            uploaded.append(f)
        except Exception:
            pass
    return uploaded


def get_gemini_client():
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        st.error("⚠️ Chave GEMINI_API_KEY não configurada. Contate o administrador.")
        st.stop()
    return genai.Client(api_key=api_key)

# ── Tela de login ────────────────────────────────────────────────────────────
def tela_login():
    st.markdown("""
    <div class="main-header">
        <h1>🌾 Consultor ITR</h1>
        <p>Geoperícias Avaliações e Tecnologia Ltda. — Suporte Técnico Municipal</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("### Acesso Restrito")
    st.markdown("Informe o código fornecido pela Geoperícias para iniciar sua sessão de consulta.")

    with st.form("login_form"):
        codigo = st.text_input("Código de acesso", placeholder="Ex: ITR2024MT", max_chars=30)
        entrar = st.form_submit_button("Entrar →", use_container_width=True)

        if entrar:
            codigo_upper = codigo.strip().upper()
            if codigo_upper in MUNICIPIOS:
                st.session_state.authenticated = True
                st.session_state.municipio_nome = MUNICIPIOS[codigo_upper]
                st.session_state.session_start = datetime.datetime.now()
                st.session_state.messages = []
                st.session_state.gemini_history = []
                st.rerun()
            else:
                st.error("Código inválido. Verifique com a Geoperícias.")

    st.markdown("""
    <div class="footer">
        Geoperícias Avaliações e Tecnologia Ltda. · Campo Grande/MS<br>
        Suporte técnico: (67) XXXX-XXXX
    </div>
    """, unsafe_allow_html=True)

# ── Tela de sessão expirada ──────────────────────────────────────────────────
def tela_expirada():
    st.markdown("""
    <div class="main-header">
        <h1>🌾 Consultor ITR</h1>
        <p>Geoperícias Avaliações e Tecnologia Ltda.</p>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="session-expired">
        ⏱️ <strong>Sessão encerrada.</strong><br>
        Sua sessão de {SESSION_DURATION_MINUTES} minutos para <strong>{st.session_state.municipio_nome}</strong> foi concluída.<br>
        Para uma nova sessão, entre em contato com a Geoperícias.
    </div>
    """, unsafe_allow_html=True)

    if st.button("← Voltar ao login"):
        for k in ["authenticated", "municipio_nome", "session_start", "messages", "gemini_history"]:
            st.session_state[k] = False if k == "authenticated" else ([] if k in ["messages","gemini_history"] else None if k == "session_start" else "")
        st.rerun()

# ── Tela principal de chat ───────────────────────────────────────────────────
def tela_chat():
    restante = tempo_restante()
    msgs_count = len([m for m in st.session_state.messages if m["role"] == "user"])

    # Header
    st.markdown(f"""
    <div class="main-header">
        <h1>🌾 Consultor ITR</h1>
        <p>{st.session_state.municipio_nome} · Suporte Técnico Geoperícias</p>
    </div>
    """, unsafe_allow_html=True)

    # Info de sessão
    st.markdown(f"""
    <div class="session-info">
        ⏱️ Tempo restante: <strong>{formatar_tempo(restante)}</strong> &nbsp;|&nbsp;
        💬 Perguntas: <strong>{msgs_count}/{MAX_MESSAGES}</strong> &nbsp;|&nbsp;
        🏛️ {st.session_state.municipio_nome}
    </div>
    """, unsafe_allow_html=True)

    # Histórico de mensagens
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # Limite de mensagens
    if msgs_count >= MAX_MESSAGES:
        st.warning(f"Limite de {MAX_MESSAGES} perguntas atingido nesta sessão.")
        st.stop()

    # Input
    if prompt := st.chat_input("Digite sua dúvida sobre ITR..."):
        # Adiciona mensagem do usuário
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        # Chama Gemini
        with st.chat_message("assistant"):
            with st.spinner("Consultando base de conhecimento..."):
                try:
                    client = get_gemini_client()
                    itr_files = get_itr_files()

                    file_context = []
                    if itr_files:
                        file_parts = [
                            types.Part(file_data=types.FileData(file_uri=f.uri, mime_type="application/pdf"))
                            for f in itr_files
                        ]
                        file_parts.append(types.Part(text="Use estes documentos como referência principal nas suas respostas sobre ITR."))
                        file_context = [
                            types.Content(role="user", parts=file_parts),
                            types.Content(role="model", parts=[types.Part(text="Documentos recebidos. Pronto para responder sobre ITR.")]),
                        ]

                    history_contents = [
                        types.Content(role=m["role"], parts=[types.Part(text=p) for p in m["parts"]])
                        for m in st.session_state.gemini_history
                    ]

                    chat = client.chats.create(
                        model="gemini-2.0-flash",
                        config=types.GenerateContentConfig(system_instruction=SYSTEM_PROMPT),
                        history=file_context + history_contents,
                    )
                    response = chat.send_message(prompt)
                    answer = response.text

                    st.session_state.gemini_history.append({"role": "user", "parts": [prompt]})
                    st.session_state.gemini_history.append({"role": "model", "parts": [answer]})

                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})
                    st.session_state["_ok"] = True

                except Exception as e:
                    st.session_state["_ok"] = False
                    st.error(f"Erro: {e}")

    if st.session_state.pop("_ok", False):
        st.rerun()

    st.markdown("""
    <div class="footer">
        Geoperícias Avaliações e Tecnologia Ltda. · As respostas têm caráter orientativo e não substituem análise jurídica formal.
    </div>
    """, unsafe_allow_html=True)

# ── Roteamento ───────────────────────────────────────────────────────────────
if not st.session_state.authenticated:
    tela_login()
elif sessao_expirada():
    tela_expirada()
else:
    tela_chat()
