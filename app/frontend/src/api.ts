import type {
  ChatUsage, CostEstimate, OnPremConfig, GpuPreset, GuardVerdict,
  ExperimentResult, LabelCorrection, FalsePositiveCandidate, ModelMetrics, FeatureImportance,
} from './types';

const API_BASE = '/api';

async function fetchJSON<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`API error ${res.status}: ${text}`);
  }
  return res.json();
}

export async function sendChat(message: string, sessionId: string) {
  return fetchJSON<{
    response: string;
    tool_calls: { tool: string; args: Record<string, unknown>; result_summary: string }[];
    session_id: string;
    usage: ChatUsage;
    guard?: GuardVerdict | null;
  }>('/chat', {
    method: 'POST',
    body: JSON.stringify({ message, session_id: sessionId }),
  });
}

export async function getSessionUsage(sessionId: string) {
  return fetchJSON<CostEstimate>(`/sessions/${sessionId}/usage`);
}

export async function refreshPricing() {
  return fetchJSON<{
    source: string;
    source_url: string | null;
    fetched_at: number;
    stale: boolean;
    error: string | null;
    anthropic_model_count: number;
    openai_model_count: number;
  }>('/config/pricing/refresh', { method: 'POST' });
}

export async function getDashboard(
  timePeriod = 'all',
  groupBy?: string,
  startDate?: string,
  endDate?: string,
) {
  const params = new URLSearchParams({ time_period: timePeriod });
  if (groupBy) params.set('group_by', groupBy);
  if (startDate) params.set('start_date', startDate);
  if (endDate) params.set('end_date', endDate);
  return fetchJSON<Record<string, unknown>>(`/dashboard?${params}`);
}

export async function getDateRange() {
  return fetchJSON<{ min_date: string | null; max_date: string | null }>('/dashboard/date-range');
}

export async function getThresholdAnalysis(sampleSize = 5000) {
  return fetchJSON<Record<string, unknown>>(`/model/threshold-analysis?sample_size=${sampleSize}`);
}

export async function queryTransactions(filters: Record<string, unknown>) {
  return fetchJSON<{ transactions: Record<string, unknown>[]; total_matching: number; showing: number }>(
    '/transactions/query',
    { method: 'POST', body: JSON.stringify(filters) },
  );
}

export async function getTransaction(id: number) {
  return fetchJSON<Record<string, unknown>>(`/transactions/${id}`);
}

export async function scoreTransaction(id: number, explain = true) {
  return fetchJSON<Record<string, unknown>>(`/transactions/${id}/score?explain=${explain}`);
}

export async function explainTransaction(id: number) {
  return fetchJSON<Record<string, unknown>>(`/transactions/${id}/explain`);
}

export async function getAlerts(userId?: number, merchantName?: string, patternType = 'all') {
  const params = new URLSearchParams({ pattern_type: patternType });
  if (userId) params.set('user_id', String(userId));
  if (merchantName) params.set('merchant_name', merchantName);
  return fetchJSON<Record<string, unknown>>(`/alerts?${params}`);
}

export async function clearSession(sessionId: string) {
  return fetchJSON<{ status: string }>(`/sessions/${sessionId}`, { method: 'DELETE' });
}

export async function getHealth() {
  return fetchJSON<{ status: string; database: boolean; model: boolean }>('/health');
}

// On-prem TCO config
export async function getOnPremConfig() {
  return fetchJSON<OnPremConfig>('/config/on-prem');
}

export async function updateOnPremConfig(config: Partial<OnPremConfig>) {
  return fetchJSON<{ message: string; config: OnPremConfig }>('/config/on-prem', {
    method: 'PUT',
    body: JSON.stringify(config),
  });
}

export async function getGpuPresets() {
  return fetchJSON<{ presets: Record<string, GpuPreset> }>('/config/on-prem/presets');
}

export interface LLMProviderConfig {
  endpoint: string;
  model: string;
  has_api_key?: boolean;
}

export interface LLMConfig {
  provider: string;
  ollama: LLMProviderConfig;
  caii: LLMProviderConfig;
  vllm: LLMProviderConfig;
  temperature: number;
  max_tokens: number;
}

export async function getLLMConfig() {
  return fetchJSON<LLMConfig>('/config/llm');
}

export async function updateLLMConfig(provider: string, endpoint: string, model: string, apiKey?: string) {
  const body: Record<string, string> = { provider, endpoint, model };
  if (apiKey) body.api_key = apiKey;
  return fetchJSON<{ status: string }>('/config/llm', {
    method: 'PUT',
    body: JSON.stringify(body),
  });
}

export async function testLLMConnection() {
  return fetchJSON<{ status: string; model?: string; reply?: string; error?: string }>('/config/llm/test', {
    method: 'POST',
  });
}

export function exportTransactionsCSV(params?: {
  user_id?: number;
  is_fraud?: boolean;
  start_date?: string;
  end_date?: string;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.user_id != null) searchParams.set('user_id', String(params.user_id));
  if (params?.is_fraud != null) searchParams.set('is_fraud', String(params.is_fraud));
  if (params?.start_date) searchParams.set('start_date', params.start_date);
  if (params?.end_date) searchParams.set('end_date', params.end_date);
  if (params?.limit) searchParams.set('limit', String(params.limit));
  const url = `${API_BASE}/export/transactions?${searchParams}`;
  window.open(url, '_blank');
}

// ---------------------------------------------------------------------------
// Experiment / Model Retraining API
// ---------------------------------------------------------------------------

export async function getOriginalModelMetrics() {
  return fetchJSON<{
    model: string;
    metrics: ModelMetrics;
    top_features: FeatureImportance[];
    gpu_info: string;
  }>('/experiments/original-metrics');
}

export async function getFalsePositives(limit = 50) {
  return fetchJSON<{
    candidates: FalsePositiveCandidate[];
    total_fraud_in_db: number;
  }>(`/experiments/false-positives?limit=${limit}`);
}

export async function getLabelCorrections() {
  return fetchJSON<{
    corrections: LabelCorrection[];
    total: number;
  }>('/experiments/corrections');
}

export async function applyLabelCorrection(transactionId: number, correctedLabel: number) {
  return fetchJSON<{ transaction_id: number; original_label: number; corrected_label: number }>(
    '/experiments/corrections',
    { method: 'POST', body: JSON.stringify({ transaction_id: transactionId, corrected_label: correctedLabel }) },
  );
}

export async function removeLabelCorrection(transactionId: number) {
  return fetchJSON<{ removed: number }>(
    `/experiments/corrections/${transactionId}`,
    { method: 'DELETE' },
  );
}

export async function generateAdditionalData(nTransactions = 10000) {
  return fetchJSON<{
    generated: number;
    fraud: number;
    legitimate: number;
    fraud_rate: number;
    path: string;
  }>('/experiments/generate-data', {
    method: 'POST',
    body: JSON.stringify({ n_transactions: nTransactions }),
  });
}

export interface ExperimentStartAck {
  status: 'started' | 'busy' | 'idle';
  experiment_id?: string;
  running_experiment_id?: string;
  phase?: string;
  started_at?: number;
  message?: string;
}

export interface ExperimentStatus {
  status: 'idle' | 'running' | 'completed' | 'failed';
  id?: string;
  phase?: string;
  description?: string;
  started_at?: number;
  finished_at?: number;
  result?: ExperimentResult;
  error?: string;
}

export async function runExperiment(opts: {
  use_corrections?: boolean;
  use_generated_data?: boolean;
  description?: string;
  hyperparams?: Record<string, number>;
} = {}) {
  return fetchJSON<ExperimentStartAck>('/experiments/run', {
    method: 'POST',
    body: JSON.stringify(opts),
  });
}

export async function getExperimentStatus() {
  return fetchJSON<ExperimentStatus>('/experiments/status');
}

export async function getExperimentDetail(experimentId: string) {
  return fetchJSON<{ experiment_id: string; result?: ExperimentResult; status: string; error?: string }>(
    `/experiments/${experimentId}`,
  );
}

export async function listExperiments() {
  return fetchJSON<{ experiments: Array<Record<string, unknown>> }>('/experiments');
}

export async function getMerchantInvestigation(merchantName: string, opts?: {
  max_counterparties?: number;
  max_transactions?: number;
}) {
  const params = new URLSearchParams({ merchant_name: merchantName });
  if (opts?.max_counterparties) params.set('max_counterparties', String(opts.max_counterparties));
  if (opts?.max_transactions) params.set('max_transactions', String(opts.max_transactions));
  return fetchJSON<Record<string, unknown>>(`/investigation/merchant?${params}`);
}

export async function traceFraudNetwork(opts: {
  merchant_name?: string;
  user_id?: number;
  direction?: 'merchant_to_users' | 'user_to_merchants' | 'auto';
  fraud_only?: boolean;
  max_counterparties?: number;
}) {
  const params = new URLSearchParams();
  if (opts.merchant_name) params.set('merchant_name', opts.merchant_name);
  if (opts.user_id !== undefined) params.set('user_id', String(opts.user_id));
  if (opts.direction) params.set('direction', opts.direction);
  if (opts.fraud_only !== undefined) params.set('fraud_only', String(opts.fraud_only));
  if (opts.max_counterparties !== undefined) params.set('max_counterparties', String(opts.max_counterparties));
  return fetchJSON<Record<string, unknown>>(`/fraud-network?${params}`);
}

export async function promoteExperiment(experimentId: string) {
  return fetchJSON<{ promoted: string; message: string }>(
    `/experiments/${experimentId}/promote`,
    { method: 'POST' },
  );
}

export function downloadCSV(data: Record<string, unknown>[], filename: string) {
  if (!data.length) return;
  const headers = Object.keys(data[0]);
  const rows = data.map(row =>
    headers.map(h => {
      const val = row[h];
      const str = String(val ?? '');
      return str.includes(',') || str.includes('"') ? `"${str.replace(/"/g, '""')}"` : str;
    }).join(','),
  );
  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
