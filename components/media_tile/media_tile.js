import { LitElement, css, html } from "https://cdn.jsdelivr.net/npm/lit/+esm";
import { SvgIcon } from "../svg_icon/svg_icon.js";
import { getStorage, ref, getDownloadURL } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-storage.js";
import { getApp } from "https://www.gstatic.com/firebasejs/10.7.1/firebase-app.js";

class MediaTile extends LitElement {
  static styles = css`
    :host {
      display: block;
      position: relative;
      border-radius: 8px;
      overflow: hidden;
      cursor: pointer;
      width: 100%;
      height: 100%;
      box-sizing: border-box;
      background-color: rgba(255, 255, 255, 0.05);
    }

    :host([has-pills]) {
      border: 1px solid var(--mesop-outline-variant-color);
    }

    .preview {
      width: 100%;
      height: 100%;
      display: flex;
      align-items: center;
      justify-content: center;
    }

    .preview img,
    .preview video {
      width: 100%;
      height: 100%;
      object-fit: cover;
    }

    .preview .icon {
      width: 64px;
      height: 64px;
      color: var(--mesop-on-surface-variant-color);
    }

    .overlay {
      position: absolute;
      top: 0;
      left: 0;
      right: 0;
      bottom: 0;
      background: linear-gradient(
        to top,
        rgba(0, 0, 0, 0.7) 0%,
        rgba(0, 0, 0, 0.3) 50%,
        transparent 100%
      );
      display: flex;
      flex-direction: column;
      justify-content: flex-end;
      padding: 12px;
      pointer-events: none;
      opacity: 0;
      transition: opacity 0.2s ease-in-out;
    }

    .overlay > * {
      pointer-events: auto;
    }

    :host(:hover) .overlay {
      opacity: 1;
    }

    .pills-container {
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
    }

    .pill {
      background-color: rgba(255, 255, 255, 0.8);
      color: #202124;
      padding: 4px 8px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 500;
    }

    audio {
      width: 100%;
      margin-bottom: 8px;
      filter: invert(1) grayscale(1) contrast(1.5);
    }
  `;

  static get properties() {
    return {
      mediaType: { type: String },
      thumbnailSrc: { type: String },
      audioSrc: { type: String },
      pillsJson: { type: String },
      clickEvent: { type: String }, // Added to receive the event handler ID
      _resolvedThumbnailSrc: { state: true },
      _resolvedAudioSrc: { state: true },
    };
  }

  constructor() {
    super();
    this.mediaType = "";
    this.thumbnailSrc = "";
    this.audioSrc = "";
    this.pillsJson = "[]";
    this.clickEvent = ""; // Initialize
    this._resolvedThumbnailSrc = "";
    this._resolvedAudioSrc = "";
    this.addEventListener("click", this.handleClick);
  }

  updated(changedProperties) {
    if (changedProperties.has('pillsJson')) {
        const hasPills = this.pillsJson && this.pillsJson !== "[]";
        if (hasPills) {
            this.setAttribute('has-pills', '');
        } else {
            this.removeAttribute('has-pills');
        }
    }
    if (changedProperties.has('thumbnailSrc')) {
        this._resolveUrl(this.thumbnailSrc).then(url => {
            this._resolvedThumbnailSrc = url;
        });
    }
    if (changedProperties.has('audioSrc')) {
        this._resolveUrl(this.audioSrc).then(url => {
            this._resolvedAudioSrc = url;
        });
    }
  }

  async _resolveUrl(url) {
        if (!url) return "";
        if (url.startsWith("gs://")) {
            try {
                let app;
                try {
                    app = getApp();
                } catch(e) {
                    // App not initialized yet.
                    app = window.genMediaFirebaseApp;
                }

                if (!app) {
                     // Retry once after 500ms
                     await new Promise(r => setTimeout(r, 500));
                     try { app = getApp(); } catch(e) { app = window.genMediaFirebaseApp; }
                }

                if (!app) {
                    console.error("Firebase app not found");
                    return "";
                }

                const storage = getStorage(app);
                const storageRef = ref(storage, url);
                return await getDownloadURL(storageRef);
            } catch (e) {
                console.error("Error resolving GCS URL:", url, e);
                return "";
            }
        }
        return url;
    }

  disconnectedCallback() {
    super.disconnectedCallback();
    this.removeEventListener("click", this.handleClick);
  }

  handleClick(e) {
    console.log("media-tile clicked, dispatching MesopEvent");
    if (!this.clickEvent) {
      console.error("Mesop event handler ID for clickEvent is not set.");
      return;
    }
    // Use the correct MesopEvent to communicate back to the server
    this.dispatchEvent(new MesopEvent(this.clickEvent, {}));
  }

  renderPreview() {
    const src = this._resolvedThumbnailSrc || this.thumbnailSrc;
    if (!src && this.mediaType !== 'audio' && this.thumbnailSrc) {
        // Still resolving or failed
        return html`<div>Loading...</div>`;
    }

    switch (this.mediaType) {
      case "image":
        return html`<img .src=${src} />`;
      case "video":
        return html`<video
          .src=${src}
          muted
          autoplay
          loop
          playsinline
        ></video>`;
      case "audio":
        return html`<div class="icon"><svg-icon .iconName=${'music_note'}></svg-icon></div>`;
      default:
        return html`<div class="icon"><svg-icon .iconName=${'help'}></svg-icon></div>`;
    }
  }

  renderPills() {
    try {
      const pills = JSON.parse(this.pillsJson);
      return pills.map((pill) => html`<div class="pill">${pill.label}</div>`);
    } catch (e) {
      console.error("Error parsing pillsJson:", e);
      return html``;
    }
  }

  render() {
    const hasPills = this.pillsJson && this.pillsJson !== "[]";
    return html`
      <div class="preview">${this.renderPreview()}</div>
      ${hasPills || this.mediaType === "audio" ? html`
      <div class="overlay">
        ${this.mediaType === "audio"
          ? html`<audio controls .src=${this._resolvedAudioSrc || this.audioSrc}></audio>`
          : ""}
        <div class="pills-container">${this.renderPills()}</div>
      </div>` : ""}
    `;
  }
}

customElements.define("media-tile", MediaTile);