import hmac
import os
import threading

from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, url_for

load_dotenv()

from auth import protegido  # noqa: E402
from db import Perfil, Post, Session, init_db  # noqa: E402
from monitor import rodar  # noqa: E402

from status import bp as status_bp  # noqa: E402

app = Flask(__name__)
app.register_blueprint(status_bp)
init_db()


@app.get("/")
@protegido
def painel():
    filtro = request.args.get("filtro", "criticos")
    with Session() as s:
        q = s.query(Post).order_by(Post.publicado_em.desc())
        if filtro == "criticos":
            q = q.filter(Post.critica.is_(True))
        posts = q.limit(200).all()
        perfis = s.query(Perfil).order_by(Perfil.username).all()
        total_criticos = s.query(Post).filter(Post.critica.is_(True)).count()
    return render_template("painel.html", posts=posts, perfis=perfis, filtro=filtro,
                           total_criticos=total_criticos)


@app.post("/perfis")
@protegido
def adicionar_perfil():
    username = request.form.get("username", "").strip().lstrip("@").lower()
    if username:
        with Session() as s:
            if not s.query(Perfil).filter_by(username=username).first():
                s.add(Perfil(username=username))
                s.commit()
    return redirect(url_for("painel"))


@app.post("/perfis/<int:perfil_id>/alternar")
@protegido
def alternar_perfil(perfil_id):
    with Session() as s:
        p = s.get(Perfil, perfil_id) or abort(404)
        p.ativo = not p.ativo
        s.commit()
    return redirect(url_for("painel"))


@app.post("/rodar-agora")
@protegido
def rodar_agora():
    threading.Thread(target=rodar, daemon=True).start()
    return redirect(url_for("painel"))


@app.post("/rodar")
def rodar_externo():
    """Alternativa ao Cron Job pago: um agendador externo chama esta rota com o token."""
    token = os.getenv("CRON_TOKEN", "")
    if not token or not hmac.compare_digest(request.headers.get("X-Cron-Token", ""), token):
        abort(403)
    return jsonify(rodar())


@app.get("/health")
def health():
    return {"ok": True}
