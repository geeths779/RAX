import { Radar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer } from 'recharts';

interface RadarChartProps {
  skills: number;
  experience: number;
  education: number;
}

export default function ScoreRadarChart({ skills, experience, education }: RadarChartProps) {
  const data = [
    { subject: 'Skills', score: skills },
    { subject: 'Experience', score: experience },
    { subject: 'Education', score: education },
  ];

  return (
    <ResponsiveContainer width="100%" height={250}>
      <RadarChart cx="50%" cy="50%" outerRadius="70%" data={data}>
        <PolarGrid stroke="#e5e7eb" />
        <PolarAngleAxis dataKey="subject" tick={{ fontSize: 13, fill: '#374151', fontWeight: 500 }} />
        <PolarRadiusAxis angle={90} domain={[0, 100]} tick={{ fontSize: 11, fill: '#6b7280' }} />
        <Radar
          name="Score"
          dataKey="score"
          stroke="#4f46e5"
          fill="#4f46e5"
          fillOpacity={0.2}
          strokeWidth={2}
        />
      </RadarChart>
    </ResponsiveContainer>
  );
}
