#!/bin/bash

if [ -z "$1" ] || [ -z "$2" ]
then
    echo "pipenv lock -r > requirements.txt"
    pipenv lock -r > requirements.txt
    echo "rsync -azrP --exclude-from \"rsync.exc\" --include \".dockerignore\" \
        ./ smartCity-dataMarket-tmp:/home/centos/kohpai/"
    rsync -azrP --exclude-from "rsync.exc" --include ".dockerignore" \
        ./ smartCity-dataMarket-tmp:/home/centos/kohpai/
else
    echo "pipenv lock -r > requirements.txt"
    pipenv lock -r > requirements.txt
    echo "rsync -azrP --exclude-from \"rsync.exc\" --include \".dockerignore\" ./ $1:$2"
    rsync -azrP --exclude-from "rsync.exc" --include ".dockerignore" ./ $1:$2
fi

