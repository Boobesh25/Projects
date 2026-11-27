FROM python:3.11-slim

WORKDIR /app

# Copy the standalone benchmark script
COPY cloud_portal_tester.py /app/cloud_portal_tester.py

# Run the benchmark and write report to /app/cloud_discovery_report.json
CMD ["python", "cloud_portal_tester.py"]
