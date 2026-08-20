"use client";

import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

type Point = {
  value?: number | string;
  name?: string;
  color?: string;
  payload?: Record<string, unknown>;
};

const PALETTE = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "hsl(var(--chart-6))",
];

function ChartTooltip({ active, payload, label, suffix = "" }: TooltipProps & { suffix?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border bg-card px-3.5 py-2.5 text-xs shadow-pop animate-scale-in">
      {label != null && <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>}
      <div className="space-y-1">
        {payload.map((p, i) => (
          <p key={i} className="flex items-center gap-2 text-[13px]">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: p.color ?? PALETTE[i % PALETTE.length] }} />
            <span className="text-muted-foreground">{p.name}:</span>
            <span className="font-semibold text-foreground">{p.value}{suffix}</span>
          </p>
        ))}
      </div>
    </div>
  );
}

function AxisTicks() {
  return {
    tick: { fontSize: 11, fill: "hsl(var(--muted-foreground))" },
    tickLine: false,
    axisLine: false,
  };
}

interface TooltipProps {
  active?: boolean;
  payload?: Array<{
    name?: string;
    value?: number | string;
    color?: string;
    payload?: Record<string, unknown>;
  }>;
  label?: string;
}

const grid = "hsl(var(--border))";

// ----------------------------------------------------------------------------
// Academic performance — average score + pass rate over terms.
// ----------------------------------------------------------------------------
export function PerformanceChart({
  data,
  height = 300,
}: {
  data: Array<{ term_name: string; avg_score: number | null; pass_rate: number | null }>;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <defs>
          <linearGradient id="gradAvg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--chart-1))" stopOpacity={0.28} />
            <stop offset="100%" stopColor="hsl(var(--chart-1))" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="gradPass" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--chart-3))" stopOpacity={0.18} />
            <stop offset="100%" stopColor="hsl(var(--chart-3))" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
        <XAxis dataKey="term_name" {...AxisTicks()} dy={6} />
        <YAxis domain={[0, 100]} {...AxisTicks()} />
        <Tooltip content={<ChartTooltip suffix="%" />} />
        <Area
          type="monotone"
          dataKey="avg_score"
          name="Average"
          stroke="hsl(var(--chart-1))"
          strokeWidth={2.5}
          fill="url(#gradAvg)"
          dot={{ r: 3.5, fill: "hsl(var(--chart-1))", strokeWidth: 0 }}
          activeDot={{ r: 5 }}
        />
        <Area
          type="monotone"
          dataKey="pass_rate"
          name="Pass rate"
          stroke="hsl(var(--chart-3))"
          strokeWidth={2.5}
          fill="url(#gradPass)"
          dot={{ r: 3.5, fill: "hsl(var(--chart-3))", strokeWidth: 0 }}
          activeDot={{ r: 5 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// ----------------------------------------------------------------------------
// Class performance — horizontal-friendly vertical bar chart by class.
// ----------------------------------------------------------------------------
export function ClassPerformanceBar({
  data,
  height = 260,
}: {
  data: Array<{ arm_name: string; avg_score: number | null; count: number }>;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
        <XAxis dataKey="arm_name" {...AxisTicks()} interval={0} tick={{ ...AxisTicks().tick, fontSize: 10 }} />
        <YAxis domain={[0, 100]} {...AxisTicks()} />
        <Tooltip content={<ChartTooltip suffix="%" />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
        <Bar dataKey="avg_score" name="Avg score" radius={[5, 5, 2, 2]} maxBarSize={36}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// ----------------------------------------------------------------------------
// Enrollment distribution donut with a centered total.
// ----------------------------------------------------------------------------
export function DistributionDonut({
  data,
  total,
  height = 220,
}: {
  data: Array<{ level_name: string; count: number }>;
  total?: number;
  height?: number;
}) {
  const center = (
    <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
      <p className="text-2xl font-bold tracking-tight">{total ?? 0}</p>
      <p className="text-[10px] font-medium uppercase tracking-wider text-muted-foreground">students</p>
    </div>
  );
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey="count"
            nameKey="level_name"
            innerRadius="68%"
            outerRadius="92%"
            paddingAngle={3}
            strokeWidth={0}
            cornerRadius={4}
          >
            {data.map((_, i) => (
              <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
            ))}
          </Pie>
          <Tooltip content={<ChartTooltip />} />
        </PieChart>
      </ResponsiveContainer>
      {center}
    </div>
  );
}

// ----------------------------------------------------------------------------
// Attendance stacked bars.
// ----------------------------------------------------------------------------
export function AttendanceBars({
  data,
  height = 200,
}: {
  data: Array<{ name: string; present: number; absent: number; late: number }>;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
        <XAxis dataKey="name" {...AxisTicks()} />
        <YAxis allowDecimals={false} {...AxisTicks()} />
        <Tooltip content={<ChartTooltip />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
        <Bar dataKey="present" name="Present" stackId="a" fill="hsl(var(--chart-3))" radius={[0, 0, 2, 2]} maxBarSize={44} />
        <Bar dataKey="late" name="Late" stackId="a" fill="hsl(var(--chart-4))" maxBarSize={44} />
        <Bar dataKey="absent" name="Absent" stackId="a" fill="hsl(var(--chart-6))" radius={[4, 4, 0, 0]} maxBarSize={44} />
      </BarChart>
    </ResponsiveContainer>
  );
}

export { PALETTE };