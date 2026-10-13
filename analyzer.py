"""Análise de contexto com Claude: decide se o post critica bancos/setor bancário/FEBRABAN."""
import base64
import os

import anthropic
import requests

MAX_IMAGENS = 4

SISTEMA = """Você é analista de reputação do setor bancário brasileiro. Recebe um post de Instagram
(legenda e, quando houver, imagens) e avalia se o autor está criticando bancos, o setor bancário
ou a FEBRABAN. Leia o CONTEXTO, não só palavras-chave.

Regras de interpretação:
- Crítica é quando o autor atribui culpa, acusa, ridiculariza, incentiva boicote ou desconfiança
  em relação a bancos (um específico ou em geral), ao sistema bancário ou à FEBRABAN.
- NÃO é crítica: alerta de golpe que usa nome de banco sem culpar o banco; notícia neutra;
  publicidade/parceria paga com banco; dica de educação financeira sem ataque.
- Comparação "fintech vs. bancões" que desqualifica os bancos tradicionais CONTA como crítica.
- Considere ironia, sarcasmo, memes e texto dentro das imagens.
- Temas comuns: juros, tarifas, spread, cartão/rotativo, Pix, golpes/fraudes, atendimento,
  lucros, endividamento, regulação, lobby.

Escala de severidade:
0 = sem crítica ou sem relação com bancos
1 = reclamação leve ou passageira
2 = crítica clara, tom moderado
3 = crítica forte ou recorrente, com chance de repercussão
4 = acusação grave, chamada à ação (boicote, denúncia) ou desinformação
5 = ataque direto e grave à FEBRABAN ou ao setor, com alto potencial de viralizar

Seja preciso: na dúvida entre crítica e não crítica, use confiança baixa e explique."""

SCHEMA = {
    "type": "object",
    "properties": {
        "relacionado_a_bancos": {"type": "boolean"},
        "menciona_febraban": {"type": "boolean"},
        "entidades_citadas": {"type": "array", "items": {"type": "string"},
                              "description": "Bancos, instituições ou órgãos citados no texto ou imagem"},
        "tom": {"type": "string", "enum": ["critico", "neutro", "positivo", "informativo", "nao_relacionado"]},
        "critica_negativa": {"type": "boolean"},
        "alvo_da_critica": {"type": "array", "items": {"type": "string"},
                            "description": "Ex.: 'bancos em geral', 'Banco X', 'FEBRABAN'"},
        "temas": {"type": "array", "items": {"type": "string"}},
        "ironia_ou_sarcasmo": {"type": "boolean"},
        "severidade": {"type": "integer", "minimum": 0, "maximum": 5},
        "trecho_relevante": {"type": "string", "description": "Trecho curto que embasa a conclusão"},
        "justificativa": {"type": "string", "description": "2 a 4 frases explicando o contexto"},
        "confianca": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["relacionado_a_bancos", "menciona_febraban", "tom", "critica_negativa",
                 "severidade", "justificativa", "confianca"],
}

_cliente = None


def _client():
    global _cliente
    if _cliente is None:
        _cliente = anthropic.Anthropic()
    return _cliente


def _imagens(post: dict) -> list[dict]:
    tipo = post.get("media_type")
    if tipo == "CAROUSEL_ALBUM":
        urls = [c.get("media_url") for c in post.get("children", {}).get("data", [])
                if c.get("media_type") == "IMAGE"]
    elif tipo == "IMAGE":
        urls = [post.get("media_url")]
    else:  # VIDEO / REELS: usa a capa
        urls = [post.get("thumbnail_url")]

    blocos = []
    for url in [u for u in urls if u][:MAX_IMAGENS]:
        try:
            r = requests.get(url, timeout=20)
            r.raise_for_status()
            mime = r.headers.get("content-type", "image/jpeg").split(";")[0]
            if mime not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
                continue
            blocos.append({"type": "image", "source": {
                "type": "base64", "media_type": mime,
                "data": base64.b64encode(r.content).decode()}})
        except requests.RequestException:
            continue
    return blocos


def analisar(post: dict, username: str) -> dict:
    texto = (
        f"Autor: @{username}\n"
        f"Formato: {post.get('media_product_type') or post.get('media_type')}\n"
        f"Publicado em: {post.get('timestamp')}\n"
        f"Legenda:\n{post.get('caption') or '(sem legenda)'}"
    )
    resp = _client().messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5"),
        max_tokens=1024,
        system=SISTEMA,
        tools=[{"name": "registrar_analise",
                "description": "Registra a análise estruturada do post.",
                "input_schema": SCHEMA}],
        tool_choice={"type": "tool", "name": "registrar_analise"},
        messages=[{"role": "user", "content": _imagens(post) + [{"type": "text", "text": texto}]}],
    )
    for bloco in resp.content:
        if bloco.type == "tool_use":
            return bloco.input
    raise RuntimeError("Claude não retornou a análise estruturada")
