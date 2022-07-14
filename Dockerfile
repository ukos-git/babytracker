FROM debian:stable

RUN apt-get update && \
    apt-get install --assume-yes \
	    python3 \
		python3-pip && \
	apt-get clean

RUN mkdir /app
WORKDIR /app
COPY requirements.txt /app/
RUN pip install -r requirements.txt
COPY babytracker /app/babytracker
VOLUME data
COPY data/config.ini /app/data/config.ini
CMD python3 -m babytracker
