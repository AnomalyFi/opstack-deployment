# Deployment of OP-Stack

In this tutorial, we will cover how to launch op-stack along with nodekit stack, generally we have following steps:

1. Deploy ethereum layer 1(eth-l1) locally
2. Deploy Nodekit-Seq
3. Deploy contracts for op-stack l2 and nodekit-l1
4. Deploy Nodekit-L1
5. Launch op-l2

## Prerequisites

- Python >=3.9 with `venv` module installed
- For the local test network:
  - 7+GiB of free RAM
  - [Multipass](https://multipass.run) installed (see [Install Multipass](https://multipass.run/install))
  - [Terraform](https://terraform.io) installed (see [Install Terraform](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli))
- For filtering outputs:
  - [jq](https://stedolan.github.io/jq/) (see [Download jq](https://stedolan.github.io/jq/download/))
- Nix:
  - https://nixos.org/


Please run in the root folder(this repository)

```shell
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Then,

**In repository `ansible-avalanche-getting-started`**
```shell
./bin/setup.sh
```

Manually creating all the virtual machines are needed, go to repository `ansible-avalanche-getting-started`, run 

```shell
terraform -chdir=terraform/multipass init
terraform -chdir=terraform/multipass apply
```

If above script failed, simply re-run it


Finally, run
```shell
python main.py deploy
```

After the deployment, You're good to go!


# Manually deployment

to create a python environment, then run following command to install ansible-collections and ansible-roles for deploying `eth-l1` and `nodekit-seq`

```shell
source .venv/bin/activate
ansible-galaxy collection install git+https://github.com/AshAvalanche/ansible-avalanche-collection.git,0.12.1-2
ansible-galaxy install -r ansible_collections/ash/avalanche/requirements.yml
```

Also, when deploying `eth-l1` and `nodekit-seq`, remember to have `.venv` activated

## Deploy eth-l1

**In folder `ansible-avalanche-getting-started`**

First to activate `.venv`

```shell
source .venv/bin/activate
```

clean up existing multipass instances(i.e. virtual machines)

```shell
./scripts/cleanup.sh
```

create virtual machines, rerun if fail or rerun `cleanup.sh` then rerun `create_vms.sh`, ensure that vm `frontend` and vm `validator[01-05]` are created by command `multipass ls`

```shell
./scripts/create_vms.sh
```

launch avalanchego(nodekit-seq chain won't be launched) and eth-l1

```shell
./scripts/bootstrap.sh
```

To get IP addresses of above instances, simply type

```
terraform -chdir=terraform/multipass output
```

*Note that the IP address of eth-l1 is named as `frontend`, and IPs for nodekit-seq validators are named as `validators`, you will see 5 validators IP*

## Deploy Nodekit-Seq

**In repository `ansible-avalanche-getting-started`**

Before running any scripts, ensure that entry `avalanchego_track_subnets`  in the  file for avalanchego-node`inventories/local/group_vars` looks like following:

```yaml
avalanchego_track_subnets:
  []
  # - 2dqvrAFWjqQV5Gdr5zc5gkmHChyp7ZrQvfdg1E57GrNH6guGNY
```

where the commented out string is the subnet id we will change later

### Create nodekit-seq subnet

First, we need to create nodekit-seq subnet by 

```shell
ansible-playbook ash.avalanche.create_subnet -i inventories/local
```

which will output content like following

```
TASK [Display Subnet information]
ok: [validator01] =>
  msg:
    blockchains:
    - id: 2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au                    <=== Blockchain ID
      name: seqchain
      subnetID: 29uVeLPJB1eQJkzRemU8g8wZDw5uJRqpab5U2mX9euieVwiEbL
      vmID: tHBYNu8ikqo4MWMHehC9iKB9mR5tB3DWzbkYmTfe9buWQ5GZ8
      vmType: SubnetEVM
    controlKeys:
    - P-local18jma8ppw3nhx5r4ap8clazz0dps7rv5u00z96u
    id: 29uVeLPJB1eQJkzRemU8g8wZDw5uJRqpab5U2mX9euieVwiEbL                      <=== Subnet ID
    pendingValidators:
    - connected: false
      endTime: 1709056176
      nodeID: NodeID-7Xhw2mDxuDS44j42TCB6U5579esbSt3Lg
      stakeAmount: 100
      startTime: 1708451376
      txID: 2j8kj87kyWayyaXX9WNaYxC8JujjfqV1DbKqnTRiLAqNKFSLkJ
      weight: 100
    subnetType: Permissioned
    threshold: 1
    validators: []
```

where Blockchain ID and Subnet ID are needed in the later steps

### Modify avalanche-node config

Next, we have to modify the config in `inventories/local/group_vars/avalanche_nodes.yml`, where we need to add subnet id to let avalanchego daemon to keep track of, also inject nodekit-seq chain config

```yaml
...

avalanchego_track_subnets:
  [] # <= where we need to comment out
  # - 2dqvrAFWjqQV5Gdr5zc5gkmHChyp7ZrQvfdg1E57GrNH6guGNY <= comment out this and replace the Subnet ID obtained above

avalanchego_chains_configs:
  24ummBEhg4mA8DV1ojNjpHpQVipSiVZUB1zhcmgLF7woWFmgDz: # replace this with Blockchain ID we just obtained
    ethRPCAddr: http://10.153.238.182:8545
    ethWSAddr: ws://10.153.238.182:8546

...

avalanchego_vms_list:
  tokenvm:
    # download_url and path are mutually exclusive
    download_url: https://github.com/AnomalyFi/nodekit-seq/releases/download
    # path: "{{ inventory_dir }}/../../files" # tokenvm_0.0.666_linux_amd64.tar.gz
    id: tHBYNu8ikqo4MWMHehC9iKB9mR5tB3DWzbkYmTfe9buWQ5GZ8
    # Used in Ash CLI
    ash_vm_type: Custom
    binary_filename: tokenvm
    versions_comp:
      0.9.5: # <= version of Nodekit-Seq, you can find all the releases here: https://github.com/AnomalyFi/nodekit-seq/releases
        ge: 1.10.10
        le: 1.10.12
```

Then run 

```shell
ansible-playbook ash.avalanche.provision_nodes -i inventories/local
```

to start the subnet.

*Note that above code usually cannot launch the nodekit-seq blockchain, which is a unknown issue(might be timeout to syncstate) of hypersdk, we simply run*

```shell
ansible -i inventories/local all -b -m shell -a "sudo systemctl restart avalanchego"
```

which will restart all the avalanchego daemon in all the vms to resolve the issue

### Healthy check

To check if nodekit-seq is running expectedly, find corresponding nodekit-seq and download the nodekit-seq release [here](https://github.com/AnomalyFi/nodekit-seq/releases), decompress the release file then you will find a binary called `token-cli`

Run

```bash
token-cli chain import
chainID: 2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au # blockchain ID
✔ uri: http://10.252.190.111:9650/ext/bc/2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au
```

**Note:** `10.252.190.111` is the IP address of the `validator01` VM, you can get it with `terraform -chdir=terraform/multipass output`.

```bash
token-cli chain watch
database: .token-cli
available chains: 1 excluded: []
1) chainID: 2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au
select chainID: 0 [auto-selected]
uri: http://10.252.190.111:9650/ext/bc/2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au
Here is network Id: %d 12345
Here is uri: %s http://10.252.190.111:9650/ext/bc/2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au
watching for new blocks on 2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au 👀
height:54 l1head:%!s(int64=106) txs:0 root:kMYb8yTR9pbtfFs5hfuEZLDjVjWnepSjpRE3kkXrEeJ2JyPAA blockId:KSLxXyN7XT67n5ubbzHzW7afA6tTjn5hmyqxwr5o4JRSt5wGi size:0.10KB units consumed: [bandwidth=0 compute=0 storage(read)=0 storage(create)=0 storage(modify)=0] unit prices: [bandwidth=100 compute=100 storage(read)=100 storage(create)=100 storage(modify)=100]
height:55 l1head:%!s(int64=107) txs:0 root:23ArBGmR9DQQLab1icAGFZbKd941FdrZuEy5oY2Yj6ZtKDri9M blockId:22zLgkd5bDmgu2qHqDBYQognAktpnp946vHx1MxDGYG38WCZPe size:0.10KB units consumed: [bandwidth=0 compute=0 storage(read)=0 storage(create)=0 storage(modify)=0] unit prices: [bandwidth=100 compute=100 storage(read)=100 storage(create)=100 storage(modify)=100] [TPS:0.00 latency:110ms gap:2474ms]
....
```

## Deploy contracts on eth-l1 for op-l2

In the following, we will need rpc address and ws address of `eth-l1` and rpc address for `nodekit-seq`, you can set them as environment variables or simply replace them in the following commands

**In folder `op-integration`**

deploy contracts on eth-l1

```
python bedrock-devnet/main.py --monorepo-dir=. --deploy-contracts --l1-rpc-url="http://10.153.238.11:8545"
```

*Note that we need to pass the rpc address of `eth-l1` after the flag argument `--l1-rpc-url`*

## Deploy nodekit-l1

```
python bedrock-devnet/main.py --monorepo-dir=. --launch-nodekit-l1 --l1-rpc-url="http://10.153.238.182:8545" --seq-url="http://10.153.238.150:9650/ext/bc/24ummBEhg4mA8DV1ojNjpHpQVipSiVZUB1zhcmgLF7woWFmgDz"
```

## Launch l2

```
python bedrock-devnet/main.py --monorepo-dir=. --launch-l2 --l1-rpc-url="http://10.153.238.182:8545" --l1-ws-url="ws://10.153.238.182:8546" --seq-url="http://10.153.238.150:9650/ext/bc/24ummBEhg4mA8DV1ojNjpHpQVipSiVZUB1zhcmgLF7woWFmgDz"
```

