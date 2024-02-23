FROM python:3.10-slim
ENV TZ="America/Sao_Paulo"

WORKDIR /app
COPY pyproject.toml service.py .env /app/
COPY credentials /app/credentials
COPY settings /app/settings
COPY messages /app/messages
COPY kami_pricing /app/kami_pricing/
RUN pip install poetry && \
    poetry install --only main

CMD ["poetry", "run", "python", "service.py"]