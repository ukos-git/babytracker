FROM debian:bullseye

RUN apt-get update && \
    apt-get install --assume-yes \
	    python3 \
		python3-pip && \
	apt-get clean

RUN mkdir /app
WORKDIR /app
COPY requirements.txt /app/
RUN pip3 install -r requirements.txt
COPY babytracker /app/babytracker
VOLUME data
COPY data/config.ini /app/data/config.ini
ENV TZ="Europe/Berlin"
CMD python3 -m babytracker
