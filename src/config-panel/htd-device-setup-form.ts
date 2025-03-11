import type { PropertyValues, TemplateResult } from 'lit';
import { css, html, LitElement } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';

import { HomeAssistant } from 'custom-card-helpers';
import { HtdDeviceSettings } from './index';


@customElement('htd-device-setup-form')
class HtdDeviceSetupFormElement extends LitElement {

  @property({attribute: false})
  public hass!: HomeAssistant;

  @property({type: Object})
  public config: HtdDeviceSettings;

  private schema = [ // HaFormSchema
    {name: 'host', selector: {text: {}}},
    {name: 'port', selector: {number: {}}},
  ];

  private labelsMap = {
    'host': 'Host',
    'port': 'Port',
  };

  handleValueChange(ev) {
    this.config = {...this.config, ...ev.detail.value};
  }

  onSave() {
    this.dispatchEvent(new CustomEvent('save', {
      detail: {
        config: this.config,
      },
      bubbles: true,
      composed: true,
    }));
  }

  protected render(): TemplateResult {
    return html`
        <ha-card header="Network Settings">
            <div class="card-content">
                <ha-form
                    .hass=${this.hass}
                    .data=${this.config}
                    .schema=${this.schema}
                    .computeLabel=${(schema) => this.labelsMap[schema.name] || schema.name}
                    @value-changed=${this.handleValueChange}
                ></ha-form>
            </div>
            <div class="card-actions">
                <ha-progress-button @click=${this.onSave}>
                    Save
                </ha-progress-button>
            </div>
        </ha-card>
    `;
  }

  static styles = [
    css`
        .card-actions {
            display: flex;
            justify-content: flex-end;
        }
    `,
  ];
}

declare global {
  interface HTMLElementTagNameMap {
    'htd-device-setup-form': HtdDeviceSetupFormElement;
  }
}
