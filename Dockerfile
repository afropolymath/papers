FROM python:3.9.0-alpine

WORKDIR /code

COPY . .

RUN mkdir -p upload

RUN chown -R $(whoami) upload

RUN chmod 777 upload

RUN pip install -r requirements.txt

CMD ["python", "-m", "flask", "run", "--host=0.0.0.0"]