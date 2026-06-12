# Consultor ITR – Geoperícias

App de perguntas e respostas sobre ITR para municípios conveniados.

## Estrutura

```
itr_assistant/
├── app.py                    # App principal
├── requirements.txt          # Dependências
├── .gitignore
└── .streamlit/
    └── secrets.toml          # Chaves e senhas (NÃO subir ao GitHub)
```

## Configuração em 4 passos

### 1. Chave Gemini (gratuita)
- Acesse https://aistudio.google.com/apikey
- Crie uma chave e cole em `secrets.toml` no campo `GEMINI_API_KEY`

### 2. Adicionar documentos ITR
- Abra `app.py` e localize a seção `SYSTEM_PROMPT`
- Cole o conteúdo dos seus documentos ITR onde está indicado:
  `[Cole aqui o conteúdo dos seus documentos ITR]`
- Quanto mais conteúdo, melhor a qualidade (Gemini suporta ~700k palavras)

### 3. Configurar municípios e senhas
- Edite `.streamlit/secrets.toml` na seção `[municipios]`
- Adicione um código por município:
  ```toml
  [municipios]
  "TAPURAH24" = "Município de Tapurah/MT"
  "RONDONOPOLIS24" = "Município de Rondonópolis/MT"
  ```

### 4. Deploy no Streamlit Cloud (gratuito)
1. Suba o projeto para um repositório GitHub **privado**
   (não inclua o `secrets.toml` — já está no `.gitignore`)
2. Acesse https://share.streamlit.io
3. Conecte o repositório e selecione `app.py`
4. Em **Settings > Secrets**, cole o conteúdo do `secrets.toml`
5. Clique em **Deploy** — o link estará disponível em ~2 minutos

## Uso

- Envie o link do app + código de acesso para o município
- O fiscal entra o código e tem 30 minutos de sessão
- Para nova sessão, precisa entrar em contato com a Geoperícias (controle comercial)

## Ajustes comuns

| Parâmetro | Onde alterar | Padrão |
|-----------|-------------|--------|
| Duração da sessão | `app.py` → `SESSION_DURATION_MINUTES` | 30 min |
| Limite de perguntas | `app.py` → `MAX_MESSAGES` | 20 |
| Modelo Gemini | `app.py` → `model_name` | gemini-1.5-pro |

## Modelo Gemini gratuito

O tier gratuito do Gemini 1.5 Pro permite:
- 2 requisições por minuto
- 50 requisições por dia
- Contexto de 1 milhão de tokens

Para mais municípios simultâneos, considere `gemini-1.5-flash` (mais rápido, gratuito, 1500 req/dia).
