#!/usr/bin/env bash

echo "Starting Docker Desktop..."
open -a Docker

echo "Waiting for Docker to be ready..."
until docker info > /dev/null 2>&1; do
  sleep 2
done

echo "✅ Docker is running. Starting Docker Compose..."
docker-compose up --build