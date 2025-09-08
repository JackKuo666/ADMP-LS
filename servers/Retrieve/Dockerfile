from python:3.11-slim as builder

WORKDIR /app

# 首先只复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
RUN pip install -U crawl4ai
# 运行安装后设置
RUN crawl4ai-setup

# Verify your installation
RUN crawl4ai-doctor

# RUN python -m playwright install --with-deps chromium
# 第二阶段
#from python:3.11-slim

#WORKDIR /app

# 从构建阶段复制已安装的依赖
#COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
#COPY --from=builder /ms-playwright /ms-playwright


# 复制应用代码
COPY . .

     
# 声明端口
EXPOSE 9487

USER root


# 3. 设置缓存路径并赋予权限

# 4. 切换非root用户（避免权限问题）
# RUN useradd -m appuser && chown -R appuser:appuser /app
# USER appuser
CMD ["python", "main.py"]