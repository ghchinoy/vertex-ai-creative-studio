import { LitElement, css, html } from "https://cdn.jsdelivr.net/npm/lit/+esm";
import { initializeApp, getApps, getApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, onIdTokenChanged, signOut } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-auth.js";

class AuthHandler extends LitElement {
  static styles = css`
    :host {
      display: block;
      width: 100%;
    }
    .auth-container {
      display: flex;
      justify-content: flex-end;
      padding: 10px;
    }
    .login-btn, .logout-btn {
      background-color: #4285F4;
      color: white;
      border: none;
      padding: 10px 20px;
      border-radius: 4px;
      cursor: pointer;
      font-size: 14px;
      font-weight: 500;
    }
    .login-btn:hover, .logout-btn:hover {
      background-color: #357ae8;
    }
    .user-info {
        display: flex;
        align-items: center;
        gap: 10px;
        color: var(--mesop-on-surface-color, #000);
    }
    .user-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
    }
    .error-msg {
        background-color: #fce8e6;
        color: #d93025;
        padding: 10px 15px;
        border-radius: 4px;
        font-size: 13px;
        margin-right: 10px;
        border: 1px solid #f8d7da;
    }
  `;

  static get properties() {
    return {
      firebaseConfig: { type: Object },
      authStateChange: { type: String },
      autoLogin: { type: Boolean },
      errorMessage: { type: String },
      cachedPhotoUrl: { type: String },
      user: { state: true },
    };
  }

  constructor() {
    super();
    this.firebaseConfig = {};
    this.authStateChange = "";
    this.autoLogin = false;
    this.errorMessage = "";
    this.cachedPhotoUrl = "";
    this.user = null;
    this._app = null;
    this._boundHandleExternalLogin = this._handleExternalLogin.bind(this);
    this._boundHandleExternalLogout = this._handleExternalLogout.bind(this);
  }

  connectedCallback() {
    super.connectedCallback();
    window.addEventListener('genmedia-login', this._boundHandleExternalLogin);
    window.addEventListener('genmedia-logout', this._boundHandleExternalLogout);
    if (this.firebaseConfig && Object.keys(this.firebaseConfig).length > 0) {
      this._initFirebase();
    }
  }

  updated(changedProperties) {
    if (changedProperties.has('firebaseConfig') && this.firebaseConfig && Object.keys(this.firebaseConfig).length > 0) {
      this._initFirebase();
    }
    if (changedProperties.has('autoLogin') && this.autoLogin && !this.user) {
        this._handleLogin();
    }
  }

  disconnectedCallback() {
    super.disconnectedCallback();
    window.removeEventListener('genmedia-login', this._boundHandleExternalLogin);
    window.removeEventListener('genmedia-logout', this._boundHandleExternalLogout);
  }

  _handleExternalLogin() {
    this._handleLogin();
  }

  _handleExternalLogout() {
    this._handleLogout();
  }

  _initFirebase() {
    if (this._app) return;

    try {
        if (getApps().length === 0) {
            this._app = initializeApp(this.firebaseConfig);
        } else {
            this._app = getApp();
        }

        // Expose app globally for other components (like media-tile)
        window.genMediaFirebaseApp = this._app;

        const auth = getAuth(this._app);

        // Listen for ID token changes (handles refresh, sign-in, sign-out)
        onIdTokenChanged(auth, async (user) => {
            this.user = user;
            if (user) {
                const token = await user.getIdToken();
                await this._syncSession(token);
                this._dispatchAuthEvent(token);
            } else {
                await this._syncSession(null);
                this._dispatchAuthEvent(null);
                if (this.autoLogin) {
                    this._handleLogin();
                }
            }
        });

    } catch (e) {
        console.error("Firebase init error:", e);
    }
  }

  async _syncSession(token) {
      try {
          const body = { token: token };
          if (this.user && this.user.photoURL) {
              body.photo_url = this.user.photoURL;
          }
          const response = await fetch('/api/auth/login', {
              method: 'POST',
              headers: {
                  'Content-Type': 'application/json',
              },
              body: JSON.stringify(body),
          });
          if (response.ok) {
              const data = await response.json();
              this._dispatchAuthEvent(token, data.role, data.email);
          } else {
              console.error("Failed to sync session");
          }
      } catch (e) {
          console.error("Error syncing session:", e);
      }
  }

  _dispatchAuthEvent(token, role, email) {
      if (this.authStateChange) {
          const eventData = { token: token };
          if (role) {
              eventData.role = role;
          }
          if (email) {
              eventData.email = email;
          }
          this.dispatchEvent(new MesopEvent(this.authStateChange, eventData));
      }
      // Reset autoLogin to prevent loops
      this.autoLogin = false;
  }

  async _handleLogin() {
      const auth = getAuth(this._app);
      const provider = new GoogleAuthProvider();
      try {
          await signInWithPopup(auth, provider);
      } catch (error) {
          console.error("Login failed", error);
      }
  }

  async _handleLogout() {
      const auth = getAuth(this._app);
      try {
          await signOut(auth);
      } catch (error) {
          console.error("Logout failed", error);
      }
  }

  _handleImageError(e) {
      if (e.target.dataset.errorHandled) return;
      // Fallback to a generic user icon if the Google avatar fails (e.g. 429)
      e.target.dataset.errorHandled = "true";
      e.target.src = "https://www.gstatic.com/images/branding/product/2x/avatar_anonymous_48dp.png";
  }

  render() {
    if (!this.user) {
        return html`
            <div class="auth-container">
                ${this.errorMessage ? html`<div class="error-msg">${this.errorMessage}</div>` : ""}
                <button class="login-btn" @click="${this._handleLogin}">Sign in with Google</button>
            </div>
        `;
    }

    return html`
        <div class="auth-container">
            ${this.errorMessage ? html`<div class="error-msg">${this.errorMessage}</div>` : ""}
            <div class="user-info">
                <img class="user-avatar" 
                     src="${this.cachedPhotoUrl || this.user.photoURL}" 
                     alt="${this.user.displayName}" 
                     title="${this.user.email}"
                     @error="${this._handleImageError}">
                <button class="logout-btn" @click="${this._handleLogout}">Sign Out</button>
            </div>
        </div>
    `;
  }
}

customElements.define("auth-handler", AuthHandler);
