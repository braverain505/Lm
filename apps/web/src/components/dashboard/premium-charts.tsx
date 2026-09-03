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
import { motion } from "framer-motion";

const ease = [0.25, 0.46, 0.45, 0.94] as const;

/* ─── Shared tooltip ──────────────────────────────────────────────────── */

function ChartTooltip({
  active,
  payload,
  label,
  suffix = "",
}: {
  active?: boolean;
  payload?: Array<{ name?: string; value?: number | string; color?: string }>;
  label?: string;
  suffix?: string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-xl border border-white/60 bg-white px-3.5 py-2.5 shadow-[0_4px_12px_rgba(0,0,0,0.08)]">
      {label != null && (
        <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/50">
          {label}
        </p>
      )}
      <div className="space-y-1">
        {payload.map((p, i) => (
          <p key={i} className="flex items-center gap-2 text-[12px]">
            <span
              className="inline-block h-2 w-2 rounded-full"
              style={{ background: p.color }}
            />
            <span className="text-muted-foreground/60">{p.name}:</span>
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

const axisStyle = {
  tick: { fontSize: 10, fill: "hsl(var(--muted-foreground) / 0.4)" },
  tickLine: false,
  axisLine: false,
};

/* ─── Enrollment Donut ────────────────────────────────────────────────── */

export function EnrollmentDonut({
  data,
  total,
  height = 200,
}: {
  data: Array<{ name: string; value: number; color: string }>;
  total?: number;
  height?: number;
}) {
  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={height}>
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            innerRadius="65%"
            outerRadius="88%"
            paddingAngle={4}
            strokeWidth={0}
            cornerRadius={6}
          >
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip
            content={<ChartTooltip />}
          />
        </PieChart>
      </ResponsiveContainer>
      {total != null && (
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <p className="text-[22px] font-bold tracking-tight text-foreground">
            {total.toLocaleString()}
          </p>
          <p className="text-[9px] font-semibold uppercase tracking-wider text-muted-foreground/40">
            students
          </p>
        </div>
      )}
    </div>
  );
}

/* ─── Attendance Bar Chart ────────────────────────────────────────────── */

export function AttendanceOverviewChart({
  data,
  height = 200,
}: {
  data: Array<{ name: string; present: number; absent: number; late: number }>;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.3)" vertical={false} />
        <XAxis dataKey="name" {...axisStyle} />
        <YAxis allowDecimals={false} {...axisStyle} />
        <Tooltip
          content={<ChartTooltip />}
          cursor={{ fill: "hsl(var(--muted) / 0.3)" }}
        />
        <Bar dataKey="present" name="Present" stackId="a" fill="#10b981" radius={[0, 0, 3, 3]} maxBarSize={36} />
        <Bar dataKey="late" name="Late" stackId="a" fill="#f59e0b" maxBarSize={36} />
        <Bar dataKey="absent" name="Absent" stackId="a" fill="#f43f5e" radius={[4, 4, 0, 0]} maxBarSize={36} />
      </BarChart>
    </ResponsiveContainer>
  );
}

/* ─── Performance Trend (Area) ────────────────────────────────────────── */

export function PerformanceTrendChart({
  data,
  height = 220,
}: {
  data: Array<{ month: string; avg: number; pass: number }>;
  height?: number;
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 8, left: -16, bottom: 0 }}>
        <defs>
          <linearGradient id="gradPerfAvg" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#6366f1" stopOpacity={0.25} />
            <stop offset="100%" stopColor="#6366f1" stopOpacity={0.02} />
          </linearGradient>
          <linearGradient id="gradPerfPass" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#10b981" stopOpacity={0.18} />
            <stop offset="100%" stopColor="#10b981" stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border) / 0.3)" vertical={false} />
        <XAxis dataKey="month" {...axisStyle} dy={4} />
        <YAxis domain={[0, 100]} {...axisStyle} />
        <Tooltip content={<ChartTooltip suffix="%" />} />
        <Area
          type="monotone"
          dataKey="avg"
          name="Average"
          stroke="#6366f1"
          strokeWidth={2.5}
          fill="url(#gradPerfAvg)"
          dot={{ r: 3, fill: "#6366f1", strokeWidth: 0 }}
          activeDot={{ r: 5, strokeWidth: 2, stroke: "#fff" }}
        />
        <Area
          type="monotone"
          dataKey="pass"
          name="Pass rate"
          stroke="#10b981"
          strokeWidth={2.5}
          fill="url(#gradPerfPass)"
          dot={{ r: 3, fill: "#10b981", strokeWidth: 0 }}
          activeDot={{ r: 5, strokeWidth: 2, stroke: "#fff" }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}

/* ─── Score Entry Progress (horizontal bars) ──────────────────────────── */

export function ScoreEntryChart({
  data,
  height = 200,
}: {
  data: Array<{ subject: string; entered: number; total: number }>;
  height?: number;
}) {
  const maxVal = Math.max(1, ...data.map((d) => d.total));
  return (
    <div className="space-y-3" style={{ height }}>
      {data.map((item, idx) => {
        const pct = item.total > 0 ? Math.round((item.entered / item.total) * 100) : 0;
        const color = pct >= 100 ? "#10b981" : pct > 50 ? "#6366f1" : pct > 0 ? "#f59e0b" : "#e2e8f0";
        return (
          <motion.div
            key={item.subject}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.3, delay: 0.1 + idx * 0.05, ease }}
          >
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-[11px] font-medium text-foreground/70 truncate max-w-[120px]">
                {item.subject}
              </span>
              <span className="text-[10px] font-semibold text-muted-foreground/50">
                {item.entered}/{item.total} · {pct}%
              </span>
            </div>
            <div className="h-2 w-full rounded-full bg-muted/30 overflow-hidden">
              <motion.div
                className="h-full rounded-full"
                style={{ backgroundColor: color }}
                initial={{ width: 0 }}
                animate={{ width: `${pct}%` }}
                transition={{ duration: 0.8, delay: 0.2 + idx * 0.05, ease: "easeOut" }}
              />
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}

/* ─── Mini stat sparkline ─────────────────────────────────────────────── */

export function MiniSparkline({
  data,
  color = "#6366f1",
  height = 40,
  width = 80,
}: {
  data: number[];
  color?: string;
  height?: number;
  width?: number;
}) {
  const chartData = data.map((v, i) => ({ x: i, y: v }));
  return (
    <ResponsiveContainer width={width} height={height}>
      <AreaChart data={chartData} margin={{ top: 2, right: 2, left: 2, bottom: 2 }}>
        <defs>
          <linearGradient id={`spark-${color.replace("#", "")}`} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity={0.3} />
            <stop offset="100%" stopColor={color} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <Area
          type="monotone"
          dataKey="y"
          stroke={color}
          strokeWidth={1.5}
          fill={`url(#spark-${color.replace("#", "")})`}
          dot={false}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
