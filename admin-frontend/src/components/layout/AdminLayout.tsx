import { Link, useLocation, Outlet, Navigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

const navItems = [
  { path: '/', label: '仪表盘' },
  { path: '/users', label: '用户管理' },
  { path: '/settings', label: '系统配置' },
];

export default function AdminLayout() {
  const { isAuthenticated, logout } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) return <Navigate to="/login" replace />;

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 border-r bg-card flex flex-col">
        <div className="p-4 border-b">
          <h1 className="text-lg font-semibold">BookReader Admin</h1>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {navItems.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={cn(
                'block px-3 py-2 rounded-md text-sm transition-colors',
                location.pathname === item.path
                  ? 'bg-primary text-primary-foreground'
                  : 'hover:bg-muted',
              )}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <div className="p-4 border-t">
          <Button variant="outline" size="sm" className="w-full" onClick={logout}>
            退出登录
          </Button>
        </div>
      </aside>
      <main className="flex-1 p-6 overflow-auto bg-background">
        <Outlet />
      </main>
    </div>
  );
}
