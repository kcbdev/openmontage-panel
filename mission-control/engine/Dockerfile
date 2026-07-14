FROM python:3.10-slim AS base
RUN apt-get update && apt-get install -y nodejs npm ffmpeg git

WORKDIR /app
COPY openmontage-src/ .

RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir pytest
RUN cd remotion-composer && npm install

# Mission Control entrypoint — writes config from env vars
COPY engine/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]

# Default command: run the headless pipeline runner
CMD ["python", "-m", "headless_runner"]
