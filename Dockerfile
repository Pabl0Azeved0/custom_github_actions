FROM python:3.12-slim

WORKDIR /action

COPY requirements.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY src/ ./src/
ENV PYTHONPATH=/action/src

# GitHub mounts /github/workspace read-write, so the action must not run as root:
# it only reads the event payload and calls APIs, and never writes to the checkout.
RUN useradd --create-home --uid 1001 reviewer
USER reviewer

ENTRYPOINT ["python", "-m", "pr_reviewer.main"]
