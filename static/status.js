(() => {
  const $ = (id) => document.getElementById(id);
  const REFRESH_MS = 60_000;
  const ROTULO_STATUS = {
    sem_posts: "Sem posts", tranquilo: "Tranquilo", atencao: "Atenção", critico: "Crítico",
  };
  const ROTULO_TIPO = { IMAGE: "Foto", VIDEO: "Vídeo", CAROUSEL_ALBUM: "Carrossel" };

  let estado = { username: null, dia: null, hoje: null };
  let timer = null;

  // Cria elementos sem innerHTML: legendas vêm da internet e não podem virar HTML.
  function el(tag, props = {}, ...filhos) {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(props)) {
      if (v == null || v === false) continue;
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else n.setAttribute(k, v === true ? "" : v);
    }
    for (const f of filhos.flat()) if (f != null) n.append(f);
    return n;
  }

  async function api(caminho) {
    const r = await fetch(caminho, { credentials: "same-origin" });
    if (!r.ok) throw new Error(`${r.status} ao carregar ${caminho}`);
    return r.json();
  }

  const hojeLocal = () => {
    const d = new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
  };
  const somaDias = (iso, n) => {
    const d = new Date(iso + "T12:00:00");
    d.setDate(d.getDate() + n);
    return d.toISOString().slice(0, 10);
  };
  const dataLonga = (iso) =>
    new Date(iso + "T12:00:00").toLocaleDateString("pt-BR", { weekday: "long", day: "numeric", month: "long" });
  const dataHora = (iso) =>
    iso ? new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—";
  const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;

  function atualizarUrl() {
    const u = new URL(location.href);
    u.searchParams.set("u", estado.username);
    u.searchParams.set("d", estado.dia);
    history.replaceState(null, "", u);
  }

  // ---------- Manchete ----------
  function renderManchete(dados) {
    const { resumo, status } = dados;
    const ehHoje = dados.data === dados.hoje;
    const quando = ehHoje ? "Hoje" : dataLonga(dados.data).replace(/^./, (c) => c.toUpperCase()) + ",";

    const est = $("estado");
    est.className = `estado ${status}`;
    est.textContent = ROTULO_STATUS[status];

    let frase;
    if (resumo.total === 0) {
      frase = `${quando} @${dados.username} não publicou nada${ehHoje ? " até agora" : ""}.`;
    } else {
      frase = `${quando} @${dados.username} publicou ${plural(resumo.total, "vez", "vezes")}`;
      frase += resumo.criticos === 0
        ? ", sem crítica a bancos."
        : ` e ${plural(resumo.criticos, "post critica", "posts criticam")} bancos ou a FEBRABAN.`;
    }
    $("frase").textContent = frase;

    const partes = [];
    if (resumo.total) partes.push(`Severidade máxima ${resumo.severidade_max} de 5 (alerta a partir de ${dados.limiar})`);
    if (resumo.alertados) partes.push(plural(resumo.alertados, "alerta enviado", "alertas enviados"));
    if (resumo.menciona_febraban) partes.push("FEBRABAN citada");
    partes.push(`Último post do perfil: ${dataHora(dados.ultimo_post)}`);
    $("meta").textContent = partes.join(". ") + ".";
  }

  // ---------- Linha do tempo de 24h ----------
  function renderTrilha(dados) {
    const trilha = $("trilha");
    trilha.replaceChildren();

    if (dados.data === dados.hoje) {
      const agora = new Date();
      const pct = ((agora.getHours() * 60 + agora.getMinutes()) / 1440) * 100;
      trilha.append(el("div", { class: "agora", style: `left:${pct}%` }));
    }

    // menor severidade primeiro, para os marcos maiores ficarem por cima
    [...dados.posts].sort((a, b) => a.severidade - b.severidade).forEach((p) => {
      const sev = p.critica ? p.severidade : 0;
      const descr = `${p.hora}: ${p.critica ? `crítica, severidade ${p.severidade}` : "sem crítica"}`;
      trilha.append(el("button", {
        class: `marco sev-${sev}`,
        style: `left:${(p.minuto_do_dia / 1440) * 100}%`,
        title: descr, "aria-label": `Ir para o post das ${descr}`,
        onclick: () => destacarPost(p.id),
      }));
    });
  }

  function destacarPost(id) {
    const alvo = document.querySelector(`[data-post="${CSS.escape(id)}"]`);
    if (!alvo) return;
    document.querySelectorAll(".post.destaque").forEach((n) => n.classList.remove("destaque"));
    alvo.classList.add("destaque");
    alvo.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "center" });
    alvo.focus({ preventScroll: true });
  }

  // ---------- Lista de posts ----------
  function renderPosts(dados) {
    const box = $("posts");
    box.replaceChildren();
    $("titulo-posts").textContent = dados.posts.length ? plural(dados.posts.length, "post no dia", "posts no dia") : "Posts do dia";

    if (!dados.posts.length) {
      box.append(el("div", { class: "vazio-posts", text:
        dados.data === dados.hoje
          ? "Nenhum post publicado hoje. A página se atualiza sozinha a cada minuto."
          : "Nenhum post publicado neste dia. Escolha outro dia na faixa dos últimos 30 dias." }));
      return;
    }

    dados.posts.forEach((p) => {
      const sev = p.critica ? p.severidade : 0;
      box.append(el("article", { class: `post sev-${sev}`, "data-post": p.id, tabindex: "-1" },
        el("div", { class: "lado" },
          el("div", { class: "hora", text: p.hora }),
          el("div", { class: "sev", text: p.critica ? `sev. ${p.severidade}` : "ok" })),
        el("div", { class: "corpo" },
          el("div", { class: "cab" },
            el("span", { class: "rotulo", text: p.critica ? "Crítica identificada" : "Sem crítica" }),
            el("span", { text: ROTULO_TIPO[p.tipo] || p.tipo }),
            p.alertado ? el("span", { class: "alertado", text: "Alerta enviado" }) : null,
            el("a", { href: p.permalink, target: "_blank", rel: "noopener", text: "Abrir no Instagram" })),
          p.erro ? el("p", { class: "erro", text: `A análise deste post falhou: ${p.erro}` }) : null,
          p.justificativa ? el("p", { class: "just", text: p.justificativa }) : null,
          p.trecho ? el("p", { class: "trecho", text: p.trecho }) : null,
          (p.alvos.length || p.temas.length || p.confianca != null)
            ? el("p", { class: "miudo", text: [
                p.alvos.length ? `Alvo: ${p.alvos.join(", ")}.` : "",
                p.temas.length ? `Temas: ${p.temas.join(", ")}.` : "",
                p.confianca != null ? `Confiança ${Math.round(p.confianca * 100)}%.` : "",
              ].filter(Boolean).join(" ") })
            : null,
          p.legenda ? el("details", {}, el("summary", { text: "Ver legenda completa" }), el("p", { text: p.legenda })) : null)));
    });
  }

  // ---------- Faixa de 30 dias ----------
  async function renderFaixa() {
    const faixa = $("faixa");
    try {
      const dias = await api(`/api/historico/${encodeURIComponent(estado.username)}?dias=30`);
      faixa.replaceChildren(...dias.map((d) => {
        const classe = d.total === 0 ? "" : `s${d.criticos ? d.severidade_max : 0}`;
        const descr = `${new Date(d.data + "T12:00:00").toLocaleDateString("pt-BR")}: ` +
          (d.total ? `${plural(d.total, "post", "posts")}, ${plural(d.criticos, "crítico", "críticos")}` : "sem posts");
        return el("button", {
          class: [classe, d.data === estado.dia ? "selecionado" : ""].join(" ").trim(),
          role: "listitem", title: descr, "aria-label": descr,
          "aria-current": d.data === estado.dia ? "date" : null,
          onclick: () => irPara(d.data),
        });
      }));
    } catch (e) {
      faixa.replaceChildren(el("p", { class: "erro", text: "Não foi possível carregar o histórico." }));
    }
  }

  // ---------- Fluxo ----------
  async function carregar() {
    if (!estado.username) return;
    atualizarUrl();
    $("proximo").disabled = estado.dia >= hojeLocal();
    try {
      const dados = await api(`/api/status/${encodeURIComponent(estado.username)}?data=${estado.dia}`);
      estado.hoje = dados.hoje;
      renderManchete(dados);
      renderTrilha(dados);
      renderPosts(dados);
      const det = dados.ultima_deteccao ? ` Último post detectado pelo monitor em ${dataHora(dados.ultima_deteccao)}.` : "";
      $("rodape").textContent = `Atualizado às ${new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}.${det}`;
    } catch (e) {
      $("estado").className = "estado";
      $("estado").textContent = "";
      $("frase").textContent = "Não foi possível carregar o status deste dia.";
      $("meta").textContent = `${e.message}. Verifique se o painel está no ar e tente de novo.`;
    }
    renderFaixa();

    clearInterval(timer);
    if (estado.dia === hojeLocal()) timer = setInterval(carregar, REFRESH_MS);
  }

  function irPara(dia) {
    estado.dia = dia > hojeLocal() ? hojeLocal() : dia;
    $("dia").value = estado.dia;
    carregar();
  }

  async function iniciar() {
    const params = new URLSearchParams(location.search);
    $("dia").max = hojeLocal();
    estado.dia = params.get("d") || hojeLocal();
    $("dia").value = estado.dia;

    let perfis = [];
    try { perfis = await api("/api/perfis"); } catch (e) { /* tratado abaixo */ }
    const sel = $("perfil");
    if (!perfis.length) {
      $("frase").textContent = "Nenhum perfil cadastrado ainda.";
      $("meta").replaceChildren("Cadastre um perfil no ", el("a", { href: "/", text: "painel" }), " para ver o status do dia.");
      sel.disabled = true;
      return;
    }
    sel.replaceChildren(...perfis.map((p) =>
      el("option", { value: p.username, text: `@${p.username}${p.ativo ? "" : " (pausado)"}` })));
    const pedido = (params.get("u") || "").toLowerCase();
    estado.username = perfis.some((p) => p.username === pedido) ? pedido : perfis[0].username;
    sel.value = estado.username;

    sel.addEventListener("change", () => { estado.username = sel.value; carregar(); });
    $("dia").addEventListener("change", (e) => e.target.value && irPara(e.target.value));
    $("anterior").addEventListener("click", () => irPara(somaDias(estado.dia, -1)));
    $("proximo").addEventListener("click", () => irPara(somaDias(estado.dia, 1)));
    $("hoje").addEventListener("click", () => irPara(hojeLocal()));
    document.addEventListener("visibilitychange", () => { if (!document.hidden) carregar(); });

    carregar();
  }

  iniciar();
})();
