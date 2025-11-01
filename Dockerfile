# 使用Python 3.11作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制所有项目文件
COPY . .

# 创建数据目录
RUN mkdir -p /app/data/groups /app/data/logs/private_chats

# 暴露端口（用于健康检查）
EXPOSE 10000

# 设置环境变量（默认端口）
ENV PORT=10000

# 运行bot
CMD ["python", "bot.py"]
