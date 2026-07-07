FROM python:3.11-slim
WORKDIR /app
COPY execution/take_snapshot.py execution/take_snapshot.py
COPY execution/generate_dashboard.py execution/generate_dashboard.py
CMD ["python3", "execution/take_snapshot.py"]
