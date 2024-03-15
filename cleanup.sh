#!/usr/bin/bash

PWD=$(pwd)
ANSIBLE_DIR="$PWD/ansible-avalanche-getting-started"
OP_DIR="$PWD/op-integration"
NODEKIT_L1_DIR="$OP_DIR/nodekit-l1"
BEDROCK_DIR="$OP_DIR/ops-bedrock"

docker container stop avax_nginx
docker container rm avax_nginx

cd $ANSIBLE_DIR
./scripts/cleanup.sh

cd $BEDROCK_DIR
docker compose down -v

cd $NODEKIT_L1_DIR
docker compose down -v