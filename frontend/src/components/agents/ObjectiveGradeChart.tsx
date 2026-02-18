import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip, ReferenceLine } from 'recharts'
import type { AgentObjective } from '../../api/types'

const gradeToNum: Record<string, number> = {
  A: 4,
  B: 3,
  C: 2,
  F: 1,
  'N/A': 0,
}

const numToGrade: Record<number, string> = {
  4: 'A',
  3: 'B',
  2: 'C',
  1: 'F',
  0: 'N/A',
}

interface ObjectiveGradeChartProps {
  objectives: AgentObjective[]
}

export function ObjectiveGradeChart({ objectives }: ObjectiveGradeChartProps) {
  if (objectives.length === 0) {
    return (
      <div className="text-xs text-text-muted py-4 text-center">
        No grade history yet
      </div>
    )
  }

  // Sort oldest first for chart
  const data = [...objectives]
    .reverse()
    .map((o) => ({
      date: o.date,
      grade: gradeToNum[o.grade || 'N/A'] || 0,
      label: o.grade || 'N/A',
    }))

  return (
    <div className="h-32">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 5, right: 10, left: 0, bottom: 5 }}>
          <XAxis
            dataKey="date"
            tick={{ fontSize: 9, fill: '#6b7280' }}
            tickFormatter={(v: string) => v.slice(5)} // MM-DD
          />
          <YAxis
            domain={[0, 4]}
            ticks={[1, 2, 3, 4]}
            tickFormatter={(v: number) => numToGrade[v] || ''}
            tick={{ fontSize: 9, fill: '#6b7280' }}
            width={24}
          />
          <Tooltip
            contentStyle={{
              backgroundColor: '#1a1a2e',
              border: '1px solid #2a2a3e',
              borderRadius: 4,
              fontSize: 11,
            }}
            formatter={(value: number) => [numToGrade[value] || 'N/A', 'Grade']}
            labelStyle={{ color: '#9ca3af' }}
          />
          <ReferenceLine y={3} stroke="#22c55e" strokeDasharray="3 3" strokeOpacity={0.3} />
          <Line
            type="monotone"
            dataKey="grade"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 3, fill: '#3b82f6' }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
