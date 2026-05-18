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

  // ===== DYNAMIC FAVICON =====
  (function () {
    const faviconUrl =
      "{{ url_for('static', filename='imagens/logos/GPTCODE-LOGO-BARRA.png') }}";
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
