import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from '@/components/ui/table';
import { usersApi } from '@/api/services';
import type { UserListItem } from '@/api/types';

function formatDate(s: string | null) {
  if (!s) return '-';
  return new Date(s).toLocaleString('zh-CN');
}

function formatSeconds(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (h > 0) return `${h}h ${m}m`;
  return `${m}m`;
}

export default function Users() {
  const [users, setUsers] = useState<UserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState('');
  const pageSize = 20;

  const fetchUsers = useCallback(async () => {
    const res = await usersApi.list({ page, page_size: pageSize, search });
    setUsers(res.data.items);
    setTotal(res.data.total);
  }, [page, search]);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const toggleActive = async (user: UserListItem) => {
    await usersApi.update(user.id, { is_active: !user.is_active });
    fetchUsers();
  };

  const toggleAdmin = async (user: UserListItem) => {
    await usersApi.update(user.id, { is_admin: !user.is_admin });
    fetchUsers();
  };

  const totalPages = Math.ceil(total / pageSize);

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold">用户管理</h2>

      <div className="flex gap-2">
        <Input
          placeholder="搜索邮箱..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="max-w-xs"
        />
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>邮箱</TableHead>
                <TableHead>状态</TableHead>
                <TableHead>角色</TableHead>
                <TableHead>书籍数</TableHead>
                <TableHead>阅读时长</TableHead>
                <TableHead>最近活跃</TableHead>
                <TableHead>注册时间</TableHead>
                <TableHead>操作</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="font-medium">{u.email}</TableCell>
                  <TableCell>
                    <Badge variant={u.is_active ? 'default' : 'destructive'}>
                      {u.is_active ? '正常' : '已禁用'}
                    </Badge>
                    {u.is_verified && <Badge variant="outline" className="ml-1">已验证</Badge>}
                  </TableCell>
                  <TableCell>
                    {u.is_admin && <Badge variant="secondary">管理员</Badge>}
                  </TableCell>
                  <TableCell>{u.book_count}</TableCell>
                  <TableCell>{formatSeconds(u.total_reading_seconds)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDate(u.last_active_at)}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{formatDate(u.created_at)}</TableCell>
                  <TableCell>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" onClick={() => toggleActive(u)}>
                        {u.is_active ? '禁用' : '启用'}
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => toggleAdmin(u)}>
                        {u.is_admin ? '取消管理员' : '设为管理员'}
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={8} className="text-center text-muted-foreground py-8">暂无用户</TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <span className="text-sm text-muted-foreground">共 {total} 个用户</span>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>
              上一页
            </Button>
            <span className="text-sm leading-8">{page} / {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage(page + 1)}>
              下一页
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
