FROM python:3.6-alpine
RUN apk --no-cache add gcc musl-dev
RUN pip install pipenv
COPY Pipfile* /tmp/
RUN cd /tmp && pipenv lock --keep-outdated --requirements > requirements.txt
RUN pip install -r /tmp/requirements.txt
COPY . /app
CMD python /app/led_sequence/main.py