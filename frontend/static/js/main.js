document.addEventListener("DOMContentLoaded", function () {
  // ===== NAVBAR SCROLL HANDLER =====
  const navbar = document.getElementById("navbar");
  const navbarCollapse = document.querySelector(".navbar-collapse");
  const navbarToggler = document.querySelector(".navbar-toggler");

  const setNavbarHeight = () => {
    if (!navbar) return;

    document.documentElement.style.setProperty(
      "--navbar-height",
      `${navbar.offsetHeight}px`
    );
  };

  const getScrollOffset = () => {
    return (navbar ? navbar.offsetHeight : 0) + 16;
  };

  const isHomePage = () => {
    return (
      window.location.pathname === "/" ||
      window.location.pathname.includes("index")
    );
  };

  const updateNavbarState = (currentScroll) => {
    if (!navbar) return;

    const shouldBeScrolled = !isHomePage() || currentScroll >= 50;

    if (navbar.classList.contains("navbar-scrolled") !== shouldBeScrolled) {
      navbar.classList.toggle("navbar-scrolled", shouldBeScrolled);
      setNavbarHeight();
    }
  };

  setNavbarHeight();
  updateNavbarState(window.pageYOffset || document.documentElement.scrollTop);
  window.addEventListener("load", setNavbarHeight);
  window.addEventListener("resize", setNavbarHeight);

  if (navbarCollapse) {
    navbarCollapse.addEventListener("shown.bs.collapse", setNavbarHeight);
    navbarCollapse.addEventListener("hidden.bs.collapse", setNavbarHeight);
  }

  window.addEventListener("scroll", () => {
    const currentScroll =
      window.pageYOffset || document.documentElement.scrollTop;
    updateNavbarState(currentScroll);
  });

  // ===== SMOOTH SCROLLING FOR INTERNAL LINKS =====
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = this.getAttribute("href");
      if (targetId === "#") return;

      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        // Close the mobile menu before scrolling to avoid wrong offsets.
        if (
          navbarCollapse &&
          navbarToggler &&
          navbarCollapse.classList.contains("show")
        ) {
          navbarToggler.click();
        }

        window.scrollTo({
          top: targetElement.offsetTop - getScrollOffset(),
          behavior: "smooth",
        });
      }
    });
  });

  // ===== CLOSE MENU WHEN CLICKING OUTSIDE =====
  document.addEventListener("click", function (e) {
    if (navbarCollapse && navbarCollapse.classList.contains("show")) {
      if (!navbar.contains(e.target)) {
        navbarToggler.click();
      }
    }
  });

  // ===== BOOTSTRAP TOOLTIPS =====
  const tooltipTriggerList = [].slice.call(
    document.querySelectorAll('[data-bs-toggle="tooltip"]')
  );
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  // ===== BACK TO TOP BUTTON =====
  document.querySelectorAll(".back-to-top").forEach((button) => {
    button.addEventListener("click", function (e) {
      e.preventDefault();
      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    });
  });

});

// ===== LEVA ATÉ O PRIMEIRO CAMPO COM ERRO =====
// O formulário de "novo" fica no fim da página, longe do alerta: abre a seção
// recolhida que contém o erro, rola até ele e põe o cursor no campo.
document.addEventListener("DOMContentLoaded", function () {
  const campo = document.querySelector(".is-invalid");
  if (!campo) return;
  let pai = campo.parentElement;
  while (pai) {
    if (pai.tagName === "DETAILS") pai.open = true;
    if (pai.classList && pai.classList.contains("collapse")) pai.classList.add("show");
    pai = pai.parentElement;
  }
  campo.scrollIntoView({ behavior: "smooth", block: "center" });
  campo.focus({ preventScroll: true });
});

// ===== PRÉ-VISUALIZAÇÃO DE IMAGEM (macro campo_imagem em _campos.html) =====
// Mostra a imagem em uso no site e, ao escolher um arquivo, a nova imagem antes de salvar.
// Também avisa na hora quando o arquivo passa do limite (o servidor recusaria o envio).
document.addEventListener("change", function (evento) {
  const entrada = evento.target;
  if (!entrada.matches || !entrada.matches("input[type=file][data-previa]")) return;
  const caixa = entrada.closest(".campo-imagem");
  if (!caixa) return;
  const figura = caixa.querySelector(".campo-imagem-figura");
  const imagem = caixa.querySelector(".campo-imagem-previa");
  const legenda = caixa.querySelector(".campo-imagem-legenda");
  const arquivo = entrada.files && entrada.files[0];

  if (imagem.dataset.urlTemporaria) {
    URL.revokeObjectURL(imagem.dataset.urlTemporaria);
    delete imagem.dataset.urlTemporaria;
  }
  entrada.setCustomValidity("");
  legenda.classList.remove("text-danger");

  if (!arquivo) {
    // seleção cancelada: volta para a imagem em uso (ou esconde, se não havia)
    imagem.src = imagem.dataset.original || "";
    legenda.textContent = imagem.dataset.original ? "Imagem em uso no site" : "";
    figura.classList.toggle("d-none", !imagem.dataset.original);
    return;
  }

  const limiteMb = Number(entrada.dataset.limiteMb || 8);
  if (arquivo.size > limiteMb * 1024 * 1024) {
    entrada.setCustomValidity("Arquivo maior que " + limiteMb + " MB.");
    legenda.textContent = "Este arquivo tem mais de " + limiteMb + " MB e não será aceito. Escolha outro.";
    legenda.classList.add("text-danger");
    figura.classList.remove("d-none");
    imagem.src = imagem.dataset.original || "";
    return;
  }
  if (!arquivo.type.startsWith("image/")) {
    legenda.textContent = "O arquivo escolhido não parece ser uma imagem.";
    legenda.classList.add("text-danger");
    figura.classList.remove("d-none");
    return;
  }

  const url = URL.createObjectURL(arquivo);
  imagem.dataset.urlTemporaria = url;
  imagem.src = url;
  legenda.textContent = "Nova imagem selecionada: " + arquivo.name + " (ainda não salva)";
  figura.classList.remove("d-none");
});

// O formulário público usa novalidate: confere o tamanho da imagem antes de enviar.
document.addEventListener(
  "submit",
  function (evento) {
    const grande = evento.target.querySelector("input[type=file][data-previa]:invalid");
    if (grande) {
      evento.preventDefault();
      evento.stopImmediatePropagation();
      grande.reportValidity();
    }
  },
  true
);

// ===== ENVIO ÚNICO DE FORMULÁRIOS =====
// Duplo clique em "Salvar"/"Enviar" mandava o mesmo POST duas vezes (registro duplicado).
// Depois do primeiro envio, novos envios do mesmo formulário são ignorados e o botão
// fica desabilitado. O listener roda depois do onsubmit="return confirm(...)": se a
// pessoa cancelou a confirmação, nada é travado.
document.addEventListener("submit", function (evento) {
  const formulario = evento.target;
  if (evento.defaultPrevented) return;
  if (formulario.dataset.enviando === "1") {
    evento.preventDefault();
    return;
  }
  formulario.dataset.enviando = "1";
  // desabilita no próximo ciclo: desabilitar já agora tiraria o botão dos dados enviados
  setTimeout(function () {
    formulario.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (botao) {
      botao.disabled = true;
    });
  }, 0);
});

// Ao voltar para a página pelo botão "voltar" do navegador, libera os formulários de novo.
window.addEventListener("pageshow", function () {
  document.querySelectorAll("form[data-enviando]").forEach(function (formulario) {
    delete formulario.dataset.enviando;
    formulario.querySelectorAll('button[type="submit"], input[type="submit"]').forEach(function (botao) {
      botao.disabled = false;
    });
  });
});
