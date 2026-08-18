import { LitElement, html, css } from 'lit';
import { customElement } from 'lit/decorators.js';

@customElement('github-badge')
export class GitHubBadge extends LitElement {

  static styles = css`
    .how-its-built-text {
        font-family: 'Brush Script MT', cursive;
        font-size: 1.4rem;
        color: var(--md-sys-color-on-background, #333);
        pointer-events: none;
        display: flex;
        align-items: center;
        opacity: 0.9;
        transform: rotate(-2deg);
        margin-top: 8px;
        margin-bottom: 8px;
    }
  `;

  render() {
    return html`
      <div class="how-its-built-text">
          <span>how it's built →</span>
      </div>
    `;
  }
}
