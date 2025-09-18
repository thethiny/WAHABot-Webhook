FROM python:3.9-buster

WORKDIR /tmp
COPY requirements.txt .
RUN pip install -r requirements.txt --no-cache-dir

WORKDIR /app
COPY src src
COPY main.py .

COPY commands commands

ENTRYPOINT ["python3", "-m", "main"]
