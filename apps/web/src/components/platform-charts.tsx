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

const PALETTE = [
  "hsl(var(--chart-1))",
  "hsl(var(--chart-2))",
  "hsl(var(--chart-3))",
  "hsl(var(--chart-4))",
  "hsl(var(--chart-5))",
  "hsl(var(--chart-6))",
];

interface TooltipItem {
  name?: string;
  value?: number | string;
  color?: string;
}

function ChartTooltip({ active, payload, label, suffix = "" }: { active?: boolean; payload?: TooltipItem[]; label?: string; suffix?: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border bg-card px-3.5 py-2.5 text-xs shadow-pop animate-scale-in">
      {label != null && <p className="mb-1.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</p>}
      <div className="space-y-1">
        {payload.map((p, i) => (
          <p key={i} className="flex items-center gap-2 text-[13px]">
            <span className="inline-block h-2 w-2 rounded-sm" style={{ background: p.color ?? PALETTE[i % PALETTE.length] }} />
            <span className="text-muted-foreground">{p.name}:</span>
            <span className="font-semibold text-foreground">
              {p.value}
              {suffix}
            </span>
          </p>
        ))}
      </div>
    </div>
  );
}

const axis = { tick: { fontSize: 11, fill: "hsl(var(--muted-foreground))" }, tickLine: false, axisLine: false };
const grid = "hsl(var(--border))";

export function TrendArea({
  data,
  keys,
  height = 280,
}: {
  data: Array<Record<string, unknown>>;
  keys: Array<{ key: string; name: string; color: string }>;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          {keys.map((k) => (
            <linearGradient key={k.key} id={`grad-${k.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={k.color} stopOpacity={0.25} />
              <stop offset="100%" stopColor={k.color} stopOpacity={0.02} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
        <XAxis dataKey="period" {...axis} dy={6} />
        <YAxis {...axis} allowDecimals={false} />
        <Tooltip content={<ChartTooltip />} />
        {keys.map((k) => (
          <Area
            key={k.key}
            type="monotone"
            dataKey={k.key}
            name={k.name}
            stroke={k.color}
            strokeWidth={2.5}
            fill={`url(#grad-${k.key})`}
            dot={{ r: 2.5, fill: k.color, strokeWidth: 0 }}
            activeDot={{ r: 5 }}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export function SeriesBars({
  data,
  keys,
  height = 280,
  suffix = "",
}: {
  data: Array<Record<string, unknown>>;
  keys: Array<{ key: string; name: string; color: string }>;
  height?: number;
  suffix?: string;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke={grid} vertical={false} />
        <XAxis dataKey="period" {...axis} dy={6} />
        <YAxis {...axis} allowDecimals={false} />
        <Tooltip content={<ChartTooltip suffix={suffix} />} cursor={{ fill: "hsl(var(--muted) / 0.4)" }} />
        {keys.map((k) => (
          <Bar key={k.key} dataKey={k.key} name={k.name} fill={k.color} radius={[4, 4, 2, 2]} maxBarSize={28} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

export function Donut({
  data,
  dataKey,
  nameKey,
  height = 240,
}: {
  data: Array<Record<string, unknown>>;
  dataKey: string;
  nameKey: string;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <PieChart>
        <Pie data={data} dataKey={dataKey} nameKey={nameKey} innerRadius="62%" outerRadius="90%" paddingAngle={3} strokeWidth={0} cornerRadius={4}>
          {data.map((_, i) => (
            <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
          ))}
        </Pie>
        <Tooltip content={<ChartTooltip />} />
      </PieChart>
    </ResponsiveContainer>
  );
}

export { PALETTE };