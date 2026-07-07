FROM python:3.11-slim
WORKDIR /app
COPY execution/take_snapshot.py execution/take_snapshot.py
CMD ["python3", "execution/take_snapshot.py"]
