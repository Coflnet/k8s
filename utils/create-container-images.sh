#!/bin/bash


while :
do
	clear
	curl -X POST -H "Content-Type: application/json" -d '{"message":"My first webhook"}' https://argo-events.flou21.de/blog
	echo "build started"
	date
	sleep 50
done