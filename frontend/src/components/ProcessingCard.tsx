const STAGES = [
  'parsing',
  'filtering',
  'graph_ingestion',
  'embedding',
  'hybrid_matching',
  'scoring',
  'completed',
];

interface ProcessingCardProps {
  resumeId: string;
  filename: string;
  stageStatuses: Map<string, { stage: string; status: string }>;
}

export default function ProcessingCard({ resumeId, filename, stageStatuses }: ProcessingCardProps) {
  return (
    <div className="bg-white rounded-lg border border-gray-200 p-4">
      <p className="text-sm font-medium text-gray-900 mb-3 truncate">{filename}</p>
      <div className="flex items-center gap-1">
        {STAGES.map((stage) => {
          const key = `${resumeId}:${stage}`;
          const ev = stageStatuses.get(key);
          const status = ev?.status ?? 'pending';

          let bgClass = 'bg-gray-200'; // pending
          if (status === 'in_progress') bgClass = 'bg-indigo-400 animate-pulse';
          else if (status === 'complete') bgClass = 'bg-green-500';
          else if (status === 'failed') bgClass = 'bg-red-500';

          return (
            <div key={stage} className="flex-1 flex flex-col items-center gap-1">
              <div className={`w-full h-2 rounded-full ${bgClass} transition-colors`} />
              <span className="text-xs text-gray-600 truncate w-full text-center">
                {stage === 'graph_ingestion' ? 'graph' : stage === 'hybrid_matching' ? 'match' : stage}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
