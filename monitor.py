"""Rodada de monitoramento. Executado pelo Cron Job do Render (ou pela rota /rodar)."""
import logging
import os
from datetime import datetime

from dotenv import load_dotenv

load_dotenv()

from analyzer import analisar  # noqa: E402
from db import Perfil, Post, Session, init_db  # noqa: E402
from instagram import InstagramErro, posts_recentes  # noqa: E402
from notifier import alertar  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("monitor")


def rodar() -> dict:
    init_db()
    limiar = int(os.getenv("SEVERIDADE_ALERTA", "2"))
    stats = {"perfis": 0, "novos": 0, "criticos": 0, "erros": 0}

    with Session() as s:
        for perfil in s.query(Perfil).filter_by(ativo=True).all():
            stats["perfis"] += 1
            # 1ª carga de um perfil: analisa o histórico mas não dispara alerta
            primeira_carga = s.query(Post).filter_by(username=perfil.username).first() is None
            try:
                midias = posts_recentes(perfil.username)
            except InstagramErro as e:
                log.error("@%s: %s", perfil.username, e)
                stats["erros"] += 1
                continue

            for m in midias:
                if s.get(Post, m["id"]):
                    continue
                post = Post(
                    id=m["id"], username=perfil.username, tipo=m.get("media_type", ""),
                    legenda=m.get("caption"), permalink=m.get("permalink", ""),
                    publicado_em=datetime.strptime(m["timestamp"], "%Y-%m-%dT%H:%M:%S%z"),
                )
                try:
                    a = analisar(m, perfil.username)
                    post.analise = a
                    post.critica = bool(a.get("critica_negativa"))
                    post.severidade = int(a.get("severidade", 0))
                except Exception as e:  # registra e segue; dá pra reprocessar depois
                    post.erro = str(e)[:500]
                    stats["erros"] += 1
                s.add(post)
                s.commit()
                stats["novos"] += 1

                if post.critica and post.severidade >= limiar:
                    stats["criticos"] += 1
                    if not primeira_carga:
                        try:
                            alertar(post)
                            post.alertado = True
                            s.commit()
                        except Exception as e:
                            log.error("Falha ao alertar %s: %s", post.id, e)

    log.info("Rodada concluída: %s", stats)
    return stats


if __name__ == "__main__":
    rodar()
