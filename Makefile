.PHONY: docker

IMAGE := ukos/babytracker:latest

docker: build

build:
	docker build -t $(IMAGE) .

run:
	docker run --rm -v $$(pwd)/data:/app/data:Z -p 8050:8050 $(IMAGE)

shell:
	docker run -it -v $$(pwd)/data:/app/data:Z $(IMAGE) /bin/bash

daemon:
	docker run -d --restart unless-stopped -v $$(pwd)/data:/app/data:Z -p 8050:8050 $(IMAGE)
