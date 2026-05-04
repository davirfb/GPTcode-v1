import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.2/firebase-app.js";
import {
  getAuth,
  onIdTokenChanged,
  signInWithEmailAndPassword,
  signOut,
} from "https://www.gstatic.com/firebasejs/10.12.2/firebase-auth.js";

const firebaseConfig = window.adminFirebaseConfig || {};
const firebaseState = window.adminFirebaseState || {};
const loginForm = document.getElementById("firebase-login-form");
const loginButton = document.getElementById("firebase-login-button");
const feedbackElement = document.getElementById("firebase-login-feedback");
const logoutForm = document.querySelector("[data-admin-logout-form]");
const buttonLabel = loginButton?.querySelector("[data-login-label]");
const defaultLabel = "Entrar";
let logoutCommitted = false;

function showFeedback(message) {
  if (!feedbackElement) return;
  feedbackElement.textContent = message;
  feedbackElement.classList.remove("d-none");
}

function hideFeedback() {
  if (!feedbackElement) return;
  feedbackElement.textContent = "";
  feedbackElement.classList.add("d-none");
}

function setLoadingState(isLoading) {
  if (!loginButton || !buttonLabel) return;
  loginButton.disabled = isLoading;
  buttonLabel.textContent = isLoading ? "Entrando..." : defaultLabel;
}

function getCookieFlags() {
  return window.location.protocol === "https:"
    ? "; Path=/; SameSite=Lax; Secure"
    : "; Path=/; SameSite=Lax";
}

function writeAuthCookie(idToken) {
  if (!idToken) return;
  document.cookie = `firebase_id_token=${idToken}${getCookieFlags()}`;
}

function clearAuthCookie() {
  document.cookie = `firebase_id_token=; Max-Age=0${getCookieFlags()}`;
}

async function syncAuthCookie(user, forceRefresh = false) {
  if (!user) {
    clearAuthCookie();
    return;
  }
  const idToken = await user.getIdToken(forceRefresh);
  writeAuthCookie(idToken);
}

function mapFirebaseError(error) {
  const code = error?.code || "";

  if (code === "auth/invalid-credential" || code === "auth/wrong-password" || code === "auth/user-not-found") {
    return "Email ou senha incorretos.";
  }
  if (code === "auth/invalid-email") {
    return "Endereco de email invalido.";
  }
  if (code === "auth/too-many-requests") {
    return "Muitas tentativas. Aguarde alguns minutos e tente novamente.";
  }
  if (code === "auth/user-disabled") {
    return "Esta conta foi desativada.";
  }
  if (code === "auth/network-request-failed") {
    return "Erro de conexao. Verifique sua internet e tente novamente.";
  }

  return error?.message || "Nao foi possivel concluir o login.";
}

async function bootstrapAdminFirebase() {
  if (!firebaseConfig.apiKey || !firebaseState.loginUrl) return;

  const app = initializeApp(firebaseConfig);
  const auth = getAuth(app);

  onIdTokenChanged(auth, async (user) => {
    if (user) {
      try {
        await syncAuthCookie(user);
      } catch (_) {
        clearAuthCookie();
      }
      return;
    }

    clearAuthCookie();

    if (firebaseState.protectedPage) {
      window.location.assign(firebaseState.loginUrl);
    }
  });

  if (logoutForm) {
    logoutForm.addEventListener("submit", async (event) => {
      if (logoutCommitted) return;
      event.preventDefault();
      logoutCommitted = true;

      try {
        await signOut(auth);
      } catch (_) {
        // Limpa cookie mesmo se o Firebase ja estiver sem sessao
      }

      clearAuthCookie();
      HTMLFormElement.prototype.submit.call(logoutForm);
    });
  }

  if (!loginForm) return;

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    hideFeedback();

    const email = document.getElementById("login-email")?.value.trim() || "";
    const password = document.getElementById("login-password")?.value || "";

    if (!email || !password) {
      showFeedback("Preencha o email e a senha.");
      return;
    }

    setLoadingState(true);

    try {
      const result = await signInWithEmailAndPassword(auth, email, password);
      await syncAuthCookie(result.user, true);
      window.location.assign(firebaseState.dashboardUrl || "/admin");
    } catch (error) {
      showFeedback(mapFirebaseError(error));
    } finally {
      setLoadingState(false);
    }
  });
}

bootstrapAdminFirebase();
