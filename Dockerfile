FROM python:3.8

RUN mkdir -p /usr/scr/app
WORKDIR /usr/src/app

COPY . /usr/src/app
RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "parser_cisco_ios_config.py"]
