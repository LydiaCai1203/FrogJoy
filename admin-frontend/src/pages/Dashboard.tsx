import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { dashboardApi } from '@/api/services';
import type { OverviewStats, GrowthPoint, ReadingStatsPoint, ActiveUserItem } from '@/api/types';
import {
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar,
} from 'recharts';

function formatSeconds(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function Dashboard() {
  const [overview, setOverview] = useState<OverviewStats | null>(null);
  const [growth, setGrowth] = useState<GrowthPoint[]>([]);
  const [reading, setReading] = useState<ReadingStatsPoint[]>([]);
  const [active, setActive] = useState<ActiveUserItem[]>([]);

  useEffect(() => {
    dashboardApi.overview().then((r) => setOverview(r.data));
    dashboardApi.userGrowth(30).then((r) => setGrowth(r.data.data));
    dashboardApi.readingStats(30).then((r) => setReading(r.data.data));
    dashboardApi.activeUsers(7, 10).then((r) => setActive(r.data.data));
  }, []);

  if (!overview) return <div className="text-muted-foreground">加载中...</div>;

  const statCards = [
    { title: '用户总数', value: overview.total_users },
    { title: '已验证用户', value: overview.verified_users },
    { title: '书籍总数', value: overview.total_books },
    { title: '今日活跃', value: overview.today_active_users },
    { title: '总阅读时长', value: formatSeconds(overview.total_reading_seconds) },
    { title: '管理员', value: overview.admin_users },
  ];

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-semibold">数据概览</h2>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        {statCards.map((c) => (
          <Card key={c.title}>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">{c.title}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{c.value}</div>
            </CardContent>
          </Card>
        ))}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader><CardTitle className="text-base">用户增长趋势（近30天）</CardTitle></CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={growth}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Area type="monotone" dataKey="count" stroke="hsl(var(--chart-1))" fill="hsl(var(--chart-1))" fillOpacity={0.2} />
              </AreaChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader><CardTitle className="text-base">阅读时长趋势（近30天）</CardTitle></CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={reading.map((r) => ({ ...r, hours: +(r.total_seconds / 3600).toFixed(1) }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                <YAxis />
                <Tooltip />
                <Bar dataKey="hours" fill="hsl(var(--chart-2))" name="阅读时长(h)" />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader><CardTitle className="text-base">活跃用户排行（近7天）</CardTitle></CardHeader>
        <CardContent>
          <div className="space-y-2">
            {active.map((u, i) => (
              <div key={u.user_id} className="flex items-center justify-between py-1 text-sm">
                <span className="text-muted-foreground w-6">{i + 1}</span>
                <span className="flex-1 truncate">{u.email}</span>
                <span className="text-muted-foreground">{u.reading_days}天</span>
                <span className="w-24 text-right font-medium">{formatSeconds(u.total_reading_seconds)}</span>
              </div>
            ))}
            {active.length === 0 && <p className="text-muted-foreground text-sm">暂无数据</p>}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
