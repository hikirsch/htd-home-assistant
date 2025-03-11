import type { HomeAssistant } from 'home-assistant-frontend/src/types';
import { html, LitElement, PropertyValues } from 'lit';
import { customElement, property, state } from 'lit/decorators.js';
import './htd-layout';
import './htd-device-setup-form';
import './htd-sources-editor';
import { preloadConfigDashboard } from '../helpers';
import { HtdSourceConfig } from '../models';

/**
 * A hack recommended by thomasloven
 * - https://github.com/thomasloven/hass-config/wiki/PreLoading-Lovelace-Elements
 * - https://github.com/thomasloven/hass-custom_icons/blob/main/js/helpers.ts#L24
 * - https://github.com/thomasloven/hass-custom_icons/blob/main/js/panel/main.ts#L8
 */
preloadConfigDashboard();

export interface HtdDeviceSettings {
  host: string;
  port: number;
}

@customElement('htd-config-panel')
class HtdConfigPanel extends LitElement {
  private integrationHome = '/config/integrations/integration/htd';

  @property({attribute: false})
  hass!: HomeAssistant;

  @property({type: Boolean, reflect: true})
  narrow = false;

  @state()
  private entryId: string;

  @property({type: Array, attribute: false})
  sources: HtdSourceConfig[];

  @property({type: Array, attribute: false})
  enabledSources: HtdSourceConfig[];

  @property({type: Array, attribute: false})
  disabledSources: HtdSourceConfig[];

  @property({attribute: false})
  config: HtdDeviceSettings[];

  async firstUpdated(_changedProperties: PropertyValues) {
    super.firstUpdated(_changedProperties);

    const urlParams = new URLSearchParams(window.location.search);
    this.entryId = urlParams.get('config_entry');

    if (!this.entryId) {
      location.replace(this.integrationHome);
    }

    this.style.setProperty('--app-header-background-color', 'var(--sidebar-background-color)');
    this.style.setProperty('--app-header-text-color', 'var(--sidebar-text-color)');
    this.style.setProperty('--app-header-border-bottom', '1px solid var(--divider-color)');

    this.refresh();
  }

  private async refreshConfig() {
    this.config = await this.hass.callWS<HtdDeviceSettings[]>({
      type: 'htd/config/get',
      entry_id: this.entryId,
    });

    this.requestUpdate();
  }

  private async refreshSources() {
    this.sources = await this.hass.callWS<HtdSourceConfig[]>({
      type: 'htd/sources/get',
      entry_id: this.entryId,
    });

    this.enabledSources = this.sources.filter(source => source.enabled);
    this.disabledSources = this.sources.filter(source => !source.enabled);
    this.requestUpdate();
  }

  private async refresh() {
    this.refreshSources();
    // this.refreshConfig();
  }

  // async onSaveConfig(event: CustomEvent<{ config: HtdDeviceSettings }>) {
  //   const {config} = event.detail;
  //   console.log('save:', config);
  //
  //   const response = await this.hass.callWS({
  //     type: 'htd/config/set',
  //     entry_id: this.entryId,
  //     host: config.host,
  //     port: config.port,
  //   });
  //
  //   console.log('set sources response:', response);
  // }

  async onSaveSources(event: CustomEvent<{ sources: HtdSourceConfig[] }>) {
    const {sources} = event.detail;
    console.log('save:', sources);

    const response = await this.hass.callWS({
      type: 'htd/sources/set',
      entry_id: this.entryId,
      sources,
    });

    console.log('set sources response:', response);
  }

  render() {
    return html`
        <htd-layout
            .hass=${this.hass}
            .header= ${'Home Theater Direct Configuration'}
        >
            ${
                !this.sources
                ? html`Loading...`
                : html`
                    <htd-sources-editor
                        .enabledSources=${this.enabledSources}
                        .disabledSources=${this.disabledSources}
                        @save=${this.onSaveSources}
                    ></htd-sources-editor>
                `
            }
        </htd-layout>
    `;
  }
}

declare global {
  interface HTMLElementTagNameMap {
    'htd-config-panel': HtdConfigPanel;
  }
}
