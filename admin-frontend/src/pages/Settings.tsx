import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Separator } from '@/components/ui/separator';
import { settingsApi } from '@/api/services';
import type { SystemSettings } from '@/api/types';

export default function Settings() {
  const [settings, setSettings] = useState<SystemSettings | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    settingsApi.get().then((r) => setSettings(r.data));
  }, []);

  const handleSave = async () => {
    if (!settings) return;
    setSaving(true);
    try {
      const res = await settingsApi.update(settings);
      setSettings(res.data);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } finally {
      setSaving(false);
    }
  };

  if (!settings) return <div className="text-muted-foreground">加载中...</div>;

  const update = (key: keyof SystemSettings, value: unknown) => {
    setSettings({ ...settings, [key]: value });
  };

  return (
    <div className="space-y-6 max-w-2xl">
      <h2 className="text-2xl font-semibold">系统配置</h2>

      <Card>
        <CardHeader><CardTitle className="text-base">游客限流</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-2">
              <Label>TTS (次/分钟)</Label>
              <Input
                type="number"
                value={settings.guest_rate_limit_tts}
                onChange={(e) => update('guest_rate_limit_tts', +e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>翻译 (次/分钟)</Label>
              <Input
                type="number"
                value={settings.guest_rate_limit_translation}
                onChange={(e) => update('guest_rate_limit_translation', +e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>AI 对话 (次/分钟)</Label>
              <Input
                type="number"
                value={settings.guest_rate_limit_chat}
                onChange={(e) => update('guest_rate_limit_chat', +e.target.value)}
              />
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">默认配置</CardTitle></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>默认 TTS 提供商</Label>
              <Input
                value={settings.default_tts_provider}
                onChange={(e) => update('default_tts_provider', e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>默认主题</Label>
              <Input
                value={settings.default_theme}
                onChange={(e) => update('default_theme', e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-2">
            <Label>默认字号</Label>
            <Input
              type="number"
              value={settings.default_font_size}
              onChange={(e) => update('default_font_size', +e.target.value)}
              className="w-32"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-base">注册控制</CardTitle></CardHeader>
        <CardContent>
          <div className="flex items-center gap-3">
            <Switch
              checked={settings.allow_registration}
              onCheckedChange={(v) => update('allow_registration', v)}
            />
            <Label>允许新用户注册</Label>
          </div>
        </CardContent>
      </Card>

      <Separator />

      <div className="flex items-center gap-3">
        <Button onClick={handleSave} disabled={saving}>
          {saving ? '保存中...' : '保存配置'}
        </Button>
        {saved && <span className="text-sm text-green-600">已保存</span>}
      </div>
    </div>
  );
}
