FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
COPY server/requirements.txt ./server/requirements.txt
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY server/ ./server/
COPY startup.sh ./
EXPOSE 8000
CMD ["bash", "startup.sh"]
