import html
import logging
import os

import requests

log = logging.getLogger("notifier")
CORES = {1: "#D4B24A", 2: "#E08A3C", 3: "#CF5737", 4: "#AE2639", 5: "#73102E"}


def _resumo(post) -> str:
    a = post.analise or {}
    return (
        f"⚠️ Post crítico de @{post.username} (severidade {post.severidade}/5)\n"
        f"Alvo: {', '.join(a.get('alvo_da_critica') or []) or '-'}\n"
        f"Temas: {', '.join(a.get('temas') or []) or '-'}\n"
        f"{a.get('justificativa', '')}\n{post.permalink}"
    )


def _html(post) -> str:
    a = post.analise or {}
    e = lambda t: html.escape(str(t or ""))  # noqa: E731
    cor = CORES.get(post.severidade, "#5B6875")
    trecho = f'<p style="border-left:3px solid #CAD3DC;padding-left:10px;color:#5B6875;font-style:italic">{e(a.get("trecho_relevante"))}</p>' if a.get("trecho_relevante") else ""
    return f"""<div style="font-family:Arial,sans-serif;max-width:560px;color:#18212B">
  <p style="margin:0 0 4px;color:{cor};font-weight:bold">Severidade {post.severidade} de 5</p>
  <h2 style="margin:0 0 12px">Crítica identificada em post de @{e(post.username)}</h2>
  <p>{e(a.get('justificativa'))}</p>{trecho}
  <p style="color:#5B6875;font-size:14px">Alvo: {e(', '.join(a.get('alvo_da_critica') or []) or '-')}<br>
  Temas: {e(', '.join(a.get('temas') or []) or '-')}</p>
  <p><a href="{e(post.permalink)}" style="background:#1F4E8C;color:#fff;padding:10px 16px;border-radius:6px;text-decoration:none">Abrir post no Instagram</a></p>
</div>"""


def _email(post) -> None:
    chave, para = os.getenv("RESEND_API_KEY"), os.getenv("ALERTA_EMAIL_PARA")
    if not (chave and para):
        return
    r = requests.post(
        "https://api.resend.com/emails",
        headers={"Authorization": f"Bearer {chave}"},
        json={
            "from": os.getenv("ALERTA_EMAIL_DE", "Monitor <onboarding@resend.dev>"),
            "to": [x.strip() for x in para.split(",") if x.strip()],
            "subject": f"[Sev. {post.severidade}] Crítica em post de @{post.username}",
            "html": _html(post),
            "text": _resumo(post),
        },
        timeout=15,
    )
    r.raise_for_status()


def alertar(post) -> None:
    falhas = []
    canais = []

    if os.getenv("RESEND_API_KEY"):
        canais.append(("e-mail", lambda: _email(post)))

    webhook = os.getenv("WEBHOOK_URL")
    if webhook:  # n8n, Make etc.
        canais.append(("webhook", lambda: requests.post(webhook, timeout=15, json={
            "texto": _resumo(post), "post_id": post.id, "username": post.username,
            "severidade": post.severidade, "permalink": post.permalink,
            "analise": post.analise or {}}).raise_for_status()))

    token, chat = os.getenv("TELEGRAM_BOT_TOKEN"), os.getenv("TELEGRAM_CHAT_ID")
    if token and chat:
        canais.append(("telegram", lambda: requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat, "text": _resumo(post)}, timeout=15).raise_for_status()))

    for nome, enviar in canais:  # um canal com falha não impede os outros
        try:
            enviar()
        except Exception as e:
            log.error("Falha no canal %s: %s", nome, e)
            falhas.append(nome)

    if canais and len(falhas) == len(canais):
        raise RuntimeError(f"Todos os canais falharam: {', '.join(falhas)}")
