FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 TZ=Asia/Ho_Chi_Minh
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -r appuser && chown -R appuser /app
USER appuser
