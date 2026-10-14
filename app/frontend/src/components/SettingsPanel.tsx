import { useState, useEffect } from 'react';
import { Cpu, Zap, Monitor, X, Loader2, Check, Save, CheckCircle2, XCircle, Server, DollarSign } from 'lucide-react';
import { getLLMConfig, updateLLMConfig, testLLMConnection, getOnPremConfig, updateOnPremConfig, getGpuPresets } from '../api';
import type { LLMConfig, LLMProviderConfig } from '../api';
import type { OnPremConfig, GpuPreset } from '../types';

interface GpuConfig {
  setting: string;
  hardware: {
    detected: boolean;
    vendor: string | null;
    name: string | null;
    memory: string | null;
    driver: string | null;
  };
  rapids: Record<string, string | null>;
  active: boolean;
  xgboost_gpu: boolean;
  force_cpu_env: boolean;
  status: string;
}

interface DiscoveredApp {
  name: string;
  subdomain: string;
  status: string;
  url: string | null;
}

interface EnvConfig {
  is_cml: boolean;
  cml_env: Record<string, string>;
  discovered_apps: DiscoveredApp[];
  discovery_error: string | null;
  backend_url_env: string | null;
  resolved_backend_url: string | null;
  mode: 'embedded' | 'proxy' | 'disconnected';
}

type LlmProviderId = 'ollama' | 'caii' | 'vllm';

const LLM_PROVIDERS: { id: LlmProviderId; label: string; endpointPlaceholder: string; modelPlaceholder: string }[] = [
  { id: 'ollama', label: 'Ollama', endpointPlaceholder: 'http://localhost:11434/v1', modelPlaceholder: 'llama3.2:latest' },
  { id: 'caii', label: 'Cloudera AI', endpointPlaceholder: 'https://ml-xxxxxxxx.your-domain.com/namespaces/serving/endpoints/your-model', modelPlaceholder: 'meta/llama-3_1-8b-instruct' },
  { id: 'vllm', label: 'vLLM', endpointPlaceholder: 'http://localhost:8000/v1', modelPlaceholder: 'meta-llama/Llama-3.1-8B-Instruct' },
];

function providerConfig(cfg: LLMConfig, p: string): LLMProviderConfig {
  return p === 'caii' ? cfg.caii : p === 'vllm' ? cfg.vllm : cfg.ollama;
}

interface Props {
  onClose: () => void;
  onBackendChange?: (connected: boolean, url: string | null) => void;
}

export function SettingsPanel({ onClose, onBackendChange }: Props) {
  // GPU state
  const [gpuConfig, setGpuConfig] = useState<GpuConfig | null>(null);
  const [gpuSetting, setGpuSetting] = useState<string>('auto');
  const [gpuSaving, setGpuSaving] = useState(false);
  const [gpuSaved, setGpuSaved] = useState(false);
  const [gpuError, setGpuError] = useState<string | null>(null);

  // Environment / Backend state
  const [envConfig, setEnvConfig] = useState<EnvConfig | null>(null);
  const [backendUrl, setBackendUrl] = useState('');
  const [backendSaving, setBackendSaving] = useState(false);
  const [backendSaved, setBackendSaved] = useState(false);
  const [backendError, setBackendError] = useState<string | null>(null);
  const [backendTesting, setBackendTesting] = useState(false);
  const [backendTestResult, setBackendTestResult] = useState<{ status: string; detail?: Record<string, unknown>; error?: string } | null>(null);

  // LLM state
  const [llmConfig, setLlmConfig] = useState<LLMConfig | null>(null);
  const [provider, setProvider] = useState('ollama');
  const [endpoint, setEndpoint] = useState('');
  const [model, setModel] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [llmSaving, setLlmSaving] = useState(false);
  const [llmSaved, setLlmSaved] = useState(false);
  const [llmError, setLlmError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ status: string; model?: string; reply?: string; error?: string } | null>(null);

  // On-prem TCO state
  const [onPremConfig, setOnPremConfig] = useState<OnPremConfig | null>(null);
  const [gpuPresets, setGpuPresets] = useState<Record<string, GpuPreset> | null>(null);
  const [onPremSaving, setOnPremSaving] = useState(false);
  const [onPremSaved, setOnPremSaved] = useState(false);
  const [onPremError, setOnPremError] = useState<string | null>(null);

  const loadGpuConfig = () => {
    fetch('/api/config/gpu')
      .then(r => { if (!r.ok) throw new Error(`${r.status}`); return r.json(); })
      .then(data => {
        setGpuConfig(data);
        setGpuSetting(data.setting);
        setGpuError(null);
      })
      .catch(() => setGpuError('Could not load GPU config (backend not connected?)'));
  };

  const loadLlmConfig = () => {
    getLLMConfig().then(cfg => {
      setLlmConfig(cfg);
      setProvider(cfg.provider);
      const active = providerConfig(cfg, cfg.provider);
      setEndpoint(active.endpoint);
      setModel(active.model);
    }).catch(() => {});
  };

  useEffect(() => {
    fetch('/frontend/config/environment')
      .then(r => r.json())
      .then((data: EnvConfig) => {
        setEnvConfig(data);
        setBackendUrl(data.resolved_backend_url || '');
      })
      .catch(() => {});

    loadGpuConfig();
    loadLlmConfig();
    getOnPremConfig().then(setOnPremConfig).catch(() => {});
    getGpuPresets().then(d => setGpuPresets(d.presets)).catch(() => {});
  }, []);

  const handleGpuChange = async (value: string) => {
    setGpuSetting(value);
    setGpuSaving(true);
    setGpuSaved(false);
    setGpuError(null);

    try {
      const res = await fetch('/api/config/gpu', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ enabled: value }),
      });
      if (!res.ok) throw new Error('Failed to save');
      await res.json();
      setGpuSaved(true);
      const refreshed = await fetch('/api/config/gpu').then(r => r.json());
      setGpuConfig(refreshed);
      setTimeout(() => setGpuSaved(false), 2000);
    } catch {
      setGpuError('Failed to save GPU setting');
    } finally {
      setGpuSaving(false);
    }
  };

  const handleProviderChange = (p: string) => {
    setProvider(p);
    if (llmConfig) {
      const cfg = providerConfig(llmConfig, p);
      setEndpoint(cfg.endpoint);
      setModel(cfg.model);
    }
    setApiKey('');
    setLlmSaved(false);
    setTestResult(null);
  };

  const handleLlmSave = async () => {
    setLlmSaving(true);
    setLlmError(null);
    setLlmSaved(false);
    setTestResult(null);
    try {
      await updateLLMConfig(provider, endpoint, model, provider !== 'ollama' ? apiKey || undefined : undefined);
      setLlmSaved(true);
      setApiKey('');  // Clear the input after save so the secret doesn't linger in the DOM.
      if (llmConfig) {
        const key = provider as LlmProviderId;
        llmConfig[key] = { endpoint, model, has_api_key: llmConfig[key]?.has_api_key || !!apiKey };
        llmConfig.provider = provider;
      }
    } catch (err) {
      setLlmError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setLlmSaving(false);
    }
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    setLlmError(null);
    try {
      const result = await testLLMConnection();
      setTestResult(result);
    } catch (err) {
      setTestResult({ status: 'error', error: err instanceof Error ? err.message : 'Request failed' });
    } finally {
      setTesting(false);
    }
  };

  const handleBackendSave = async () => {
    setBackendSaving(true);
    setBackendSaved(false);
    setBackendError(null);
    setBackendTestResult(null);
    try {
      const res = await fetch('/frontend/config/backend-url', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: backendUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to save');
      setBackendSaved(true);
      // Refresh env config and reload backend-dependent settings
      const envRes = await fetch('/frontend/config/environment');
      const envData: EnvConfig = await envRes.json();
      setEnvConfig(envData);
      onBackendChange?.(!!envData.resolved_backend_url, envData.resolved_backend_url);
      loadGpuConfig();
      loadLlmConfig();
      setTimeout(() => setBackendSaved(false), 2000);
    } catch (err) {
      setBackendError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setBackendSaving(false);
    }
  };

  const handleBackendTest = async () => {
    setBackendTesting(true);
    setBackendTestResult(null);
    setBackendError(null);
    try {
      const res = await fetch('/frontend/config/backend-test');
      setBackendTestResult(await res.json());
    } catch (err) {
      setBackendTestResult({ status: 'error', error: err instanceof Error ? err.message : 'Request failed' });
    } finally {
      setBackendTesting(false);
    }
  };

  const handleOnPremSave = async () => {
    if (!onPremConfig) return;
    setOnPremSaving(true);
    setOnPremSaved(false);
    setOnPremError(null);
    try {
      const result = await updateOnPremConfig(onPremConfig);
      setOnPremConfig(result.config);
      setOnPremSaved(true);
      setTimeout(() => setOnPremSaved(false), 2000);
    } catch (err) {
      setOnPremError(err instanceof Error ? err.message : 'Failed to save');
    } finally {
      setOnPremSaving(false);
    }
  };

  const updateOnPremField = <K extends keyof OnPremConfig>(key: K, value: OnPremConfig[K]) => {
    if (!onPremConfig) return;
    setOnPremConfig({ ...onPremConfig, [key]: value });
    setOnPremSaved(false);
  };

  const rapidsLibs = gpuConfig?.rapids
    ? Object.entries(gpuConfig.rapids)
    : [];
  const anyRapidsInstalled = rapidsLibs.some(([, v]) => v !== null);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-16 bg-black/50 backdrop-blur-sm"
         onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}>
      <div className="bg-surface-1 rounded-xl border border-surface-3 shadow-2xl w-[480px] max-h-[80vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-surface-3">
          <h2 className="text-sm font-semibold text-gray-200">Settings</h2>
          <button onClick={onClose} className="p-1 text-gray-500 hover:text-gray-300 rounded-lg hover:bg-surface-3">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* Backend Connection Section */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              Backend Connection
            </h3>

            <div className="bg-surface-2 rounded-lg p-3 border border-surface-3 space-y-3">
              {/* Status */}
              <div className="flex items-center gap-2">
                <span className={`w-2 h-2 rounded-full ${
                  envConfig?.mode === 'proxy' || envConfig?.mode === 'embedded'
                    ? 'bg-fraud-green' : 'bg-fraud-red'
                }`} />
                <span className="text-xs text-gray-300">
                  {envConfig?.mode === 'embedded' && 'Embedded (local mode)'}
                  {envConfig?.mode === 'proxy' && 'Connected via proxy'}
                  {envConfig?.mode === 'disconnected' && 'Not connected'}
                  {!envConfig && 'Loading...'}
                </span>
                {envConfig?.resolved_backend_url && (
                  <span className="text-[10px] font-mono text-gray-500 ml-auto truncate max-w-[200px]"
                        title={envConfig.resolved_backend_url}>
                    {envConfig.resolved_backend_url}
                  </span>
                )}
              </div>

              {/* URL Input — hidden in embedded mode */}
              {envConfig?.mode !== 'embedded' && (
                <>
                  <div>
                    <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                      Backend API URL
                    </label>
                    <input
                      type="text"
                      value={backendUrl}
                      onChange={e => { setBackendUrl(e.target.value); setBackendSaved(false); setBackendTestResult(null); }}
                      placeholder="https://fraud-api.ml-xxxxxxxx.your-domain.com"
                      className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                 text-gray-200 font-mono placeholder-gray-600
                                 focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
                    />
                  </div>

                  {/* Discovered apps — quick-pick buttons */}
                  {envConfig?.discovered_apps && envConfig.discovered_apps.length > 0 && (
                    <div>
                      <span className="text-[10px] text-gray-500 uppercase tracking-wider">Discovered apps</span>
                      <div className="mt-1 space-y-1">
                        {envConfig.discovered_apps.map((a) => (
                          <button
                            key={a.subdomain}
                            onClick={() => { if (a.url) { setBackendUrl(a.url); setBackendSaved(false); setBackendTestResult(null); } }}
                            className={`w-full text-left px-2 py-1.5 rounded text-xs border transition-colors
                              ${a.url === backendUrl
                                ? 'border-accent/30 bg-accent/5'
                                : 'border-surface-4 hover:border-gray-500 hover:bg-surface-3/50'
                              }`}
                          >
                            <div className="flex items-center justify-between">
                              <span className="text-gray-200">{a.name}</span>
                              <span className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${
                                a.status === 'APPLICATION_RUNNING'
                                  ? 'bg-fraud-green/10 text-fraud-green'
                                  : 'bg-gray-700 text-gray-400'
                              }`}>
                                {a.status.replace('APPLICATION_', '')}
                              </span>
                            </div>
                            {a.url && <div className="text-[10px] font-mono text-gray-500 mt-0.5 truncate">{a.url}</div>}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {envConfig?.discovery_error && (
                    <p className="text-[10px] text-gray-600">
                      Auto-discovery: {envConfig.discovery_error}
                    </p>
                  )}

                  {/* Action Buttons */}
                  <div className="flex gap-2">
                    <button
                      onClick={handleBackendSave}
                      disabled={backendSaving}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/20 text-accent text-xs font-medium rounded-md
                                 hover:bg-accent/30 disabled:opacity-50 transition-colors"
                    >
                      {backendSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                      Save
                    </button>
                    <button
                      onClick={handleBackendTest}
                      disabled={backendTesting || !backendUrl}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 text-gray-300 text-xs font-medium rounded-md
                                 hover:bg-surface-4 disabled:opacity-50 transition-colors"
                    >
                      {backendTesting ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                      Test
                    </button>
                  </div>

                  {/* Results */}
                  {backendTestResult?.status === 'ok' && (
                    <div className="flex items-start gap-2 text-xs text-fraud-green bg-fraud-green/5 border border-fraud-green/20 rounded-md px-3 py-2">
                      <CheckCircle2 className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="font-medium">Backend connected</p>
                        {backendTestResult.detail && (
                          <p className="text-fraud-green/80 mt-0.5">
                            DB: {(backendTestResult.detail as Record<string, unknown>).database ? 'ok' : 'down'},
                            Model: {(backendTestResult.detail as Record<string, unknown>).model ? 'ok' : 'down'}
                          </p>
                        )}
                      </div>
                    </div>
                  )}
                  {backendTestResult?.status === 'error' && (
                    <div className="flex items-start gap-2 text-xs text-fraud-red bg-fraud-red/5 border border-fraud-red/20 rounded-md px-3 py-2">
                      <XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                      <div>
                        <p className="font-medium">Connection failed</p>
                        <p className="text-fraud-red/80 mt-0.5 break-all">{backendTestResult.error}</p>
                      </div>
                    </div>
                  )}
                  {backendError && <p className="text-xs text-fraud-red">{backendError}</p>}
                  {backendSaved && (
                    <div className="flex items-center gap-1.5 text-xs text-fraud-green">
                      <CheckCircle2 className="w-3 h-3" /> Backend URL saved
                    </div>
                  )}
                </>
              )}
            </div>
          </section>

          {/* GPU / RAPIDS Section */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              GPU Acceleration (RAPIDS)
            </h3>

            {/* GPU Hardware Status */}
            <div className="bg-surface-2 rounded-lg p-3 border border-surface-3 mb-3">
              <div className="flex items-center gap-2 mb-2">
                <Monitor className="w-4 h-4 text-gray-400" />
                <span className="text-xs font-medium text-gray-300">Hardware</span>
              </div>
              {gpuConfig ? (
                gpuConfig.hardware.detected ? (
                  <div className="space-y-1 text-xs">
                    <div className="flex justify-between">
                      <span className="text-gray-500">GPU</span>
                      <span className="text-fraud-green">{gpuConfig.hardware.name}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Memory</span>
                      <span className="text-gray-300">{gpuConfig.hardware.memory}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-gray-500">Driver</span>
                      <span className="text-gray-300">{gpuConfig.hardware.driver}</span>
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-gray-500">No NVIDIA GPU detected</p>
                )
              ) : (
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Loader2 className="w-3 h-3 animate-spin" /> Loading...
                </div>
              )}
            </div>

            {/* RAPIDS Libraries Status */}
            <div className="bg-surface-2 rounded-lg p-3 border border-surface-3 mb-3">
              <div className="flex items-center gap-2 mb-2">
                <Zap className="w-4 h-4 text-gray-400" />
                <span className="text-xs font-medium text-gray-300">RAPIDS Libraries</span>
              </div>
              {gpuConfig ? (
                <div className="grid grid-cols-3 gap-2">
                  {rapidsLibs.map(([lib, version]) => (
                    <div key={lib} className={`text-center px-2 py-1.5 rounded text-xs border
                      ${version
                        ? 'bg-fraud-green/5 border-fraud-green/20 text-fraud-green'
                        : 'bg-surface-3/50 border-surface-4 text-gray-500'
                      }`}>
                      <div className="font-medium">{lib}</div>
                      <div className="text-[10px] mt-0.5 opacity-75">
                        {version || 'not installed'}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="flex items-center gap-2 text-xs text-gray-500">
                  <Loader2 className="w-3 h-3 animate-spin" /> Loading...
                </div>
              )}
              {gpuConfig && !anyRapidsInstalled && (
                gpuConfig.hardware.vendor === 'AMD' ? (
                  <p className="text-[10px] text-gray-600 mt-2">
                    RAPIDS is CUDA-only — unavailable on AMD. Dataframes stay on the CPU;
                    XGBoost training is {gpuConfig.xgboost_gpu ? 'GPU-accelerated via ROCm/HIP' : 'on the CPU'}.
                  </p>
                ) : (
                  <p className="text-[10px] text-gray-600 mt-2">
                    Install with: pip install --extra-index-url https://pypi.nvidia.com -r requirements-gpu.txt
                  </p>
                )
              )}
            </div>

            {/* GPU Mode Toggle */}
            <div className="bg-surface-2 rounded-lg p-3 border border-surface-3">
              <div className="flex items-center gap-2 mb-3">
                <Cpu className="w-4 h-4 text-gray-400" />
                <span className="text-xs font-medium text-gray-300">Processing Mode</span>
                {gpuSaving && <Loader2 className="w-3 h-3 animate-spin text-accent ml-auto" />}
                {gpuSaved && <Check className="w-3 h-3 text-fraud-green ml-auto" />}
              </div>

              <div className="space-y-2">
                {[
                  { value: 'auto', label: 'Auto', desc: 'Use GPU if available, fall back to CPU' },
                  { value: 'true', label: 'GPU Only', desc: 'Require GPU (fail if unavailable)' },
                  { value: 'false', label: 'CPU Only', desc: 'Always use CPU, even if GPU available' },
                ].map(option => (
                  <label
                    key={option.value}
                    className={`flex items-start gap-3 p-2 rounded-lg cursor-pointer border transition-colors
                      ${gpuSetting === option.value
                        ? 'bg-accent/5 border-accent/30'
                        : 'border-transparent hover:bg-surface-3/50'
                      }`}
                  >
                    <input
                      type="radio"
                      name="gpu-mode"
                      value={option.value}
                      checked={gpuSetting === option.value}
                      onChange={() => handleGpuChange(option.value)}
                      className="mt-0.5 accent-accent"
                    />
                    <div>
                      <div className="text-xs font-medium text-gray-200">{option.label}</div>
                      <div className="text-[10px] text-gray-500">{option.desc}</div>
                    </div>
                  </label>
                ))}
              </div>

              {gpuError && (
                <p className="text-xs text-fraud-red mt-2">{gpuError}</p>
              )}

              {gpuConfig && (
                <div className="mt-3 pt-3 border-t border-surface-4">
                  <div className="flex items-center justify-between text-xs">
                    <span className="text-gray-500">Current runtime</span>
                    <span className={gpuConfig.active ? 'text-fraud-green' : 'text-gray-400'}>
                      {gpuConfig.status}
                    </span>
                  </div>
                  <p className="text-[10px] text-gray-600 mt-1">
                    Changes apply to pipeline scripts on next run. Restart the backend to update runtime status.
                  </p>
                </div>
              )}
            </div>
          </section>

          {/* On-Prem TCO Section */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              On-Prem TCO Calculator
            </h3>

            <div className="bg-surface-2 rounded-lg p-3 border border-surface-3 space-y-3">
              {/* Enable toggle */}
              <label className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Server className="w-4 h-4 text-gray-400" />
                  <span className="text-xs font-medium text-gray-300">Enable on-prem cost tracking</span>
                </div>
                <input
                  type="checkbox"
                  checked={onPremConfig?.enabled ?? true}
                  onChange={e => updateOnPremField('enabled', e.target.checked)}
                  className="accent-accent"
                />
              </label>

              {onPremConfig?.enabled && gpuPresets && (
                <>
                  {/* GPU Preset */}
                  <div>
                    <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">GPU Model</label>
                    <select
                      value={onPremConfig.gpu_preset}
                      onChange={e => updateOnPremField('gpu_preset', e.target.value)}
                      className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                 text-gray-200 focus:outline-none focus:border-accent/50"
                    >
                      {Object.entries(gpuPresets).map(([id, preset]) => (
                        <option key={id} value={id}>
                          {preset.label} ({preset.tdp_watts}W, {preset.memory_gb}GB, ${preset.cost_usd.toLocaleString()})
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Num GPUs + Utilization — side by side */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">GPUs</label>
                      <input
                        type="number"
                        min={1}
                        max={64}
                        value={onPremConfig.num_gpus}
                        onChange={e => updateOnPremField('num_gpus', parseInt(e.target.value) || 1)}
                        className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                   text-gray-200 font-mono focus:outline-none focus:border-accent/50"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        Utilization ({onPremConfig.gpu_utilization_pct}%)
                      </label>
                      <input
                        type="range"
                        min={5}
                        max={100}
                        step={5}
                        value={onPremConfig.gpu_utilization_pct}
                        onChange={e => updateOnPremField('gpu_utilization_pct', parseInt(e.target.value))}
                        className="w-full accent-accent mt-1"
                      />
                    </div>
                  </div>

                  {/* Power & Cooling */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        <DollarSign className="w-2.5 h-2.5 inline" /> Electricity ($/kWh)
                      </label>
                      <input
                        type="number"
                        min={0.01}
                        max={1}
                        step={0.01}
                        value={onPremConfig.electricity_rate_kwh}
                        onChange={e => updateOnPremField('electricity_rate_kwh', parseFloat(e.target.value) || 0.15)}
                        className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                   text-gray-200 font-mono focus:outline-none focus:border-accent/50"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        PUE (cooling)
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={3}
                        step={0.05}
                        value={onPremConfig.pue}
                        onChange={e => updateOnPremField('pue', parseFloat(e.target.value) || 1.3)}
                        className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                   text-gray-200 font-mono focus:outline-none focus:border-accent/50"
                      />
                      <p className="text-[10px] text-gray-600 mt-0.5">1.0 = no cooling overhead</p>
                    </div>
                  </div>

                  {/* Amortization & Maintenance */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        Amortization (years)
                      </label>
                      <input
                        type="number"
                        min={1}
                        max={10}
                        step={0.5}
                        value={onPremConfig.amortization_years}
                        onChange={e => updateOnPremField('amortization_years', parseFloat(e.target.value) || 3)}
                        className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                   text-gray-200 font-mono focus:outline-none focus:border-accent/50"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        Maintenance (% / yr)
                      </label>
                      <input
                        type="number"
                        min={0}
                        max={50}
                        step={1}
                        value={onPremConfig.maintenance_pct}
                        onChange={e => updateOnPremField('maintenance_pct', parseFloat(e.target.value) || 0)}
                        className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                   text-gray-200 font-mono focus:outline-none focus:border-accent/50"
                      />
                    </div>
                  </div>

                  {/* Server power + base cost */}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        Server power (W)
                      </label>
                      <input
                        type="number"
                        min={50}
                        max={5000}
                        step={50}
                        value={onPremConfig.server_power_watts}
                        onChange={e => updateOnPremField('server_power_watts', parseFloat(e.target.value) || 300)}
                        className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                   text-gray-200 font-mono focus:outline-none focus:border-accent/50"
                      />
                      <p className="text-[10px] text-gray-600 mt-0.5">CPU, RAM, NIC, fans</p>
                    </div>
                    <div>
                      <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                        Server cost ($)
                      </label>
                      <input
                        type="number"
                        min={0}
                        max={100000}
                        step={500}
                        value={onPremConfig.server_base_cost_usd}
                        onChange={e => updateOnPremField('server_base_cost_usd', parseFloat(e.target.value) || 5000)}
                        className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                   text-gray-200 font-mono focus:outline-none focus:border-accent/50"
                      />
                      <p className="text-[10px] text-gray-600 mt-0.5">Chassis excl. GPUs</p>
                    </div>
                  </div>

                  {/* Throughput override */}
                  <div>
                    <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                      Throughput override (tok/s)
                    </label>
                    <input
                      type="number"
                      min={0}
                      max={100000}
                      step={100}
                      value={onPremConfig.tokens_per_second ?? ''}
                      onChange={e => {
                        const v = e.target.value ? parseFloat(e.target.value) : null;
                        updateOnPremField('tokens_per_second', v);
                      }}
                      placeholder={`Default: ${gpuPresets[onPremConfig.gpu_preset]?.default_tok_s ?? '?'} tok/s`}
                      className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                                 text-gray-200 font-mono placeholder-gray-600
                                 focus:outline-none focus:border-accent/50"
                    />
                    <p className="text-[10px] text-gray-600 mt-0.5">
                      Leave empty to use GPU preset default. Set from actual measurements for accuracy.
                    </p>
                  </div>

                  {/* Save button */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={handleOnPremSave}
                      disabled={onPremSaving}
                      className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/20 text-accent text-xs font-medium rounded-md
                                 hover:bg-accent/30 disabled:opacity-50 transition-colors"
                    >
                      {onPremSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                      Save
                    </button>
                    {onPremSaved && (
                      <span className="flex items-center gap-1 text-xs text-fraud-green">
                        <CheckCircle2 className="w-3 h-3" /> Saved
                      </span>
                    )}
                    {onPremError && <span className="text-xs text-fraud-red">{onPremError}</span>}
                  </div>

                  {/* Source attribution */}
                  <div className="text-[10px] text-gray-600 leading-tight border-t border-surface-4 pt-2">
                    GPU specs from NVIDIA/Intel data sheets. Cost model based on{' '}
                    <a href="https://energy.inference.net/" target="_blank" rel="noreferrer"
                       className="text-gray-400 underline decoration-dotted hover:text-accent">
                      energy.inference.net
                    </a>{' '}
                    and{' '}
                    <a href="https://arxiv.org/html/2512.03024v1" target="_blank" rel="noreferrer"
                       className="text-gray-400 underline decoration-dotted hover:text-accent">
                      TokenPowerBench
                    </a>.
                  </div>
                </>
              )}
            </div>
          </section>

          {/* LLM Section */}
          <section>
            <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
              LLM Configuration
            </h3>

            <div className="bg-surface-2 rounded-lg p-3 border border-surface-3 space-y-4">
              {/* Provider */}
              <div>
                <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1.5">Provider</label>
                <div className="flex gap-2">
                  {LLM_PROVIDERS.map(p => (
                    <button
                      key={p.id}
                      onClick={() => handleProviderChange(p.id)}
                      className={`px-3 py-2 text-xs rounded-lg border transition-colors
                        ${provider === p.id
                          ? 'border-accent bg-accent/10 text-accent'
                          : 'border-surface-4 text-gray-400 hover:border-gray-500 hover:text-gray-300'
                        }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Endpoint */}
              <div>
                <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">Endpoint URL</label>
                <input
                  type="text"
                  value={endpoint}
                  onChange={e => { setEndpoint(e.target.value); setLlmSaved(false); setTestResult(null); }}
                  placeholder={LLM_PROVIDERS.find(p => p.id === provider)?.endpointPlaceholder}
                  className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                             text-gray-200 font-mono placeholder-gray-600
                             focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
                />
                {provider === 'caii' && (
                  <p className="text-[10px] text-gray-600 mt-1">
                    Copy the Model Endpoint URL from the CAII console. The /v1 suffix is added automatically.
                  </p>
                )}
                {provider === 'vllm' && (
                  <p className="text-[10px] text-gray-600 mt-1">
                    Base URL of a vLLM server running the OpenAI-compatible API. The /v1 suffix is added automatically.
                  </p>
                )}
              </div>

              {/* Model */}
              <div>
                <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">Model</label>
                <input
                  type="text"
                  value={model}
                  onChange={e => { setModel(e.target.value); setLlmSaved(false); setTestResult(null); }}
                  placeholder={LLM_PROVIDERS.find(p => p.id === provider)?.modelPlaceholder}
                  className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                             text-gray-200 font-mono placeholder-gray-600
                             focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
                />
              </div>

              {provider !== 'ollama' && (
                <div>
                  <label className="block text-[10px] text-gray-500 uppercase tracking-wider mb-1">
                    {provider === 'caii' ? 'CDP Token' : 'API Key'}
                    {llmConfig && providerConfig(llmConfig, provider).has_api_key && !apiKey && (
                      <span className="ml-2 text-fraud-green normal-case tracking-normal">
                        <Check className="w-2.5 h-2.5 inline" /> configured
                      </span>
                    )}
                  </label>
                  <input
                    type="password"
                    value={apiKey}
                    onChange={e => { setApiKey(e.target.value); setLlmSaved(false); setTestResult(null); }}
                    placeholder={llmConfig && providerConfig(llmConfig, provider).has_api_key
                      ? '••••••••  (leave blank to keep existing)'
                      : provider === 'caii' ? 'Paste your CDP access token' : 'Optional — only if the server enforces one'}
                    autoComplete="off"
                    className="w-full px-2.5 py-1.5 text-xs bg-surface-0 border border-surface-4 rounded-md
                               text-gray-200 font-mono placeholder-gray-600
                               focus:outline-none focus:border-accent/50 focus:ring-1 focus:ring-accent/20"
                  />
                  {provider === 'caii' ? (
                    <p className="text-[10px] text-gray-600 mt-1">
                      In a CML session this is auto-detected from <code className="text-gray-500">/tmp/jwt</code>.
                      Outside CML, paste the token here — it's stored in <code className="text-gray-500">config.yaml</code> and exported as <code className="text-gray-500">CDP_TOKEN</code>.
                    </p>
                  ) : (
                    <p className="text-[10px] text-gray-600 mt-1">
                      Only needed if vLLM was started with <code className="text-gray-500">--api-key</code>.
                      Stored in <code className="text-gray-500">config.yaml</code> and exported as <code className="text-gray-500">VLLM_API_KEY</code>.
                    </p>
                  )}
                </div>
              )}

              {/* Action Buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleLlmSave}
                  disabled={llmSaving || !endpoint || !model}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-accent/20 text-accent text-xs font-medium rounded-md
                             hover:bg-accent/30 disabled:opacity-50 transition-colors"
                >
                  {llmSaving ? <Loader2 className="w-3 h-3 animate-spin" /> : <Save className="w-3 h-3" />}
                  Save
                </button>
                <button
                  onClick={handleTest}
                  disabled={testing || !endpoint || !model}
                  className="flex items-center gap-1.5 px-3 py-1.5 bg-surface-3 text-gray-300 text-xs font-medium rounded-md
                             hover:bg-surface-4 disabled:opacity-50 transition-colors"
                >
                  {testing ? <Loader2 className="w-3 h-3 animate-spin" /> : <Zap className="w-3 h-3" />}
                  Test
                </button>
              </div>

              {/* Test Result */}
              {testResult && testResult.status === 'ok' && (
                <div className="flex items-start gap-2 text-xs text-fraud-green bg-fraud-green/5 border border-fraud-green/20 rounded-md px-3 py-2">
                  <CheckCircle2 className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-medium">Connected successfully</p>
                    {testResult.model && <p className="text-fraud-green/80 mt-0.5">Model: {testResult.model}</p>}
                    {testResult.reply && <p className="text-fraud-green/80">Reply: {testResult.reply}</p>}
                  </div>
                </div>
              )}

              {testResult && testResult.status === 'error' && (
                <div className="flex items-start gap-2 text-xs text-fraud-red bg-fraud-red/5 border border-fraud-red/20 rounded-md px-3 py-2">
                  <XCircle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                  <div>
                    <p className="font-medium">Connection failed</p>
                    <p className="text-fraud-red/80 mt-0.5 break-all">{testResult.error}</p>
                  </div>
                </div>
              )}

              {llmError && (
                <p className="text-xs text-fraud-red">{llmError}</p>
              )}

              {llmSaved && (
                <div className="flex items-center gap-1.5 text-xs text-fraud-green">
                  <CheckCircle2 className="w-3 h-3" />
                  Configuration saved. Restart the app for changes to take full effect.
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
