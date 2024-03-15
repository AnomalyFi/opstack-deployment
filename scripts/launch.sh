#!/usr/bin/bash

PWD=$(pwd)
ANSIBLE_DIR="$PWD/ansible-avalanche-getting-started"
OP_DIR="$PWD/op-integration"

cd $ANSIBLE_DIR

./bin/setup.sh

source .venv/bin/activate

./scripts/create_vms.sh
./scripts/bootstrap.sh