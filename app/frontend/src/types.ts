export interface Transaction {
  transaction_id: number;
  user_id: number;
  card_id: string;
  merchant_id?: number;
  merchant_name: string;
  merchant_city: string;
  merchant_state: string;
  merchant_country?: string;
  mcc: number;
  amount: number;
  hour: number;
  minute: number;
  day: number;
  month: number;
  year: number;
  use_chip: string;
  errors: string;
  is_fraud: number;
}

export interface ToolCall {
  tool: string;
  args: Record<string, unknown>;
  result_summary: string;
}

export interface GuardVerdict {
  safe: boolean;
  screened: boolean;
  categories: string[];
  category_names: string | null;
  error: string | null;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
  tool_calls?: ToolCall[];
  timestamp?: number;
  guard?: GuardVerdict | null;
}

export interface ShapFeature {
  feature: string;
  value: number;
  shap_value: number;
  direction: string;
}

export interface ScoreResult {
  fraud_score: number;
  is_fraud: boolean;
  risk_level: 'HIGH' | 'MEDIUM' | 'LOW';
  actual_fraud?: boolean;
  explanation?: {
    base_value: number;
    top_features: ShapFeature[];
    shap_values_all: Record<string, number>;
  };
}

export interface ExplanationResult {
  transaction_id: number;
  fraud_score: number;
  risk_level: string;
  actual_fraud: boolean;
  narrative: string;
  top_features: ShapFeature[];
  base_value: number;
  transaction_summary: {
    amount: number;
    merchant: string;
    country?: string;
    state: string;
    hour: number;
    use_chip: string;
  };
}

export interface DashboardKPIs {
  total_transactions: number;
  total_fraud: number;
  fraud_rate_pct: number;
  total_fraud_amount: number;
  avg_fraud_amount: number;
  total_amount: number;
  unique_users: number;
  unique_merchants: number;
}

export interface ComparisonEntry {
  previous: number;
  change_pct: number | null;
}

export interface MonthlyTrend {
  year: number;
  month: number;
  total: number;
  fraud_count: number;
  fraud_rate_pct: number;
  fraud_amount: number;
}

export interface DashboardData {
  kpis: DashboardKPIs;
  time_period: string;
  date_range?: { start: string; end: string };
  comparison?: Record<string, ComparisonEntry>;
  comparison_period?: { start: string; end: string };
  monthly_trend?: MonthlyTrend[];
  top_fraud_countries?: { country: string; fraud_count: number; fraud_rate_pct: number }[];
  top_fraud_states?: { state: string; fraud_count: number; fraud_rate_pct: number }[];
  hourly_pattern?: { hour: number; fraud_count: number; fraud_rate_pct: number }[];
  top_fraud_mccs?: { mcc: number; fraud_count: number; fraud_rate_pct: number }[];
  top_fraud_merchants?: { merchant_name: string; fraud_count: number; fraud_rate_pct: number; fraud_amount: number }[];
  top_fraud_users?: { user_id: number; fraud_count: number; fraud_rate_pct: number; fraud_amount: number }[];
  by_country?: Record<string, unknown>[];
  by_state?: Record<string, unknown>[];
  by_mcc?: Record<string, unknown>[];
  by_hour?: Record<string, unknown>[];
  by_merchant?: Record<string, unknown>[];
  by_user?: Record<string, unknown>[];
}

export interface ThresholdPoint {
  threshold: number;
  precision: number;
  recall: number;
  f1: number;
  tp: number;
  fp: number;
  tn: number;
  fn: number;
  flagged: number;
  missed: number;
  total: number;
}

export interface ScoreDistribution {
  bin: string;
  bin_start: number;
  fraud: number;
  legitimate: number;
}

export interface ThresholdAnalysisData {
  curve: ThresholdPoint[];
  distribution: ScoreDistribution[];
  sample_size: number;
  fraud_count: number;
  legit_count: number;
  current_threshold: number;
}

export interface DateRange {
  min_date: string | null;
  max_date: string | null;
}

export interface Alert {
  type: string;
  severity: 'HIGH' | 'MEDIUM' | 'LOW';
  description: string;
  transaction_id?: number;
  transaction_ids?: number[];
  amount?: number;
  total_amount?: number;
  is_fraud?: boolean;
}

export interface AlertsResult {
  entity: string;
  summary: { high: number; medium: number; total_transactions_analyzed: number };
  alerts: Alert[];
}

export interface TokenUsageTotals {
  input: number;
  output: number;
  total: number;
}

export interface ProviderModelCost {
  label: string;
  input_per_mtok_usd: number;
  output_per_mtok_usd: number;
  cost_usd: number;
}

export interface ProviderCostEstimate {
  default_model: string;
  default_label: string;
  default_cost_usd: number;
  models: Record<string, ProviderModelCost>;
}

export interface PricingSource {
  source: 'litellm' | 'builtin' | 'fallback' | string;
  source_url: string | null;
  fetched_at: number;
  stale?: boolean;
  error?: string | null;
}

export interface OnPremConfigSummary {
  gpu_label: string;
  gpu_preset: string;
  num_gpus: number;
  pue: number;
  electricity_rate_kwh: number;
  gpu_utilization_pct: number;
  amortization_years: number;
  tokens_per_second: number;
}

export interface OnPremCostEstimate {
  enabled: boolean;
  cost_usd?: number;
  energy_cost_usd?: number;
  hardware_cost_usd?: number;
  maintenance_cost_usd?: number;
  energy_kwh?: number;
  total_watts?: number;
  generation_seconds?: number;
  config_summary?: OnPremConfigSummary;
}

export interface GpuPreset {
  label: string;
  tdp_watts: number;
  cost_usd: number;
  memory_gb: number;
  default_tok_s: number;
}

export interface OnPremConfig {
  enabled: boolean;
  gpu_preset: string;
  num_gpus: number;
  server_power_watts: number;
  pue: number;
  electricity_rate_kwh: number;
  gpu_utilization_pct: number;
  amortization_years: number;
  maintenance_pct: number;
  server_base_cost_usd: number;
  tokens_per_second: number | null;
}

export interface CostEstimate {
  tokens: TokenUsageTotals;
  on_prem?: OnPremCostEstimate;
  providers: {
    anthropic: ProviderCostEstimate;
    openai: ProviderCostEstimate;
  };
  pricing_source?: PricingSource;
}

export interface ChatUsage {
  turn: CostEstimate;
  session: CostEstimate;
}

// Experiment / Model Comparison types

export interface ConfusionMatrix {
  tn: number;
  fp: number;
  fn: number;
  tp: number;
}

export interface ModelMetrics {
  roc_auc: number;
  avg_precision: number;
  precision?: number;
  recall?: number;
  f1?: number;
  optimal_threshold?: number;
  confusion_matrix?: ConfusionMatrix;
}

export interface FeatureImportance {
  feature: string;
  mean_abs_shap: number;
}

export interface ExperimentDataSummary {
  train_rows: number;
  val_rows: number;
  test_rows: number;
  corrections_applied: number;
  generated_data_added: number;
  features: number;
}

export interface ExperimentTiming {
  data_load_s: number;
  corrections_s: number;
  merge_s: number;
  training_s: number;
  evaluation_s: number;
  total_s: number;
}

export interface ExperimentResult {
  experiment_id: string;
  status: string;
  description: string;
  gpu_info: string;
  data_summary: ExperimentDataSummary;
  timing: ExperimentTiming;
  original_model: {
    metrics: ModelMetrics;
    top_features: FeatureImportance[];
  };
  new_model: {
    metrics: ModelMetrics;
    top_features: FeatureImportance[];
    model_path: string;
  };
  deltas: Record<string, number>;
}

export interface LabelCorrection {
  transaction_id: number;
  original_label: number;
  corrected_label: number;
  corrected_at: string;
  user_id: number;
  merchant_name: string;
  amount: number;
  hour: number;
  is_fraud: number;
}

export interface FalsePositiveCandidate {
  transaction_id: number;
  user_id: number;
  merchant_name: string;
  amount: number;
  hour: number;
  is_fraud: number;
  fraud_score: number;
  confidence: string;
}

export interface FraudNetworkSampleTransaction {
  transaction_id: number;
  amount: number;
  date: string;
}

export interface FraudNetworkCounterparty {
  // Counterparty is either a user (user_id) or a merchant (merchant_name)
  user_id?: number;
  merchant_name?: string;
  merchant_state?: string;
  merchant_country?: string;
  shared_transactions: number;
  shared_fraud: number;
  shared_fraud_amount: number;
  shared_amount: number;
  last_shared: number | null;
  // Overall footprint of the counterparty (not just shared with the seed):
  user_total_transactions?: number;
  user_total_fraud?: number;
  user_unique_merchants?: number;
  merchant_total_transactions?: number;
  merchant_total_fraud?: number;
  merchant_unique_users?: number;
  sample_fraud_transactions?: FraudNetworkSampleTransaction[];
}

export interface FraudNetworkSeed {
  type: 'merchant' | 'user';
  merchant_name?: string;
  user_id?: number;
  total_transactions: number;
  fraud_transactions: number;
  fraud_amount: number;
  unique_users?: number;
  unique_merchants?: number;
  first_seen: number | null;
  last_seen: number | null;
}

export interface FraudNetworkSummary {
  counterparties_returned: number;
  fraud_heavy_counterparties: number;
  total_shared_fraud_transactions: number;
  total_shared_fraud_amount: number;
  seed_role: 'merchant' | 'user';
}

export interface FraudNetworkTrace {
  direction: 'merchant_to_users' | 'user_to_merchants';
  seed: FraudNetworkSeed;
  counterparties: FraudNetworkCounterparty[];
  summary: FraudNetworkSummary;
  fraud_only: boolean;
  error?: string;
}

export interface MerchantInvestigationKpis {
  total_transactions: number;
  fraud_transactions: number;
  fraud_rate_pct: number;
  fraud_amount: number;
  total_amount: number;
  unique_users: number;
  fraud_users: number;
  first_seen: number | null;
  last_seen: number | null;
}

export interface MerchantGeoRow {
  merchant_state: string | null;
  merchant_country?: string | null;
  total: number;
  fraud_count: number;
  fraud_amount: number;
}

export interface MerchantTimePoint {
  year: number;
  month: number;
  total: number;
  fraud_count: number;
  fraud_amount: number;
}

export interface MerchantInvestigation {
  merchant_name: string;
  kpis: MerchantInvestigationKpis;
  geographic_spread: MerchantGeoRow[];
  time_series: MerchantTimePoint[];
  trace: FraudNetworkTrace;
  patterns: AlertsResult;
  top_fraud_transactions: Transaction[];
  top_fraud_count: number;
  error?: string;
}

export type RightPanelView =
  | { type: 'dashboard'; data: DashboardData }
  | { type: 'transactions'; data: Transaction[] }
  | { type: 'explanation'; data: ExplanationResult }
  | { type: 'alerts'; data: AlertsResult }
  | { type: 'threshold'; data: ThresholdAnalysisData }
  | { type: 'experiment'; data: ExperimentResult | null }
  | { type: 'trace'; data: FraudNetworkTrace }
  | { type: 'investigation'; data: MerchantInvestigation }
  | { type: 'pipeline' }
  | { type: 'monitor' }
  | null;
