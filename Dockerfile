FROM python:3.11-slim-bullseye
ENV TZ="America/Sao_Paulo"

WORKDIR /usr/src/app

ARG EMAIL_USER
ARG EMAIL_PASS
ARG BOTCONVERSA_API_KEY

RUN echo "EMAIL_USER=${EMAIL_USER}" >> .env && \
    echo "EMAIL_PASS=${EMAIL_PASS}" >> .env && \
    echo "BOTCONVERSA_API_KEY=${BOTCONVERSA_API_KEY}" >> .env

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

RUN pip install --upgrade pip
COPY ./requirements.txt /usr/src/app/requirements.txt
RUN pip install -r requirements.txt

COPY service.py /usr/src/app/
COPY credentials /usr/src/app/credentials
COPY settings /usr/src/app/settings
COPY messages /usr/src/app/messages
COPY kami_pricing /usr/src/app/kami_pricing

CMD ["python", "service.py"]