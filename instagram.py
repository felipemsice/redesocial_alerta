"""Coleta posts públicos de contas profissionais via Instagram Graph API (Business Discovery).

Limitações oficiais:
- O perfil monitorado precisa ser conta Comercial ou Criador de conteúdo.
- Não traz Stories nem comentários de terceiros; não existe webhook para contas de
  terceiros, por isso o app faz polling.
- Limite de ~200 chamadas/hora por token.
"""
import os

import requests

CAMPOS = (
    "id,caption,media_type,media_product_type,media_url,thumbnail_url,"
    "permalink,timestamp,children{media_type,media_url}"
)


class InstagramErro(RuntimeError):
    pass


def posts_recentes(username: str, limite: int = 10) -> list[dict]:
    versao = os.getenv("GRAPH_VERSION", "v21.0")
    ig_user_id = os.environ["IG_USER_ID"]
    params = {
        "fields": f"business_discovery.username({username}){{media.limit({limite}){{{CAMPOS}}}}}",
        "access_token": os.environ["IG_ACCESS_TOKEN"],
    }
    r = requests.get(f"https://graph.facebook.com/{versao}/{ig_user_id}", params=params, timeout=30)
    dados = r.json()
    if "error" in dados:
        e = dados["error"]
        raise InstagramErro(f"[{e.get('code')}] {e.get('message')}")
    return dados.get("business_discovery", {}).get("media", {}).get("data", [])
