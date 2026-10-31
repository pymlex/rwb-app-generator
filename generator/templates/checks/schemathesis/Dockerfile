FROM python:3.12-alpine
RUN pip install --no-cache-dir schemathesis==4.31.1
WORKDIR /checks
COPY checks/schemathesis/run.py ./run.py
ENTRYPOINT ["python", "/checks/run.py"]
