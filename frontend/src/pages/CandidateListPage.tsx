import { useState, useCallback, useMemo } from 'react';
import { useParams, Link } from 'react-router-dom';
import { getCandidates, deleteResume, notifyCandidate, notifyAllCandidates } from '@/services/candidateService';
import { useCachedFetch, clearCache } from '@/hooks/useApiCache';
import type { CandidateWithScores, CandidateListResponse, BulkDecision, BulkNotifyResponse } from '@/types';
import { Trash2, Loader2, RefreshCw, Mail, Send, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import { PageSpinner, Skeleton } from '@/components/ui/Spinner';
import ConfirmDialog from '@/components/ui/ConfirmDialog';
import NotifyModal from '@/components/ui/NotifyModal';
import { useToast } from '@/components/ui/Toast';

export default function CandidateListPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [sortBy, setSortBy] = useState('overall_score');
  const [minScore, setMinScore] = useState(0);
  const [threshold, setThreshold] = useState(70);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmTarget, setConfirmTarget] = useState<{ resumeId: string; name: string } | null>(null);
  const [notifyTarget, setNotifyTarget] = useState<CandidateWithScores | null>(null);
  // Manual overrides: candidate_id → 'shortlisted' | 'rejected'
  const [overrides, setOverrides] = useState<Record<string, 'shortlisted' | 'rejected'>>({});
  const [bulkSending, setBulkSending] = useState(false);
  const [bulkConfirmOpen, setBulkConfirmOpen] = useState(false);
  const [bulkResults, setBulkResults] = useState<BulkNotifyResponse | null>(null);
  const { toast } = useToast();

  const fetcher = useCallback(
    () => getCandidates(jobId!, sortBy),
    [jobId, sortBy],
  );

  const { data, loading, error, refetch } = useCachedFetch<CandidateListResponse>(
    jobId ? `candidates:${jobId}:${sortBy}` : null,
    fetcher,
  );

  const candidates: CandidateWithScores[] = data?.candidates ?? [];
  const filtered = candidates.filter((c) => c.overall_score >= minScore);

  // Compute decision for each candidate: auto from threshold, or manual override
  const getDecision = useCallback((c: CandidateWithScores): 'shortlisted' | 'rejected' => {
    if (overrides[c.id]) return overrides[c.id];
    return c.overall_score >= threshold ? 'shortlisted' : 'rejected';
  }, [overrides, threshold]);

  // Summary counts for the bulk action bar
  const bulkSummary = useMemo(() => {
    const eligible = filtered.filter(
      (c) => c.pipeline_status === 'completed' && (!c.notification_status || c.notification_status === 'not_sent'),
    );
    const shortlisted = eligible.filter((c) => getDecision(c) === 'shortlisted').length;
    const rejected = eligible.filter((c) => getDecision(c) === 'rejected').length;
    const noEmail = eligible.filter((c) => !c.email).length;
    return { eligible: eligible.length, shortlisted, rejected, noEmail };
  }, [filtered, getDecision]);

  const toggleDecision = (candidateId: string, current: 'shortlisted' | 'rejected') => {
    setOverrides((prev) => ({
      ...prev,
      [candidateId]: current === 'shortlisted' ? 'rejected' : 'shortlisted',
    }));
  };

  const handleDelete = async () => {
    if (!confirmTarget) return;
    setDeletingId(confirmTarget.resumeId);
    setConfirmTarget(null);
    try {
      await deleteResume(confirmTarget.resumeId);
      clearCache(`candidates:${jobId}`);
      toast('success', `"${confirmTarget.name}" removed successfully.`);
      refetch();
    } catch {
      toast('error', 'Failed to delete candidate. Please try again.');
    } finally {
      setDeletingId(null);
    }
  };

  const handleNotify = async (type: 'shortlisted' | 'rejected', customMessage?: string) => {
    if (!notifyTarget) return;
    try {
      const res = await notifyCandidate(notifyTarget.id, type, customMessage);
      toast('success', res.message || `Email sent to ${res.email_sent_to}`);
      clearCache(`candidates:${jobId}`);
      setNotifyTarget(null);
      refetch();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      if (detail?.includes('not configured')) {
        toast('error', 'Email service is not configured. Set RESEND_API_KEY on the server.');
      } else if (detail?.includes('no email')) {
        toast('error', 'This candidate has no email address on file.');
      } else if (detail?.includes('domain not verified')) {
        toast('error', 'Email domain not verified. Verify a domain at resend.com/domains to send to candidates.');
      } else if (detail?.includes('delivery failed') || detail?.includes('delivery forbidden')) {
        toast('error', detail || 'Email delivery failed.');
      } else {
        toast('error', detail || 'Failed to send notification email. Please try again.');
      }
      setNotifyTarget(null);
    }
  };

  const handleBulkSend = async () => {
    setBulkConfirmOpen(false);
    setBulkSending(true);
    try {
      const decisions: BulkDecision[] = filtered
        .filter(
          (c) =>
            c.pipeline_status === 'completed' &&
            (!c.notification_status || c.notification_status === 'not_sent'),
        )
        .map((c) => ({
          candidate_id: c.id,
          type: getDecision(c),
        }));

      if (decisions.length === 0) {
        toast('error', 'No eligible candidates to notify.');
        setBulkSending(false);
        return;
      }

      const res = await notifyAllCandidates(jobId!, decisions);
      setBulkResults(res);
      clearCache(`candidates:${jobId}`);
      refetch();
    } catch (err: unknown) {
      const detail = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast('error', detail || 'Bulk notification failed. Please try again.');
    } finally {
      setBulkSending(false);
    }
  };

  if (loading && !data) return <PageSpinner label="Loading candidates…" />;

  if (error && !data) {
    return (
      <div className="flex flex-col items-center justify-center py-20 gap-3">
        <p className="text-sm text-red-600">Failed to load candidates.</p>
        <button onClick={refetch} className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors">
          <RefreshCw size={14} /> Retry
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <ConfirmDialog
        open={!!confirmTarget}
        title="Delete Candidate"
        message={`Remove "${confirmTarget?.name}"? This will permanently delete the resume and all analysis data.`}
        confirmLabel="Delete"
        variant="danger"
        onConfirm={handleDelete}
        onCancel={() => setConfirmTarget(null)}
      />
      <ConfirmDialog
        open={bulkConfirmOpen}
        title="Send Emails to All Candidates"
        message={`This will send ${bulkSummary.shortlisted} shortlisted and ${bulkSummary.rejected} rejection email(s) to eligible candidates.${bulkSummary.noEmail > 0 ? ` ${bulkSummary.noEmail} candidate(s) without email will be skipped.` : ''} Proceed?`}
        confirmLabel="Send All"
        variant="primary"
        onConfirm={handleBulkSend}
        onCancel={() => setBulkConfirmOpen(false)}
      />
      <NotifyModal
        open={!!notifyTarget}
        candidateName={notifyTarget?.name || `Candidate ${notifyTarget?.id.slice(0, 8) ?? ''}`}
        candidateEmail={notifyTarget?.email ?? null}
        onSend={handleNotify}
        onClose={() => setNotifyTarget(null)}
      />

      {/* ── Bulk Results Modal ── */}
      {bulkResults && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="fixed inset-0 bg-black/40" onClick={() => setBulkResults(null)} />
          <div className="relative bg-white rounded-xl shadow-xl border border-gray-200 p-6 max-w-lg w-full max-h-[80vh] overflow-y-auto">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Bulk Email Results</h3>
            <div className="grid grid-cols-2 gap-3 mb-4">
              <div className="bg-green-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-green-700">{bulkResults.sent}</p>
                <p className="text-xs text-green-600">Sent</p>
              </div>
              <div className="bg-red-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-red-700">{bulkResults.failed}</p>
                <p className="text-xs text-red-600">Failed</p>
              </div>
              <div className="bg-yellow-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-yellow-700">{bulkResults.skipped_no_email}</p>
                <p className="text-xs text-yellow-600">No Email</p>
              </div>
              <div className="bg-gray-50 rounded-lg p-3 text-center">
                <p className="text-2xl font-bold text-gray-700">{bulkResults.skipped_already_notified}</p>
                <p className="text-xs text-gray-600">Already Notified</p>
              </div>
            </div>
            {bulkResults.results.length > 0 && (
              <div className="space-y-2 mb-4">
                {bulkResults.results.map((r) => (
                  <div
                    key={r.candidate_id}
                    className={`flex items-center gap-2 text-sm px-3 py-2 rounded-lg ${
                      r.status === 'sent'
                        ? 'bg-green-50 text-green-800'
                        : r.status === 'skipped'
                          ? 'bg-yellow-50 text-yellow-800'
                          : 'bg-red-50 text-red-800'
                    }`}
                  >
                    {r.status === 'sent' ? (
                      <CheckCircle2 size={14} />
                    ) : r.status === 'skipped' ? (
                      <AlertTriangle size={14} />
                    ) : (
                      <XCircle size={14} />
                    )}
                    <span className="font-medium">{r.name || r.candidate_id.slice(0, 8)}</span>
                    <span className="text-xs opacity-75">
                      {r.status === 'sent'
                        ? `${r.type} → ${r.email}`
                        : r.reason === 'no_email'
                          ? 'No email address'
                          : r.reason === 'already_notified'
                            ? 'Already notified'
                            : r.reason || 'Error'}
                    </span>
                  </div>
                ))}
              </div>
            )}
            <button
              onClick={() => setBulkResults(null)}
              className="w-full px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* ── Header ── */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <h2 className="text-xl font-bold text-gray-900">Candidates</h2>
        <div className="flex items-center gap-4">
          <label className="text-sm text-gray-600 flex items-center gap-2">
            Min Score:
            <input
              type="range"
              min={0}
              max={100}
              value={minScore}
              onChange={(e) => setMinScore(Number(e.target.value))}
              className="w-24"
            />
            <span className="text-sm font-medium text-gray-700 w-8">{minScore}</span>
          </label>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="text-sm text-gray-900 bg-white border border-gray-300 rounded-lg px-2 py-1.5"
          >
            <option value="overall_score">Overall</option>
            <option value="skills_score">Skills</option>
            <option value="experience_score">Experience</option>
            <option value="education_score">Education</option>
          </select>
        </div>
      </div>

      {/* ── Shortlist Threshold + Bulk Action Bar ── */}
      <div className="bg-white rounded-xl border border-gray-200 p-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-4">
            <label className="text-sm text-gray-700 font-medium flex items-center gap-2">
              Shortlist Threshold:
              <input
                type="range"
                min={0}
                max={100}
                value={threshold}
                onChange={(e) => {
                  setThreshold(Number(e.target.value));
                  setOverrides({}); // reset manual overrides when threshold changes
                }}
                className="w-32 accent-indigo-600"
              />
              <span className="text-sm font-bold text-indigo-600 w-8">{threshold}</span>
            </label>
            <div className="flex items-center gap-3 text-xs text-gray-500">
              <span className="inline-flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-green-500" />
                {bulkSummary.shortlisted} shortlisted
              </span>
              <span className="inline-flex items-center gap-1">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500" />
                {bulkSummary.rejected} rejected
              </span>
              {bulkSummary.noEmail > 0 && (
                <span className="inline-flex items-center gap-1 text-yellow-600">
                  <AlertTriangle size={12} />
                  {bulkSummary.noEmail} no email
                </span>
              )}
            </div>
          </div>
          <button
            onClick={() => setBulkConfirmOpen(true)}
            disabled={bulkSending || bulkSummary.eligible === 0}
            className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {bulkSending ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              <Send size={14} />
            )}
            Send Email to All ({bulkSummary.eligible})
          </button>
        </div>
      </div>

      {/* ── Table ── */}
      <div className="bg-white rounded-xl border border-gray-200 overflow-x-auto">
        {loading && !data ? (
          <div className="p-6 space-y-3">
            {[1, 2, 3].map((i) => <Skeleton key={i} className="h-12 w-full" />)}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-6 text-center text-sm text-gray-500">
            No candidates found.
          </div>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 bg-gray-50">
                <th className="text-left px-4 py-3 font-medium text-gray-600">#</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">Candidate</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 cursor-pointer" onClick={() => setSortBy('overall_score')}>
                  Overall
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 cursor-pointer" onClick={() => setSortBy('skills_score')}>
                  Skills
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 cursor-pointer" onClick={() => setSortBy('experience_score')}>
                  Exp
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-600 cursor-pointer" onClick={() => setSortBy('education_score')}>
                  Edu
                </th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Status</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Decision</th>
                <th className="text-center px-4 py-3 font-medium text-gray-600">Notified</th>
                <th className="text-right px-4 py-3 font-medium text-gray-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filtered.map((c, i) => {
                const decision = getDecision(c);
                const isCompleted = c.pipeline_status === 'completed';
                const alreadyNotified = c.notification_status && c.notification_status !== 'not_sent';
                return (
                  <tr key={c.id} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-gray-500">{i + 1}</td>
                    <td className="px-4 py-3">
                      <div>
                        <span className="font-medium text-gray-900">
                          {c.name || `Candidate ${c.id.slice(0, 8)}`}
                        </span>
                        {c.email && (
                          <p className="text-xs text-gray-400 mt-0.5">{c.email}</p>
                        )}
                        {!c.email && isCompleted && (
                          <p className="text-xs text-yellow-500 mt-0.5">No email</p>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <ScoreBadge score={c.overall_score} />
                    </td>
                    <td className="px-4 py-3 text-center text-gray-600">{c.skills_score ?? '—'}</td>
                    <td className="px-4 py-3 text-center text-gray-600">{c.experience_score ?? '—'}</td>
                    <td className="px-4 py-3 text-center text-gray-600">{c.education_score ?? '—'}</td>
                    <td className="px-4 py-3 text-center">
                      <span
                        className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          c.pipeline_status === 'completed'
                            ? 'bg-green-100 text-green-700'
                            : c.pipeline_status === 'failed'
                              ? 'bg-red-100 text-red-700'
                              : 'bg-yellow-100 text-yellow-700'
                        }`}
                      >
                        {c.pipeline_status}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {isCompleted && !alreadyNotified ? (
                        <button
                          onClick={() => toggleDecision(c.id, decision)}
                          className={`text-xs font-medium px-2.5 py-1 rounded-full border transition-colors ${
                            decision === 'shortlisted'
                              ? 'bg-green-50 border-green-300 text-green-700 hover:bg-green-100'
                              : 'bg-red-50 border-red-300 text-red-700 hover:bg-red-100'
                          }`}
                          title="Click to toggle"
                        >
                          {decision === 'shortlisted' ? '✓ Shortlisted' : '✗ Rejected'}
                        </button>
                      ) : !isCompleted ? (
                        <span className="text-xs text-gray-400">—</span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <NotificationBadge status={c.notification_status} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Link
                          to={`/app/candidates/${jobId}/${c.resume_id}`}
                          className="text-sm text-indigo-600 hover:text-indigo-700 font-medium"
                        >
                          Detail
                        </Link>
                        <button
                          onClick={() => setNotifyTarget(c)}
                          className="text-gray-400 hover:text-indigo-600 transition-colors"
                          title="Send notification email"
                        >
                          <Mail size={15} />
                        </button>
                        <button
                          onClick={() => setConfirmTarget({ resumeId: c.resume_id, name: c.name || `Candidate ${c.id.slice(0, 8)}` })}
                          disabled={deletingId === c.resume_id}
                          className="text-gray-400 hover:text-red-600 transition-colors disabled:opacity-50"
                          title="Delete"
                        >
                          {deletingId === c.resume_id ? (
                            <Loader2 size={15} className="animate-spin" />
                          ) : (
                            <Trash2 size={15} />
                          )}
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

function ScoreBadge({ score }: { score: number }) {
  let color = 'bg-red-100 text-red-700';
  if (score >= 70) color = 'bg-green-100 text-green-700';
  else if (score >= 40) color = 'bg-yellow-100 text-yellow-700';

  return (
    <span className={`inline-block text-xs font-bold px-2 py-0.5 rounded-full ${color}`}>
      {score}
    </span>
  );
}

function NotificationBadge({ status }: { status: string | null }) {
  if (!status || status === 'not_sent') {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const color =
    status === 'shortlisted'
      ? 'bg-green-100 text-green-700'
      : 'bg-red-100 text-red-700';
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>
      {status}
    </span>
  );
}
