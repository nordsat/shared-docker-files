FROM python:3.11-slim
# this should install pytroll collectors package where cat resides
WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY cat.py /usr/local/bin

#RUN mkdir /app
COPY entrypoint.sh /app
RUN chmod u+x /app/entrypoint.sh

ENTRYPOINT [ "/app/entrypoint.sh" ]
