document.addEventListener("DOMContentLoaded", function () {
  // ===== NAVBAR SCROLL HANDLER =====
  const navbar = document.getElementById("navbar");
  const navbarCollapse = document.querySelector(".navbar-collapse");
  const navbarToggler = document.querySelector(".navbar-toggler");
  let lastScrollTop = 0;

  const isHomePage = () => {
    return window.location.pathname === "/" || window.location.pathname.includes("index");
  };

  // Aplicar classe inicial baseada na página
  if (!isHomePage()) {
    navbar.classList.add("navbar-scrolled");
  }

  window.addEventListener("scroll", () => {
    const currentScroll = window.pageYOffset || document.documentElement.scrollTop;

    if (isHomePage()) {
      if (currentScroll >= 50) {
        navbar.classList.add("navbar-scrolled");
      } else {
        navbar.classList.remove("navbar-scrolled");
      }
    } else {
      navbar.classList.add("navbar-scrolled");
    }

    lastScrollTop = currentScroll <= 0 ? 0 : currentScroll;
  });

  // ===== SMOOTH SCROLLING PARA LINKS INTERNOS =====
  document.querySelectorAll('a[href^="#"]').forEach((anchor) => {
    anchor.addEventListener("click", function (e) {
      e.preventDefault();
      const targetId = this.getAttribute("href");
      if (targetId === "#") return;

      const targetElement = document.querySelector(targetId);
      if (targetElement) {
        // Fechar menu mobile antes de fazer scroll
        if (navbarCollapse.classList.contains("show")) {
          navbarToggler.click();
        }
        
        window.scrollTo({
          top: targetElement.offsetTop - 80,
          behavior: "smooth",
        });
      }
    });
  });

  // ===== FECHAR MENU AO CLICAR FORA =====
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

  // ===== FAVICON DINÂMICO =====
  (function () {
    const faviconUrl = "{{ url_for('static', filename='imagens/logos/GPTCODE-LOGO-BARRA.png') }}";
    let link = document.querySelector("link[rel~='icon']");
    if (!link) {
      link = document.createElement("link");
      link.rel = "icon";
      document.head.appendChild(link);
    }
    link.type = "image/png";
    link.href = faviconUrl;
  })();
});

