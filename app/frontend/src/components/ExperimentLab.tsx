import { useState, useEffect, useCallback } from 'react';
import {
  FlaskConical, Play, Database, CheckCircle2, ArrowUpCircle,
  Loader2, RefreshCw, Trash2,
} from 'lucide-react';
import type {
  ExperimentResult, FalsePositiveCandidate, LabelCorrection,
  ModelMetrics, FeatureImportance, ConfusionMatrix,
} from '../types';
import {
  getOriginalModelMetrics, getFalsePositives, getLabelCorrections,
  applyLabelCorrection, removeLabelCorrection, generateAdditionalData,
  runExperiment, promoteExperiment, getExperimentStatus, getExperimentDetail,
} from '../api';

interface Props {
  result: ExperimentResult | null;
  onResult: (result: ExperimentResult) => void;
}

// ---------------------------------------------------------------------------
// Metric display helpers
// ---------------------------------------------------------------------------

function pct(v: number | undefined): string {
  if (v == null) return '--';
  return `${(v * 100).toFixed(1)}%`;
}

function delta(v: number | undefined): string {
  if (v == null) return '';
  const sign = v > 0 ? '+' : '';
  return `${sign}${(v * 100).toFixed(2)}pp`;
}

function deltaColor(v: number | undefined): string {
  if (v == null) return 'text-gray-500';
  if (v > 0.001) return 'text-fraud-green';
  if (v < -0.001) return 'text-fraud-red';
  return 'text-gray-400';
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function MetricCard({ label, value, deltaVal }: { label: string; value: string; deltaVal?: number }) {
  return (
    <div className="bg-surface-2 rounded-lg border border-surface-3 px-3 py-2">
      <div className="text-[10px] uppercase tracking-wide text-gray-500">{label}</div>
      <div className="font-mono text-lg text-gray-100">{value}</div>
      {deltaVal != null && (
        <div className={`text-xs font-mono ${deltaColor(deltaVal)}`}>{delta(deltaVal)}</div>
      )}
    </div>
  );
}

function ConfusionMatrixView({ cm, label }: { cm?: ConfusionMatrix; label: string }) {
  if (!cm) return null;
  const total = cm.tn + cm.fp + cm.fn + cm.tp;
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1">{label}</div>
      <div className="grid grid-cols-2 gap-1 text-xs font-mono">
        <div className="bg-fraud-green/10 border border-fraud-green/30 rounded px-2 py-1 text-center">
          <div className="text-gray-500">TN</div>
          <div className="text-fraud-green">{cm.tn.toLocaleString()}</div>
        </div>
        <div className="bg-fraud-red/10 border border-fraud-red/30 rounded px-2 py-1 text-center">
          <div className="text-gray-500">FP</div>
          <div className="text-fraud-red">{cm.fp.toLocaleString()}</div>
        </div>
        <div className="bg-fraud-amber/10 border border-fraud-amber/30 rounded px-2 py-1 text-center">
          <div className="text-gray-500">FN</div>
          <div className="text-fraud-amber">{cm.fn.toLocaleString()}</div>
        </div>
        <div className="bg-fraud-green/10 border border-fraud-green/30 rounded px-2 py-1 text-center">
          <div className="text-gray-500">TP</div>
          <div className="text-fraud-green">{cm.tp.toLocaleString()}</div>
        </div>
      </div>
      <div className="text-[10px] text-gray-600 mt-1 text-center">{total.toLocaleString()} test samples</div>
    </div>
  );
}

function FeatureList({ features, label }: { features: FeatureImportance[]; label: string }) {
  if (!features?.length) return null;
  const maxVal = features[0]?.mean_abs_shap || 1;
  return (
    <div>
      <div className="text-[10px] uppercase tracking-wide text-gray-500 mb-1.5">{label}</div>
      <div className="space-y-1">
        {features.slice(0, 8).map((f) => (
          <div key={f.feature} className="flex items-center gap-2">
            <span className="text-[10px] text-gray-400 w-36 truncate" title={f.feature}>{f.feature}</span>
            <div className="flex-1 h-2 bg-surface-3 rounded-full overflow-hidden">
              <div
                className="h-full bg-accent/60 rounded-full"
                style={{ width: `${(f.mean_abs_shap / maxVal) * 100}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-gray-500 w-10 text-right">
              {f.mean_abs_shap.toFixed(3)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ExperimentLab({ result, onResult }: Props) {
  // -- State for the 3-step workflow --
  const [step, setStep] = useState<'review' | 'prepare' | 'results'>(result ? 'results' : 'review');

  // Step 1: Review data
  const [candidates, setCandidates] = useState<FalsePositiveCandidate[]>([]);
  const [corrections, setCorrections] = useState<LabelCorrection[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [originalMetrics, setOriginalMetrics] = useState<{
    metrics: ModelMetrics;
    top_features: FeatureImportance[];
    gpu_info: string;
  } | null>(null);

  // Step 2: Prepare & train
  const [generating, setGenerating] = useState(false);
  const [generatedInfo, setGeneratedInfo] = useState<{
    generated: number; fraud: number; legitimate: number; fraud_rate: number;
  } | null>(null);
  const [genCount, setGenCount] = useState(10000);
  const [useCorrections, setUseCorrections] = useState(true);
  const [useGenerated, setUseGenerated] = useState(true);
  const [training, setTraining] = useState(false);
  const [trainingPhase, setTrainingPhase] = useState<string | null>(null);
  const [trainingError, setTrainingError] = useState<string | null>(null);

  // Load original model metrics + corrections on mount
  useEffect(() => {
    getOriginalModelMetrics()
      .then((d) => setOriginalMetrics({ metrics: d.metrics, top_features: d.top_features, gpu_info: d.gpu_info }))
      .catch(() => {});
    getLabelCorrections()
      .then((d) => setCorrections(d.corrections))
      .catch(() => {});
  }, []);

  const loadCandidates = useCallback(() => {
    setLoadingCandidates(true);
    getFalsePositives(50)
      .then((d) => setCandidates(d.candidates))
      .catch(() => {})
      .finally(() => setLoadingCandidates(false));
  }, []);

  useEffect(() => { loadCandidates(); }, [loadCandidates]);

  const handleCorrect = async (txId: number, label: number) => {
    await applyLabelCorrection(txId, label);
    // Refresh corrections list
    const c = await getLabelCorrections();
    setCorrections(c.corrections);
    // Remove from candidates
    setCandidates((prev) => prev.filter((c) => c.transaction_id !== txId));
  };

  const handleUndoCorrection = async (txId: number) => {
    await removeLabelCorrection(txId);
    const c = await getLabelCorrections();
    setCorrections(c.corrections);
  };

  const handleGenerate = async () => {
    setGenerating(true);
    try {
      const info = await generateAdditionalData(genCount);
      setGeneratedInfo(info);
    } catch {
      // ignore
    } finally {
      setGenerating(false);
    }
  };

  const handleTrain = async () => {
    setTraining(true);
    setTrainingError(null);
    setTrainingPhase('queued');
    try {
      const ack = await runExperiment({
        use_corrections: useCorrections,
        use_generated_data: useGenerated,
        description: `Retrained with ${corrections.length} corrections${useGenerated && generatedInfo ? `, ${generatedInfo.generated} generated rows` : ''}`,
      });
      if (ack.status !== 'started' || !ack.experiment_id) {
        setTrainingError(ack.message || 'Could not start experiment');
        setTraining(false);
        setTrainingPhase(null);
        return;
      }

      // Poll the status endpoint until the run finishes or errors out.
      const targetId = ack.experiment_id;
      let tries = 0;
      const maxTries = 600; // ~10 min at 1s interval
      while (tries++ < maxTries) {
        await new Promise(r => setTimeout(r, 1000));
        const st = await getExperimentStatus();
        setTrainingPhase(st.phase || st.status);
        if (st.id !== targetId) continue;
        if (st.status === 'completed' && st.result) {
          onResult(st.result);
          setStep('results');
          break;
        }
        if (st.status === 'failed') {
          setTrainingError(st.error || 'Experiment failed');
          break;
        }
      }
      // Fallback: fetch detail in case status rotated before we polled
      if (tries >= maxTries) {
        const detail = await getExperimentDetail(targetId).catch(() => null);
        if (detail?.result) {
          onResult(detail.result);
          setStep('results');
        } else {
          setTrainingError('Timed out waiting for experiment to finish');
        }
      }
    } catch (err) {
      setTrainingError(err instanceof Error ? err.message : 'Training failed');
    } finally {
      setTraining(false);
      setTrainingPhase(null);
    }
  };

  const handlePromote = async () => {
    if (!result) return;
    await promoteExperiment(result.experiment_id);
    // Refresh original metrics
    const m = await getOriginalModelMetrics();
    setOriginalMetrics({ metrics: m.metrics, top_features: m.top_features, gpu_info: m.gpu_info });
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center gap-2">
        <FlaskConical className="w-5 h-5 text-accent" />
        <h2 className="text-sm font-semibold text-gray-100">Model Retraining Lab</h2>
      </div>

      {/* Step tabs */}
      <div className="flex gap-1 bg-surface-2 rounded-lg p-1">
        {(['review', 'prepare', 'results'] as const).map((s, i) => (
          <button
            key={s}
            onClick={() => setStep(s)}
            className={`flex-1 px-3 py-1.5 text-xs font-medium rounded-md transition-colors
              ${step === s ? 'bg-accent/20 text-accent' : 'text-gray-400 hover:text-gray-200 hover:bg-surface-3'}
              ${s === 'results' && !result ? 'opacity-50 pointer-events-none' : ''}`}
          >
            <span className="mr-1.5">{i + 1}.</span>
            {s === 'review' ? 'Review Data' : s === 'prepare' ? 'Prepare & Train' : 'Compare Results'}
          </button>
        ))}
      </div>

      {/* ---- Step 1: Review Data ---- */}
      {step === 'review' && (
        <div className="space-y-4">
          {/* Original model summary */}
          {originalMetrics && (
            <div className="bg-surface-2 rounded-lg border border-surface-3 p-3">
              <div className="text-xs font-medium text-gray-300 mb-2">Current Production Model</div>
              <div className="grid grid-cols-3 gap-2">
                <MetricCard label="ROC AUC" value={pct(originalMetrics.metrics.roc_auc)} />
                <MetricCard label="Avg Precision" value={pct(originalMetrics.metrics.avg_precision)} />
                <MetricCard label="Threshold" value={originalMetrics.metrics.optimal_threshold?.toFixed(3) ?? '--'} />
              </div>
              <div className="text-[10px] text-gray-600 mt-2">{originalMetrics.gpu_info}</div>
            </div>
          )}

          {/* Corrections summary */}
          {corrections.length > 0 && (
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
              <div className="flex items-center justify-between">
                <div className="text-xs text-blue-400 font-medium">
                  {corrections.length} label correction{corrections.length !== 1 ? 's' : ''} pending
                </div>
                <button onClick={() => setStep('prepare')} className="text-[10px] text-blue-400 hover:text-blue-300">
                  Go to training &rarr;
                </button>
              </div>
              <div className="mt-2 space-y-1 max-h-24 overflow-y-auto">
                {corrections.slice(0, 5).map((c) => (
                  <div key={c.transaction_id} className="flex items-center justify-between text-[10px]">
                    <span className="text-gray-400">
                      TX #{c.transaction_id} &middot; ${c.amount?.toFixed(2)} &middot; {c.merchant_name}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className="text-fraud-red line-through">fraud</span>
                      <span className="text-fraud-green">legit</span>
                      <button
                        onClick={() => handleUndoCorrection(c.transaction_id)}
                        className="text-gray-500 hover:text-fraud-red"
                        title="Undo correction"
                      >
                        <Trash2 className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                ))}
                {corrections.length > 5 && (
                  <div className="text-[10px] text-gray-500">+{corrections.length - 5} more</div>
                )}
              </div>
            </div>
          )}

          {/* False positive candidates */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <div className="text-xs font-medium text-gray-300">
                Potential Mislabeled Transactions
              </div>
              <button
                onClick={loadCandidates}
                disabled={loadingCandidates}
                className="text-[10px] text-gray-400 hover:text-accent flex items-center gap-1"
              >
                <RefreshCw className={`w-3 h-3 ${loadingCandidates ? 'animate-spin' : ''}`} />
                Refresh
              </button>
            </div>
            <p className="text-[10px] text-gray-500 mb-2">
              These transactions are labeled as fraud but the model gives them a low fraud score,
              suggesting they may be mislabeled. Click to mark as legitimate.
            </p>

            {loadingCandidates ? (
              <div className="flex items-center justify-center py-8 text-gray-500">
                <Loader2 className="w-5 h-5 animate-spin" />
              </div>
            ) : (
              <div className="space-y-1 max-h-[400px] overflow-y-auto">
                {candidates.map((c) => (
                  <div
                    key={c.transaction_id}
                    className="flex items-center justify-between bg-surface-2 rounded-md px-3 py-2 border border-surface-3 hover:border-surface-4"
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-xs">
                        <span className="text-gray-300 font-mono">#{c.transaction_id}</span>
                        <span className="text-gray-500">User {c.user_id}</span>
                        <span className="text-gray-500 truncate">{c.merchant_name}</span>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] mt-0.5">
                        <span className="text-gray-400 font-mono">${c.amount.toFixed(2)}</span>
                        <span className="text-gray-500">{c.hour}:00</span>
                        <span className={`font-medium ${
                          c.confidence === 'LOW' ? 'text-fraud-green' :
                          c.confidence === 'MEDIUM' ? 'text-fraud-amber' : 'text-fraud-red'
                        }`}>
                          Score: {c.fraud_score} ({c.confidence})
                        </span>
                      </div>
                    </div>
                    <button
                      onClick={() => handleCorrect(c.transaction_id, 0)}
                      className="flex items-center gap-1 px-2 py-1 text-[10px] font-medium
                                 text-fraud-green bg-fraud-green/10 border border-fraud-green/30
                                 rounded hover:bg-fraud-green/20 shrink-0 ml-2"
                      title="Mark as legitimate (not fraud)"
                    >
                      <CheckCircle2 className="w-3 h-3" />
                      Not Fraud
                    </button>
                  </div>
                ))}
                {candidates.length === 0 && (
                  <div className="text-center py-6 text-gray-500 text-xs">
                    No candidates found. The model agrees with all fraud labels.
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ---- Step 2: Prepare & Train ---- */}
      {step === 'prepare' && (
        <div className="space-y-4">
          {/* Data corrections toggle */}
          <div className="bg-surface-2 rounded-lg border border-surface-3 p-3">
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <div className="text-xs font-medium text-gray-300">Use Label Corrections</div>
                <div className="text-[10px] text-gray-500">
                  {corrections.length} correction{corrections.length !== 1 ? 's' : ''} will be applied to training data
                </div>
              </div>
              <input
                type="checkbox"
                checked={useCorrections}
                onChange={(e) => setUseCorrections(e.target.checked)}
                className="w-4 h-4 rounded accent-accent"
              />
            </label>
          </div>

          {/* Generate data section */}
          <div className="bg-surface-2 rounded-lg border border-surface-3 p-3 space-y-3">
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <div className="text-xs font-medium text-gray-300">Use Generated Data</div>
                <div className="text-[10px] text-gray-500">
                  Add synthetic transactions to expand the training set
                </div>
              </div>
              <input
                type="checkbox"
                checked={useGenerated}
                onChange={(e) => setUseGenerated(e.target.checked)}
                className="w-4 h-4 rounded accent-accent"
              />
            </label>

            {useGenerated && (
              <div className="space-y-2 pt-1 border-t border-surface-3">
                <div className="flex items-center gap-2">
                  <label className="text-[10px] text-gray-500 shrink-0">Transactions:</label>
                  <input
                    type="range"
                    min={1000}
                    max={500000}
                    step={5000}
                    value={genCount}
                    onChange={(e) => setGenCount(Number(e.target.value))}
                    className="flex-1 accent-accent"
                  />
                  <span className="text-xs font-mono text-gray-300 w-16 text-right">
                    {genCount.toLocaleString()}
                  </span>
                </div>
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium
                             bg-accent/10 border border-accent/30 text-accent rounded-md
                             hover:bg-accent/20 disabled:opacity-50"
                >
                  {generating ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Database className="w-3.5 h-3.5" />}
                  {generating ? 'Generating...' : 'Generate Data'}
                </button>
                {generatedInfo && (
                  <div className="text-[10px] text-gray-400 bg-surface-3 rounded px-2 py-1.5">
                    Generated {generatedInfo.generated.toLocaleString()} transactions
                    ({generatedInfo.fraud} fraud, {generatedInfo.legitimate} legitimate,
                    {generatedInfo.fraud_rate}% fraud rate)
                  </div>
                )}
              </div>
            )}
          </div>

          {/* Train button */}
          <button
            onClick={handleTrain}
            disabled={training}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 text-sm font-semibold
                       bg-accent text-white rounded-lg hover:bg-accent/90
                       disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {training ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin" />
                {trainingPhase
                  ? `Training — ${trainingPhase.replace(/_/g, ' ')}...`
                  : 'Training with GPU-Accelerated XGBoost...'}
              </>
            ) : (
              <>
                <Play className="w-4 h-4" />
                Retrain Model
              </>
            )}
          </button>

          {training && (
            <div className="text-center text-[10px] text-gray-500">
              Running in a background thread — the UI stays responsive. Typical runs finish in 10-60 seconds.
            </div>
          )}

          {trainingError && (
            <div className="text-center text-xs text-fraud-red bg-fraud-red/10 border border-fraud-red/30 rounded-md px-3 py-2">
              {trainingError}
            </div>
          )}
        </div>
      )}

      {/* ---- Step 3: Results ---- */}
      {step === 'results' && result && (
        <div className="space-y-4">
          {/* Timing & data summary */}
          <div className="bg-surface-2 rounded-lg border border-surface-3 p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-medium text-gray-300">Experiment {result.experiment_id}</span>
              <span className="text-[10px] text-gray-500">{result.gpu_info}</span>
            </div>
            <div className="grid grid-cols-4 gap-2 text-center text-[10px]">
              <div className="bg-surface-3 rounded px-2 py-1">
                <div className="text-gray-500">Train Time</div>
                <div className="text-gray-200 font-mono">{result.timing.training_s}s</div>
              </div>
              <div className="bg-surface-3 rounded px-2 py-1">
                <div className="text-gray-500">Total Time</div>
                <div className="text-gray-200 font-mono">{result.timing.total_s}s</div>
              </div>
              <div className="bg-surface-3 rounded px-2 py-1">
                <div className="text-gray-500">Corrections</div>
                <div className="text-gray-200 font-mono">{result.data_summary.corrections_applied}</div>
              </div>
              <div className="bg-surface-3 rounded px-2 py-1">
                <div className="text-gray-500">+Generated</div>
                <div className="text-gray-200 font-mono">{result.data_summary.generated_data_added.toLocaleString()}</div>
              </div>
            </div>
          </div>

          {/* Side-by-side metrics */}
          <div className="grid grid-cols-2 gap-3">
            {/* Original */}
            <div className="bg-surface-2 rounded-lg border border-surface-3 p-3">
              <div className="text-xs font-medium text-gray-400 mb-2">Original Model</div>
              <div className="space-y-2">
                <MetricCard label="ROC AUC" value={pct(result.original_model.metrics.roc_auc)} />
                <MetricCard label="Precision" value={pct(result.original_model.metrics.precision)} />
                <MetricCard label="Recall" value={pct(result.original_model.metrics.recall)} />
                <MetricCard label="F1 Score" value={pct(result.original_model.metrics.f1)} />
              </div>
            </div>

            {/* New */}
            <div className="bg-surface-2 rounded-lg border border-accent/30 p-3">
              <div className="text-xs font-medium text-accent mb-2">New Model</div>
              <div className="space-y-2">
                <MetricCard
                  label="ROC AUC"
                  value={pct(result.new_model.metrics.roc_auc)}
                  deltaVal={result.deltas.roc_auc}
                />
                <MetricCard
                  label="Precision"
                  value={pct(result.new_model.metrics.precision)}
                  deltaVal={result.deltas.precision}
                />
                <MetricCard
                  label="Recall"
                  value={pct(result.new_model.metrics.recall)}
                  deltaVal={result.deltas.recall}
                />
                <MetricCard
                  label="F1 Score"
                  value={pct(result.new_model.metrics.f1)}
                  deltaVal={result.deltas.f1}
                />
              </div>
            </div>
          </div>

          {/* Confusion matrices */}
          <div className="grid grid-cols-2 gap-3">
            <ConfusionMatrixView cm={result.original_model.metrics.confusion_matrix} label="Original" />
            <ConfusionMatrixView cm={result.new_model.metrics.confusion_matrix} label="New Model" />
          </div>

          {/* Feature importance comparison */}
          <div className="grid grid-cols-2 gap-3">
            <FeatureList features={result.original_model.top_features} label="Original Top Features" />
            <FeatureList features={result.new_model.top_features} label="New Model Top Features" />
          </div>

          {/* Promote button */}
          <button
            onClick={handlePromote}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 text-xs font-semibold
                       bg-fraud-green/10 border border-fraud-green/30 text-fraud-green rounded-lg
                       hover:bg-fraud-green/20"
          >
            <ArrowUpCircle className="w-4 h-4" />
            Promote New Model to Production
          </button>
        </div>
      )}

      {step === 'results' && !result && (
        <div className="flex flex-col items-center justify-center py-12 text-gray-500 text-xs">
          <FlaskConical className="w-10 h-10 mb-3 opacity-20" />
          <p>No experiment results yet.</p>
          <p className="mt-1">Review data and run an experiment to see results here.</p>
        </div>
      )}
    </div>
  );
}
