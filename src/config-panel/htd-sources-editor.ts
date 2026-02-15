import { css, html, LitElement } from 'lit';
import { customElement, property } from 'lit/decorators.js';
import { repeat } from 'lit/directives/repeat.js';
import Sortable, { SortableEvent } from 'sortablejs';
import { mdiDrag } from '@mdi/js';
import { HtdSourceConfig } from '../models';
import { HomeAssistant } from 'custom-card-helpers';

@customElement('htd-sources-editor')
class HtdSourcesEditor extends LitElement {
  private defaultSortableOptions: Sortable.Options = {
    animation: 150,
    handle: '.handle',
  };

  @property({ attribute: false })
  hass: HomeAssistant;

  @property({ type: Array })
  enabledSources: HtdSourceConfig[] = [];

  @property({ type: Array })
  disabledSources: HtdSourceConfig[] = [];

  @property({ type: String })
  sourceType: string;

  @property({ attribute: false })
  hasChanges: boolean = false;

  handleCancel() {

  }

  handleReset() {

  }

  handleSubmit() {
    if (!this.hasChanges) {
      console.log('No changes to save');
      return;
    }
    this.onSave();
    this.hasChanges = false;
  }

  onSave() {
    this.dispatchEvent(new CustomEvent('save', {
      detail: {
        sources: [
          ...this.enabledSources,
          ...this.disabledSources,
        ],
      },
      bubbles: true,
      composed: true,
    }));
  }

  onDragEnd = (enabled: boolean) => async (event: SortableEvent) => {
    if (event.oldIndex === event.newIndex) {
      return;
    }

    const sources = enabled ? this.enabledSources : this.disabledSources;
    const movedItem = sources.splice(event.oldIndex, 1)[0];
    sources.splice(event.newIndex, 0, movedItem);
    this.hasChanges = true;
    this.requestUpdate();
  };

  firstUpdated() {
    Sortable.create(
      this.shadowRoot?.querySelector('#enabled-sortable-list'),
      {
        ...this.defaultSortableOptions,
        onEnd: this.onDragEnd(true),
      },
    );

    Sortable.create(
      this.shadowRoot?.querySelector('#disabled-sortable-list'),
      {
        ...this.defaultSortableOptions,
        onEnd: this.onDragEnd(false),
      },
    );
  }

  toggleEnabled = (changed: HtdSourceConfig) => async () => {
    const sources = changed.enabled ? this.enabledSources : this.disabledSources;
    const index = sources.indexOf(changed);
    const otherSources = !changed.enabled ? this.enabledSources : this.disabledSources;
    const source = sources.find(s => s.zone === changed.zone);
    source.enabled = !source.enabled;
    sources.splice(index, 1);
    otherSources.push(source);
    this.hasChanges = true;
    this.requestUpdate();
  };

  updateAlias = (changed: HtdSourceConfig) => async (event: Event) => {
    const input = event.target as HTMLInputElement;
    const sources = changed.enabled ? this.enabledSources : this.disabledSources;
    const source = sources.find(s => s.zone === changed.zone);
    source.alias = input.value;
    this.hasChanges = true;
  };

  renderRow(source: HtdSourceConfig) {
    let label = source.intercom ? 'Intercom' : `Source ${source.zone}`;
    return html`
        <tr>
            <td class="center">
                <ha-svg-icon
                    class="handle"
                    .path=${mdiDrag}
                ></ha-svg-icon>
            </td>
            <td class="center">
                <ha-checkbox
                    .checked=${source.enabled}
                    @change=${this.toggleEnabled(source)}
                ></ha-checkbox>
            </td>
            <td>${label}</td>
            <td>
                <ha-textfield
                    id="source-${source.zone}"
                    .value=${source.alias}
                    .disabled=${!source.enabled}
                    @change=${this.updateAlias(source)}
                ></ha-textfield>
            </td>
        </tr>
    `;
  }

  render() {
    return html`
        <ha-card header="Source Configuration">
            <table>
                <thead>
                <tr>
                    <th>&nbsp;</th>
                    <th class="center">Enabled</th>
                    <th>Source Number</th>
                    <th>Alias</th>
                </tr>
                </thead>
                <tbody id="enabled-sortable-list">
                ${repeat(this.enabledSources, i => i.zone, source => this.renderRow(source))}
                </tbody>
                <tbody id="disabled-sortable-list">
                ${repeat(this.disabledSources, i => i.zone, source => this.renderRow(source))}
                </tbody>
            </table>
            <div class="card-actions">
                <ha-progress-button @click=${this.handleSubmit}>
                    Save
                </ha-progress-button>

                <ha-progress-button @click=${this.handleCancel}>
                    Cancel
                </ha-progress-button>

                <ha-progress-button @click=${this.handleReset}>
                    Reset
                </ha-progress-button>
            </div>
        </ha-card>
    `;
  }

  static styles = css`
      table {
          width: 100%;
          border-collapse: collapse;
      }

      th, td {
          padding: 8px;
          border-bottom: 1px solid var(--divider-color);
          text-align: left
      }

      td.center, th.center {
          text-align: center;
      }

      tr:last-child td {
          border-bottom: 0;
      }

      .handle {
          cursor: grab;
      }

      .sortable-ghost {
          background: rgba(var(--rgb-primary-color), 0.25);
          box-shadow: 0 0 0 2px var(--primary-color);
          border-radius: 4px;
          opacity: 0.4;
      }

      .sortable-chosen {
      }
  `;
}


declare global {
  interface HTMLElementTagNameMap {
    'htd-sources-editor': HtdSourcesEditor;
  }
}
