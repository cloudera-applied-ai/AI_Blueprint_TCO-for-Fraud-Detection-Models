import { useEffect, useState } from 'react';
import { Coins, ChevronDown, RefreshCw, Loader2, Server } from 'lucide-react';
import type { CostEstimate, ProviderCostEstimate, ProviderModelCost } from '../types';

interface Props {
  usage: CostEstimate | null;
  onRefreshPricing?: () => Promise<void>;
}

const STORAGE_KEY_ANTHROPIC = 'fraud-cost-counter-anthropic-model';
const STORAGE_KEY_OPENAI = 'fraud-cost-counter-openai-model';

function formatCost(value: number): string {
  if (value === 0) return '$0.00';
  if (value < 0.01) return `$${value.toFixed(4)}`;
  if (value < 1) return `$${value.toFixed(3)}`;
  return `$${value.toFixed(2)}`;
}

function formatTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return `${(n / 1000).toFixed(1)}K`;
  return `${(n / 1_000_000).toFixed(2)}M`;
}

function formatRelativeTime(unixSeconds: number): string {
  if (!unixSeconds) return 'never';
  const ageSec = Date.now() / 1000 - unixSeconds;
  if (ageSec < 60) return 'just now';
  if (ageSec < 3600) return `${Math.floor(ageSec / 60)}m ago`;
  if (ageSec < 86400) return `${Math.floor(ageSec / 3600)}h ago`;
  return `${Math.floor(ageSec / 86400)}d ago`;
}

function readStoredModel(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function writeStoredModel(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

function resolveModel(
  provider: ProviderCostEstimate | undefined,
  storedId: string | null,
): { id: string; model: ProviderModelCost } | null {
  if (!provider) return null;
  const ids = Object.keys(provider.models);
  if (!ids.length) return null;
  const chosenId = storedId && provider.models[storedId] ? storedId : provider.default_model;
  return { id: chosenId, model: provider.models[chosenId] };
}

export function CostCounter({ usage, onRefreshPricing }: Props) {
  const [open, setOpen] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [anthropicModelId, setAnthropicModelId] = useState<string | null>(() =>
    readStoredModel(STORAGE_KEY_ANTHROPIC),
  );
  const [openaiModelId, setOpenaiModelId] = useState<string | null>(() =>
    readStoredModel(STORAGE_KEY_OPENAI),
  );

  const handleRefresh = async () => {
    if (!onRefreshPricing || refreshing) return;
    setRefreshing(true);
    try {
      await onRefreshPricing();
    } finally {
      setRefreshing(false);
    }
  };

  // Once we receive usage, if our stored selection is invalid (unknown model id),
  // fall back to the backend's default so the UI stays in sync.
  useEffect(() => {
    if (!usage) return;
    if (anthropicModelId && !usage.providers.anthropic.models[anthropicModelId]) {
      setAnthropicModelId(usage.providers.anthropic.default_model);
    }
    if (openaiModelId && !usage.providers.openai.models[openaiModelId]) {
      setOpenaiModelId(usage.providers.openai.default_model);
    }
  }, [usage, anthropicModelId, openaiModelId]);

  const anthropic = resolveModel(usage?.providers.anthropic, anthropicModelId);
  const openai = resolveModel(usage?.providers.openai, openaiModelId);

  const tokens = usage?.tokens.total ?? 0;
  const onPrem = usage?.on_prem;
  const onPremCost = (onPrem?.enabled && onPrem?.cost_usd) ? onPrem.cost_usd : 0;
  const anthropicCost = anthropic?.model.cost_usd ?? 0;
  const openaiCost = openai?.model.cost_usd ?? 0;
  const cloudMax = Math.max(anthropicCost, openaiCost);

  const handleAnthropicChange = (id: string) => {
    setAnthropicModelId(id);
    writeStoredModel(STORAGE_KEY_ANTHROPIC, id);
  };
  const handleOpenaiChange = (id: string) => {
    setOpenaiModelId(id);
    writeStoredModel(STORAGE_KEY_OPENAI, id);
  };

  return (
    <div className="relative">
      <button
        onClick={() => setOpen(v => !v)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg
                   bg-surface-2 border border-surface-4 hover:border-accent/40
                   text-xs transition-colors"
        title="Click for cost breakdown and model selection"
      >
        <Coins className="w-3.5 h-3.5 text-fraud-amber" />
        <div className="flex items-center gap-1.5">
          <span className="text-gray-500">Tokens</span>
          <span className="font-mono text-gray-200">{formatTokens(tokens)}</span>
        </div>
        {onPrem?.enabled && (
          <>
            <span className="h-3 w-px bg-surface-4" />
            <div
              className="flex items-center gap-1.5"
              title={`On-prem TCO (${onPrem.config_summary?.gpu_label ?? 'GPU'})`}
            >
              <span className="text-gray-500">On-Prem</span>
              <span className="font-mono text-blue-400">{formatCost(onPremCost)}</span>
            </div>
          </>
        )}
        <span className="h-3 w-px bg-surface-4" />
        <div
          className="flex items-center gap-1.5"
          title={anthropic ? `${anthropic.model.label} equivalent` : 'Anthropic equivalent'}
        >
          <span className="text-gray-500">Claude</span>
          <span className="font-mono text-fraud-amber">{formatCost(anthropicCost)}</span>
        </div>
        <span className="h-3 w-px bg-surface-4" />
        <div
          className="flex items-center gap-1.5"
          title={openai ? `${openai.model.label} equivalent` : 'OpenAI equivalent'}
        >
          <span className="text-gray-500">OpenAI</span>
          <span className="font-mono text-fraud-amber">{formatCost(openaiCost)}</span>
        </div>
        <ChevronDown className={`w-3 h-3 text-gray-500 transition-transform ${open ? 'rotate-180' : ''}`} />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-[380px] z-50
                        bg-surface-1 border border-surface-4 rounded-lg shadow-xl
                        p-4 space-y-3 text-xs">
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-gray-400 font-medium">Session token usage</span>
              <span className="text-gray-500">live</span>
            </div>
            <div className="grid grid-cols-3 gap-2">
              <TokenCell label="Input" value={usage?.tokens.input ?? 0} />
              <TokenCell label="Output" value={usage?.tokens.output ?? 0} />
              <TokenCell label="Total" value={usage?.tokens.total ?? 0} accent />
            </div>
          </div>

          <div className="border-t border-surface-3 pt-3">
            <div className="text-gray-400 font-medium mb-2">Compare against</div>
            <div className="space-y-2">
              <ModelSelector
                providerLabel="Anthropic API"
                provider={usage?.providers.anthropic}
                selectedId={anthropic?.id ?? ''}
                onChange={handleAnthropicChange}
              />
              <ModelSelector
                providerLabel="OpenAI API"
                provider={usage?.providers.openai}
                selectedId={openai?.id ?? ''}
                onChange={handleOpenaiChange}
              />
            </div>
          </div>

          <div className="border-t border-surface-3 pt-3">
            <div className="text-gray-400 font-medium mb-2">Equivalent API cost</div>
            <div className="space-y-1.5">
              <CostRow
                label={anthropic?.model.label ?? 'Claude Sonnet 4.5'}
                sublabel="Anthropic API"
                cost={anthropicCost}
                rate={anthropic?.model}
              />
              <CostRow
                label={openai?.model.label ?? 'GPT-4o'}
                sublabel="OpenAI API"
                cost={openaiCost}
                rate={openai?.model}
              />
            </div>
          </div>

          {onPrem?.enabled && onPrem.config_summary && (
            <div className="border-t border-surface-3 pt-3">
              <div className="text-gray-400 font-medium mb-2 flex items-center gap-1.5">
                <Server className="w-3 h-3" />
                On-prem TCO estimate
              </div>
              <div className="space-y-1.5">
                <OnPremCostRow label="Energy" sublabel={`${onPrem.total_watts?.toFixed(0) ?? '?'}W total draw`} cost={onPrem.energy_cost_usd ?? 0} />
                <OnPremCostRow label="Hardware" sublabel={`${onPrem.config_summary.amortization_years}yr amortization`} cost={onPrem.hardware_cost_usd ?? 0} />
                <OnPremCostRow label="Maintenance" sublabel="staff + upkeep" cost={onPrem.maintenance_cost_usd ?? 0} />
                <div className="flex items-center justify-between px-2 py-1.5 rounded-md bg-blue-500/10 border border-blue-500/30">
                  <div>
                    <div className="text-blue-400 font-medium">Total on-prem</div>
                    <div className="text-[10px] text-gray-500">
                      {onPrem.config_summary.gpu_label} x{onPrem.config_summary.num_gpus} &middot; {onPrem.config_summary.gpu_utilization_pct}% util &middot; ${onPrem.config_summary.electricity_rate_kwh}/kWh
                    </div>
                  </div>
                  <div className="font-mono text-blue-400 font-semibold">
                    {formatCost(onPremCost)}
                  </div>
                </div>
              </div>
            </div>
          )}

          {cloudMax > 0 && (
            <div className="border-t border-surface-3 pt-3">
              <div className="flex items-center justify-between">
                <span className="text-gray-400">Saved vs. cloud</span>
                <span className="font-mono text-fraud-green font-semibold">
                  {formatCost(cloudMax)}
                </span>
              </div>
              {onPrem?.enabled && onPremCost > 0 && cloudMax > onPremCost && (
                <div className="flex items-center justify-between mt-1">
                  <span className="text-gray-500 text-[10px]">On-prem savings vs. cloud</span>
                  <span className="font-mono text-blue-400 text-[10px]">
                    {formatCost(cloudMax - onPremCost)} ({((1 - onPremCost / cloudMax) * 100).toFixed(0)}%)
                  </span>
                </div>
              )}
              <p className="text-gray-600 mt-1 leading-relaxed">
                Running on a local inference service — actual API spend stays $0.
                {onPrem?.enabled && ' On-prem TCO reflects real infrastructure costs.'}
              </p>
            </div>
          )}

          <div className="border-t border-surface-3 pt-3 flex items-center justify-between gap-2">
            <div className="text-[10px] text-gray-600 leading-tight">
              <div>
                Prices from{' '}
                {usage?.pricing_source?.source_url ? (
                  <a
                    href={usage.pricing_source.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="text-gray-400 hover:text-accent underline decoration-dotted"
                  >
                    {usage.pricing_source.source === 'litellm' ? 'LiteLLM' : usage.pricing_source.source}
                  </a>
                ) : (
                  <span className="text-gray-500">built-in table</span>
                )}
                {usage?.pricing_source?.stale && (
                  <span className="text-fraud-amber ml-1">(stale)</span>
                )}
              </div>
              <div>
                Updated{' '}
                <span className="text-gray-400">
                  {formatRelativeTime(usage?.pricing_source?.fetched_at ?? 0)}
                </span>
              </div>
            </div>
            {onRefreshPricing && (
              <button
                onClick={handleRefresh}
                disabled={refreshing}
                className="flex items-center gap-1 px-2 py-1 rounded-md
                           bg-surface-2 border border-surface-4
                           hover:border-accent/40 hover:text-accent
                           text-gray-400 disabled:opacity-50"
              >
                {refreshing
                  ? <Loader2 className="w-3 h-3 animate-spin" />
                  : <RefreshCw className="w-3 h-3" />}
                <span className="text-[10px]">Refresh</span>
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function ModelSelector({
  providerLabel, provider, selectedId, onChange,
}: {
  providerLabel: string;
  provider: ProviderCostEstimate | undefined;
  selectedId: string;
  onChange: (id: string) => void;
}) {
  const models = provider ? Object.entries(provider.models) : [];
  return (
    <label className="flex items-center justify-between gap-2 bg-surface-2 border border-surface-3 rounded-md px-2 py-1.5">
      <span className="text-[10px] uppercase tracking-wide text-gray-500 shrink-0">
        {providerLabel}
      </span>
      <select
        value={selectedId}
        onChange={(e) => onChange(e.target.value)}
        disabled={!provider}
        className="flex-1 min-w-0 bg-surface-3 border border-surface-4 rounded px-2 py-1
                   text-gray-200 text-xs outline-none
                   focus:border-accent/50 disabled:opacity-50"
      >
        {models.length === 0 && <option value="">—</option>}
        {models.map(([id, m]) => (
          <option key={id} value={id}>
            {m.label} · ${m.input_per_mtok_usd}/${m.output_per_mtok_usd}
          </option>
        ))}
      </select>
    </label>
  );
}

function TokenCell({ label, value, accent }: { label: string; value: number; accent?: boolean }) {
  return (
    <div className="bg-surface-2 rounded-md px-2 py-1.5 border border-surface-3">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`font-mono ${accent ? 'text-accent' : 'text-gray-200'}`}>
        {value.toLocaleString()}
      </div>
    </div>
  );
}

function CostRow({
  label, sublabel, cost, highlight, rate,
}: {
  label: string;
  sublabel: string;
  cost: number;
  highlight?: boolean;
  rate?: ProviderModelCost;
}) {
  return (
    <div className={`flex items-center justify-between px-2 py-1.5 rounded-md
                     ${highlight ? 'bg-fraud-green/10 border border-fraud-green/30' : 'bg-surface-2'}`}>
      <div>
        <div className={highlight ? 'text-fraud-green font-medium' : 'text-gray-300'}>{label}</div>
        <div className="text-[10px] text-gray-500">
          {rate
            ? `${sublabel} · $${rate.input_per_mtok_usd}/$${rate.output_per_mtok_usd} per MTok`
            : sublabel}
        </div>
      </div>
      <div className={`font-mono ${highlight ? 'text-fraud-green' : 'text-fraud-amber'}`}>
        {formatCost(cost)}
      </div>
    </div>
  );
}

function OnPremCostRow({ label, sublabel, cost }: { label: string; sublabel: string; cost: number }) {
  return (
    <div className="flex items-center justify-between px-2 py-1 rounded-md bg-surface-2">
      <div>
        <div className="text-gray-400 text-[11px]">{label}</div>
        <div className="text-[10px] text-gray-600">{sublabel}</div>
      </div>
      <div className="font-mono text-blue-400/70 text-[11px]">{formatCost(cost)}</div>
    </div>
  );
}
