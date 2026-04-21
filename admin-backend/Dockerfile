FROM python:3.11-slim

WORKDIR /app

COPY admin-backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

COPY epub-tts-backend/shared /app/shared
COPY admin-backend/ /app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
