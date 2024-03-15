#!/usr/bin/bash

PWD=$(pwd)
ANSIBLE_DIR="$PWD/ansible-avalanche-getting-started"
OP_DIR="$PWD/op-integration"

cd $ANSIBLE_DIR

./bin/setup.sh
source .venv/bin/activate
ansible-galaxy collection install git+https://github.com/AshAvalanche/ansible-avalanche-collection.git,0.12.1-2
ansible-galaxy install -r ansible_collections/ash/avalanche/requirements.yml