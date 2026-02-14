import type { CSSResultGroup, TemplateResult } from 'lit';
import { css, html, LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';

import { HomeAssistant } from 'custom-card-helpers';


@customElement('htd-layout')
class HtdLayoutElement extends LitElement {

  @property({attribute: false})
  public hass!: HomeAssistant;

  @property()
  public header?: string;

  @property({type: String, attribute: 'back-url'})
  public backUrl?: string;

  @property({type: Boolean, reflect: true})
  public narrow = false;

  protected render(): TemplateResult {
    return html`
        <div class="toolbar">
            <ha-icon-button-arrow-prev
                .hass=${this.hass}
                @click=${this._backTapped}
            ></ha-icon-button-arrow-prev>

            <div class="main-title">
                <slot name="header">${this.header}</slot>
            </div>

            <slot name="toolbar-icon"></slot>
        </div>

        <div class="content ha-scrollbar">
            <!--<slot name="left"></slot>-->
            <slot></slot>
        </div>
    `;
  }

  private _backTapped(): void {
    history.back();
  }

  static get styles(): CSSResultGroup {
    return [
      css`
          :host {
              display: block;
              height: 100%;
              background-color: var(--primary-background-color);
              overflow: hidden;
              position: relative;
          }

          :host([narrow]) {
              width: 100%;
              position: fixed;
          }

          .toolbar {
              display: flex;
              align-items: center;
              font-size: 20px;
              height: var(--header-height);
              padding: 8px 12px;
              background-color: var(--app-header-background-color);
              font-weight: 400;
              color: var(--app-header-text-color, white);
              border-bottom: var(--app-header-border-bottom, none);
              box-sizing: border-box;
          }

          @media (max-width: 599px) {
              .toolbar {
                  padding: 4px;
              }
          }

          .toolbar a {
              color: var(--sidebar-text-color);
              text-decoration: none;
          }

          ha-menu-button,
          ha-icon-button-arrow-prev,
          ::slotted([slot="toolbar-icon"]) {
              pointer-events: auto;
              color: var(--sidebar-icon-color);
          }

          .main-title {
              margin: var(--margin-title);
              line-height: 20px;
              min-width: 0;
              flex-grow: 1;
              overflow-wrap: break-word;
              display: -webkit-box;
              -webkit-line-clamp: 2;
              -webkit-box-orient: vertical;
              overflow: hidden;
              text-overflow: ellipsis;
              padding-bottom: 1px;
          }

          .content {
              box-sizing: border-box;
              padding: 30px;
              position: relative;
              width: 100%;
              height: calc(100% - 1px - var(--header-height));
              overflow-y: auto;
              overflow: auto;
              -webkit-overflow-scrolling: touch;
              display: flex;
              justify-content: center;
              gap: 1rem;
          }
          
          .content ::slotted(*) {
              flex: 1;
              max-width: 700px;
          }

          /*
          .content ::slotted([slot="left"]) {
              max-width: 400px;
              flex: 1;
          }
          */
          
          :host([narrow]) #fab.tabs {
              bottom: calc(84px + env(safe-area-inset-bottom));
          }
      `,
    ];
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'htd-layout': HtdLayoutElement;
  }
}
