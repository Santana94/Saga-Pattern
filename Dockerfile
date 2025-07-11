FROM python:3.9

WORKDIR /app

# Install common dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Build argument to select which service to build
ARG SERVICE_DIR
# Persist the build argument as an environment variable
ENV SERVICE_DIR=${SERVICE_DIR}

# Copy the entire service folder into /app/<SERVICE_DIR>
COPY ${SERVICE_DIR} /app/${SERVICE_DIR}

EXPOSE 8000

# Use an entrypoint that runs uvicorn with the proper package reference.
CMD ["sh", "-c", "uvicorn ${SERVICE_DIR}.main:app --host 0.0.0.0 --port 8000"]
