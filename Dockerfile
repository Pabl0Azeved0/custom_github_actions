FROM python:3.12-slim

WORKDIR /action

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
ENV PYTHONPATH=/action/src

ENTRYPOINT ["python", "-m", "pr_reviewer.main"]
