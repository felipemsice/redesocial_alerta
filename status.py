"""Página de status diário por perfil + API JSON que a alimenta."""
import os
from collections import defaultdict
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from flask import Blueprint, abort, jsonify, request, send_from_directory

from auth import protegido
from db import Perfil, Post, Session, engine

bp = Blueprint("status", __name__)
TZ = ZoneInfo(os.getenv("TZ_LOCAL", "America/Sao_Paulo"))
SQLITE = engine.dialect.name == "sqlite"


def _limiar() -> int:
    return int(os.getenv("SEVERIDADE_ALERTA", "2"))


def _para_db(dt: datetime) -> datetime:
    """Converte para UTC; no SQLite as datas ficam gravadas sem fuso."""
    dt = dt.astimezone(timezone.utc)
    return dt.replace(tzinfo=None) if SQLITE else dt


def _local(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def _intervalo(ini: date, fim: date):
    a = datetime.combine(ini, time.min, tzinfo=TZ)
    b = datetime.combine(fim, time.min, tzinfo=TZ) + timedelta(days=1)
    return _para_db(a), _para_db(b)


def _username_valido(username: str) -> str:
    username = username.strip().lstrip("@").lower()
    with Session() as s:
        if not s.query(Perfil).filter_by(username=username).first():
            abort(404, description="Perfil não cadastrado")
    return username


def _serializa(p: Post) -> dict:
    a = p.analise or {}
    return {
        "id": p.id,
        "hora": _local(p.publicado_em).strftime("%H:%M"),
        "minuto_do_dia": _local(p.publicado_em).hour * 60 + _local(p.publicado_em).minute,
        "tipo": p.tipo,
        "legenda": p.legenda or "",
        "permalink": p.permalink,
        "critica": p.critica,
        "severidade": p.severidade,
        "alertado": p.alertado,
        "erro": p.erro,
        "tom": a.get("tom"),
        "justificativa": a.get("justificativa"),
        "trecho": a.get("trecho_relevante"),
        "alvos": a.get("alvo_da_critica") or [],
        "temas": a.get("temas") or [],
        "confianca": a.get("confianca"),
        "menciona_febraban": a.get("menciona_febraban", False),
    }


def _status(posts: list[dict]) -> str:
    if not posts:
        return "sem_posts"
    if any(p["critica"] and p["severidade"] >= _limiar() for p in posts):
        return "critico"
    if any(p["critica"] or p["erro"] for p in posts):
        return "atencao"
    return "tranquilo"


@bp.get("/status")
@protegido
def pagina():
    return send_from_directory("static", "status.html")


@bp.get("/api/perfis")
@protegido
def perfis():
    with Session() as s:
        return jsonify([{"username": p.username, "ativo": p.ativo}
                        for p in s.query(Perfil).order_by(Perfil.username)])


@bp.get("/api/status/<username>")
@protegido
def status_do_dia(username):
    username = _username_valido(username)
    try:
        dia = date.fromisoformat(request.args.get("data", ""))
    except ValueError:
        dia = datetime.now(TZ).date()

    ini, fim = _intervalo(dia, dia)
    with Session() as s:
        posts = (s.query(Post).filter(Post.username == username,
                                      Post.publicado_em >= ini, Post.publicado_em < fim)
                 .order_by(Post.publicado_em).all())
        ultimo = (s.query(Post).filter_by(username=username)
                  .order_by(Post.publicado_em.desc()).first())
        ultima_deteccao = (s.query(Post.detectado_em).filter_by(username=username)
                           .order_by(Post.detectado_em.desc()).first())

    itens = [_serializa(p) for p in posts]
    return jsonify({
        "username": username,
        "data": dia.isoformat(),
        "hoje": datetime.now(TZ).date().isoformat(),
        "limiar": _limiar(),
        "status": _status(itens),
        "resumo": {
            "total": len(itens),
            "criticos": sum(p["critica"] for p in itens),
            "alertados": sum(p["alertado"] for p in itens),
            "severidade_max": max((p["severidade"] for p in itens), default=0),
            "menciona_febraban": any(p["menciona_febraban"] for p in itens),
        },
        "ultimo_post": _local(ultimo.publicado_em).isoformat() if ultimo else None,
        "ultima_deteccao": _local(ultima_deteccao[0]).isoformat() if ultima_deteccao else None,
        "posts": itens,
    })


@bp.get("/api/historico/<username>")
@protegido
def historico(username):
    username = _username_valido(username)
    dias = max(1, min(int(request.args.get("dias", 30)), 90))
    fim = datetime.now(TZ).date()
    ini = fim - timedelta(days=dias - 1)
    a, b = _intervalo(ini, fim)

    with Session() as s:
        posts = s.query(Post).filter(Post.username == username,
                                     Post.publicado_em >= a, Post.publicado_em < b).all()

    por_dia = defaultdict(lambda: {"total": 0, "criticos": 0, "severidade_max": 0})
    for p in posts:
        d = por_dia[_local(p.publicado_em).date().isoformat()]
        d["total"] += 1
        d["criticos"] += int(p.critica)
        d["severidade_max"] = max(d["severidade_max"], p.severidade if p.critica else 0)

    saida = []
    for i in range(dias):
        dia = (ini + timedelta(days=i)).isoformat()
        saida.append({"data": dia, **por_dia.get(dia, {"total": 0, "criticos": 0, "severidade_max": 0})})
    return jsonify(saida)
