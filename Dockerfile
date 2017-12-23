FROM python:3.6.3-alpine3.6
ADD . /code
WORKDIR /code
RUN pip install -r requirements.txt
ENV FLASK_APP index.py
ENV FLASK_DEBUG 1
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:5000", "--reload", "index:app"]
