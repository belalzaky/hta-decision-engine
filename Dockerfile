# HTA Decision Engine — containerised build of the NICE recommendation spine.
#
# The raw NICE spreadsheet is NOT baked into the image and is never redistributed
# (see LICENSING.md §7). Mount your local cache at run time:
#
#   docker build -t hta-decision-engine .
#   docker run --rm \
#     -v "$PWD/data:/app/data" -v "$PWD/results:/app/results" \
#     hta-decision-engine build
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

ENV PYTHONPATH=/app/src

ENTRYPOINT ["python", "-m", "hta.cli"]
CMD ["--help"]
