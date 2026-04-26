import { useState, useEffect, useCallback } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { useLocation } from "wouter";
import { API_URL } from "@/config";
import { Button } from "@/components/ui/button";
import { Monitor, Smartphone, Tablet, LogOut, Loader2, CheckCircle2 } from "lucide-react";

interface Device {
  session_id: string;
  device_name: string;
  device_type: string;
  last_active: string;
  last_ip?: string | null;
  is_current: boolean;
}

function DeviceIcon({ type }: { type: string }) {
  switch (type) {
    case "mobile":
      return <Smartphone className="w-5 h-5 text-primary/70" />;
    case "tablet":
      return <Tablet className="w-5 h-5 text-primary/70" />;
    default:
      return <Monitor className="w-5 h-5 text-primary/70" />;
  }
}

function formatRelativeTime(isoString: string): string {
  if (!isoString) return "未知";
  const now = Date.now();
  const then = new Date(isoString).getTime();
  const diff = Math.floor((now - then) / 1000);
  if (diff < 60) return "刚刚";
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`;
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`;
  return `${Math.floor(diff / 86400)} 天前`;
}

export function DeviceManagement() {
  const { token, logout } = useAuth();
  const [, navigate] = useLocation();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [loggingOutAll, setLoggingOutAll] = useState(false);

  const fetchDevices = useCallback(async () => {
    if (!token) return;
    try {
      const res = await fetch(`${API_URL}/auth/devices`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setDevices(await res.json());
      }
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    fetchDevices();
  }, [fetchDevices]);

  const removeDevice = async (sessionId: string) => {
    if (!token) return;
    setRemovingId(sessionId);
    try {
      await fetch(`${API_URL}/auth/devices/${sessionId}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
      await fetchDevices();
    } catch {
      // ignore
    } finally {
      setRemovingId(null);
    }
  };

  const logoutAll = async () => {
    if (!token) return;
    setLoggingOutAll(true);
    try {
      await fetch(`${API_URL}/auth/logout-all`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      logout();
      navigate("/");
    } catch {
      setLoggingOutAll(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-display font-bold tracking-wide">设备管理</h3>
      <div className="space-y-2">
        {devices.map((device) => (
          <div
            key={device.session_id}
            className="flex items-center gap-3 bg-card border border-border rounded-sm p-3"
          >
            <DeviceIcon type={device.device_type} />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium truncate flex items-center gap-2">
                {device.device_name}
                {device.is_current && (
                  <span className="inline-flex items-center gap-1 text-xs text-primary">
                    <CheckCircle2 className="w-3 h-3" />
                    当前
                  </span>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                活跃于 {formatRelativeTime(device.last_active)}
                {device.last_ip && ` · ${device.last_ip}`}
              </div>
            </div>
            {!device.is_current && (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => removeDevice(device.session_id)}
                disabled={removingId === device.session_id}
                className="text-destructive hover:text-destructive shrink-0"
              >
                {removingId === device.session_id ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <LogOut className="w-4 h-4" />
                )}
                <span className="ml-1">退出</span>
              </Button>
            )}
          </div>
        ))}
      </div>

      {devices.length > 1 && (
        <Button
          variant="outline"
          className="w-full text-destructive hover:text-destructive"
          onClick={logoutAll}
          disabled={loggingOutAll}
        >
          {loggingOutAll ? (
            <Loader2 className="w-4 h-4 animate-spin mr-2" />
          ) : (
            <LogOut className="w-4 h-4 mr-2" />
          )}
          退出所有设备
        </Button>
      )}
    </div>
  );
}
