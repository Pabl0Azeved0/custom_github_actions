FROM python:3.12-slim

WORKDIR /action

COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY src/ ./src/
ENV PYTHONPATH=/action/src

ENTRYPOINT ["python", "-m", "pr_reviewer.main"]
