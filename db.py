import os
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker

url = os.getenv("DATABASE_URL", "sqlite:///local.db")
if url.startswith("postgres://"):  # Render às vezes entrega nesse formato
    url = url.replace("postgres://", "postgresql://", 1)

engine = create_engine(url, pool_pre_ping=True, pool_size=3, max_overflow=2, pool_recycle=300) if not url.startswith("sqlite") else create_engine(url)
Session = sessionmaker(engine, expire_on_commit=False)


def agora():
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Perfil(Base):
    __tablename__ = "perfis"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(100), unique=True)
    ativo: Mapped[bool] = mapped_column(default=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)


class Post(Base):
    __tablename__ = "posts"
    id: Mapped[str] = mapped_column(String(64), primary_key=True)  # media id do Instagram
    username: Mapped[str] = mapped_column(String(100), index=True)
    tipo: Mapped[str] = mapped_column(String(30))
    legenda: Mapped[str | None] = mapped_column(Text)
    permalink: Mapped[str] = mapped_column(String(300))
    publicado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    detectado_em: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=agora)
    analise: Mapped[dict | None] = mapped_column(JSON)
    critica: Mapped[bool] = mapped_column(default=False, index=True)
    severidade: Mapped[int] = mapped_column(default=0)
    alertado: Mapped[bool] = mapped_column(default=False)
    erro: Mapped[str | None] = mapped_column(Text)


def init_db():
    Base.metadata.create_all(engine)
