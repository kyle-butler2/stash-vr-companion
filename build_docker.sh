#!/bin/bash

export DOCKER_HOST=ssh://tower
docker image build --tag stash-vr-companion -f Dockerfile.local .

