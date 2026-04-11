import { CheckCircle, AlertTriangle } from 'lucide-react';

interface ScoreCardProps {
  items: string[];
  type: 'strength' | 'gap';
}

export default function ScoreCard({ items, type }: ScoreCardProps) {
  if (items.length === 0) return null;

  const isStrength = type === 'strength';
  const Icon = isStrength ? CheckCircle : AlertTriangle;

  return (
    <div
      className={`rounded-lg border p-4 ${
        isStrength
          ? 'bg-green-50 border-green-200'
          : 'bg-red-50 border-red-200'
      }`}
    >
      <h4
        className={`text-sm font-semibold mb-2 flex items-center gap-2 ${
          isStrength ? 'text-green-700' : 'text-red-700'
        }`}
      >
        <Icon size={16} />
        {isStrength ? 'Strengths' : 'Gaps'}
      </h4>
      <ul className="space-y-1">
        {items.map((item, i) => (
          <li
            key={i}
            className={`text-sm ${isStrength ? 'text-green-800' : 'text-red-800'}`}
          >
            • {item}
          </li>
        ))}
      </ul>
    </div>
  );
}
