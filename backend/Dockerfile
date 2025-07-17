FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt 


COPY . .

COPY run.sh .
RUN chmod +x run.sh

EXPOSE 8000

ENTRYPOINT ["/bin/bash", "/app/run.sh"]
