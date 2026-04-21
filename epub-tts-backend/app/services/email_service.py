import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from loguru import logger
from shared.config import settings


class EmailService:
    @staticmethod
    def send_verification_email(to_email: str, token: str) -> bool:
        if not settings.smtp_host or not settings.smtp_user:
            logger.warning("SMTP not configured, skipping verification email")
            return False

        verify_url = f"{settings.app_url}/#/verify?token={token}"

        html = f"""\
<div style="max-width:480px;margin:0 auto;padding:32px;font-family:system-ui,sans-serif;">
  <h2 style="color:#333;margin-bottom:24px;">DeepReader 邮箱验证</h2>
  <p style="color:#555;line-height:1.6;">
    感谢注册 DeepReader！请点击下方按钮验证您的邮箱地址：
  </p>
  <div style="text-align:center;margin:32px 0;">
    <a href="{verify_url}"
       style="background:#0066ff;color:#fff;padding:12px 32px;border-radius:6px;text-decoration:none;font-weight:600;">
      验证邮箱
    </a>
  </div>
  <p style="color:#999;font-size:13px;">
    如果按钮无法点击，请复制以下链接到浏览器打开：<br/>
    <a href="{verify_url}" style="color:#0066ff;word-break:break-all;">{verify_url}</a>
  </p>
  <p style="color:#999;font-size:13px;">此链接 24 小时内有效。</p>
</div>"""

        msg = MIMEMultipart("alternative")
        msg["Subject"] = "DeepReader - 邮箱验证"
        msg["From"] = settings.smtp_from or settings.smtp_user
        msg["To"] = to_email
        msg.attach(MIMEText(html, "html", "utf-8"))

        try:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port) as server:
                server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(msg["From"], [to_email], msg.as_string())
            logger.info(f"Verification email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send verification email to {to_email}: {e}")
            return False
