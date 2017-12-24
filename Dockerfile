FROM python:3.6.3-alpine3.6
ADD requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt
ADD . /app
WORKDIR /app
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--reload", "index:app"]
