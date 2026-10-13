# Monitor de menções ao setor bancário no Instagram

Acompanha perfis públicos do Instagram, detecta posts novos e usa o Claude para avaliar, pelo
contexto (legenda + imagens), se o autor critica bancos, o setor bancário ou a FEBRABAN.
Posts críticos acima do limiar de severidade geram alerta (webhook e/ou Telegram).

## Como funciona

1. O GitHub Actions chama `/rodar` a cada 15 min, que executa `monitor.py` e consulta a Instagram Graph API
   (endpoint *Business Discovery*) para cada perfil ativo.
2. Cada post novo é analisado por `analyzer.py` e salvo no Postgres.
3. Se `critica_negativa` e `severidade >= SEVERIDADE_ALERTA`, dispara `notifier.py`.
4. `app.py` é o painel (Flask, com login básico) para gerenciar perfis e ver as análises.

Na primeira carga de um perfil o histórico é analisado, mas não gera alerta.

## Pré-requisitos na Meta

O Business Discovery só lê contas **Comerciais ou de Criador**, e você precisa de uma conta
profissional sua para fazer as consultas.

1. Converta um Instagram seu em conta profissional e vincule a uma Página do Facebook.
2. Em developers.facebook.com, crie um app do tipo Business e adicione o produto Instagram
   (Instagram API com login do Facebook).
3. Gere um token com `instagram_basic`, `pages_show_list` e `pages_read_engagement`.
   Para produção, prefira um **token de usuário de sistema** no Business Manager (não expira);
   tokens long-lived comuns duram ~60 dias.
4. Descubra o `IG_USER_ID`:
   `GET /me/accounts?fields=instagram_business_account` → use o id retornado.
5. Teste: `GET /{IG_USER_ID}?fields=business_discovery.username(instagram){followers_count}`

## Rodando localmente

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencha
flask --app app run    # painel em http://localhost:5000
python monitor.py      # uma rodada manual
```

## Deploy (Render + Supabase + Resend + GitHub Actions)

1. **Supabase:** crie um projeto (região São Paulo). Em Project Settings → Database → Connection
   string, copie a do **Session pooler** e acrescente `?sslmode=require`. As tabelas são criadas
   sozinhas no primeiro start.
2. **Resend:** use um domínio já verificado (ex.: nexapi.com.br) e crie uma API key.
3. **Render:** New → Blueprint → selecione o repositório. Preencha as variáveis pedidas e clique
   em Apply. Copie o `CRON_TOKEN` e o `DASHBOARD_PASSWORD` gerados (aba Environment).
4. **GitHub Actions:** no repositório, Settings → Secrets and variables → Actions, crie
   `APP_URL` (ex.: https://monitor.nexapi.com.br) e `CRON_TOKEN`. Depois, em Actions →
   "Verificar perfis" → Run workflow, faça o primeiro teste.
5. **Domínio (opcional):** no Render, Settings → Custom Domains → `monitor.nexapi.com.br`, e crie
   o CNAME indicado no DNS do domínio.

## Limitações conhecidas

- Não lê Stories, posts de contas pessoais ou privadas, nem comentários.
- Vídeos/Reels são avaliados pela legenda e pela capa; para analisar a fala, seria preciso
  transcrever o áudio (ex.: Whisper) — o Business Discovery nem sempre entrega a URL do vídeo.
- Limite de ~200 chamadas/hora por token: com polling de 15 min dá para ~40 perfis.
