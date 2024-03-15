import os
import sys
import re
import time
import json
import typing
import subprocess
import requests
import yaml

pjoin = os.path.join

def deployEthL1(ansibleDir: str, inventoryDir: str):
    ansiblePlaybookBin = '.venv/bin/ansible-playbook'
    playbook = 'playbooks/local_ethereum.yml'
    sub = run_command(
        [ansiblePlaybookBin, playbook, '-i', inventoryDir],
        cwd=ansibleDir,
        capture_output=False,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    if sub.returncode != 0:
        raise Exception(f"unable to launch eth-l1, reason: {sub.stderr}")
    
def bootstrapValidators(ansibleDir: str, inventoryDir: str):
    ansiblePlaybookBin = '.venv/bin/ansible-playbook'
    playbook = 'ash.avalanche.bootstrap_local_network'
    sub = run_command(
        [ansiblePlaybookBin, playbook, '-i', inventoryDir],
        cwd=ansibleDir,
        capture_output=False,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    if sub.returncode != 0:
        raise Exception(f"unable to bootstrap avalanche nodes, reason: {sub.stderr}")

def createAvalancheSubnet(ansibleDir: str, inventoryDir: str) -> str:
    ansiblePlaybookBin = '.venv/bin/ansible-playbook'
    playbook = 'ash.avalanche.create_subnet'
    sub = run_command(
        [ansiblePlaybookBin, playbook, '-i', inventoryDir],
        cwd=ansibleDir,
        capture_output=True,
    )

    if sub.returncode != 0:
        raise Exception(f" unable to create nodekit-seq subnet, reason: {sub.stderr}")
    
    return sub.stdout.decode('utf-8')

def updateTrackedSubnetNChainConfig(ansibleDir: str, inventoryDir: str, subnetID: str, chainID: str, ethl1IP: str):
    avaNodeConfLoc = pjoin(ansibleDir, inventoryDir, 'group_vars/avalanche_nodes.yml')
    print(avaNodeConfLoc)
    with open(avaNodeConfLoc, 'r+') as f:
        nodeConf = yaml.safe_load(f)
        # clean existing tracked subnets and chain configs then assign new
        nodeConf['avalanchego_track_subnets'] = [subnetID]
        nodeConf['avalanchego_subnets_configs'] = {}
        nodeConf['avalanchego_subnets_configs'][subnetID] = {
            'proposerMinBlockDelay': 0,
            'proposerNumHistoricalBlocks': 5000,
            'consensusParameters': {
                'maxItemProcessingTime': 300000000000
            }
        }

        nodeConf['avalanchego_chains_configs'] = {}
        nodeConf['avalanchego_chains_configs'][chainID] = {
            'ethRPCAddr': f'http://{ethl1IP}:8545',
            'ethWSAddr': f'ws://{ethl1IP}:8546'
        }

        # clean existing content
        f.truncate(0)
        f.seek(0)

        yaml.safe_dump(nodeConf, f)

def provisionAvaNodes(ansibleDir: str, inventoryDir: str):
    ansiblePlaybookBin = '.venv/bin/ansible-playbook'
    playbook = 'ash.avalanche.provision_nodes'
    sub = run_command(
        [ansiblePlaybookBin, playbook, '-i', inventoryDir],
        cwd=ansibleDir,
        capture_output=False,
        stdout=sys.stdout,
        stderr=sys.stderr
    )

    if sub.returncode != 0:
        raise Exception(f" unable to provision avalanche nodes, reason: {sub.stderr}")

def restartAvalancheGo(ansibleDir: str, inventoryDir: str):
    ansibleBin = '.venv/bin/ansible'
    try:
        run_command(
            [ansibleBin, '-i', inventoryDir, 'all', '-b', '-m', 'shell', '-a', "sudo systemctl restart avalanchego"],
            cwd=ansibleDir,
            stdout=sys.stdout,
            stderr=sys.stderr
        )
        # eth-l1 vm doesn't not contain avalanchego so there will be error executing the binary
    except Exception as e:
        pass

def deployContractsOnL1(opDir: str, l1RPC: str):
    cmd = ['python', 'bedrock-devnet/main.py', '--monorepo-dir=.', '--deploy-contracts', f'--l1-rpc-url={l1RPC}']
    sub = run_command(
        ['nix-shell', '--run', ' '.join(cmd)],
        capture_output=False,
        stderr=sys.stderr,
        stdout=sys.stdout,
        cwd=opDir
    )

    if sub.returncode != 0:
        raise Exception(f"unable to deploy contracts on ETH L1, reason: {sub.stderr}")

# python bedrock-devnet/main.py 
# --monorepo-dir=. 
# --launch-nodekit-l1 
# --l1-rpc-url="http://10.153.238.182:8545" 
# --seq-url="http://10.153.238.150:9650/ext/bc/24ummBEhg4mA8DV1ojNjpHpQVipSiVZUB1zhcmgLF7woWFmgDz"
def deployNodekitL1(opDir: str, l1RPC: str, seqRPC: str):
    cmd = ['python', 
           'bedrock-devnet/main.py', 
           '--monorepo-dir=.', 
           '--launch-nodekit-l1',
           f'--l1-rpc-url={l1RPC}',
           f"--seq-url={seqRPC}"]
    sub = run_command(
        ['nix-shell', '--run', ' '.join(cmd)],
        capture_output=False,
        stderr=sys.stderr,
        stdout=sys.stdout,
        cwd=opDir
    )

    if sub.returncode != 0:
        raise Exception(f"unable to deploy contracts on ETH L1, reason: {sub.stderr}")
    
# python 
# bedrock-devnet/main.py 
# --monorepo-dir=. 
# --launch-l2 
# --l1-rpc-url="http://10.153.238.182:8545" 
# --l1-ws-url="ws://10.153.238.182:8546"
# --seq-url="http://10.153.238.150:9650/ext/bc/24ummBEhg4mA8DV1ojNjpHpQVipSiVZUB1zhcmgLF7woWFmgDz"
def deployOPL2(opDir: str, l1RPC: str, l1WS: str, seqRPC: str):
    cmd = ['python', 
           'bedrock-devnet/main.py', 
           '--monorepo-dir=.', 
           '--launch-l2',
           f'--l1-rpc-url={l1RPC}',
           f"--l1-ws-url={l1WS}"
           f"--seq-url={seqRPC}"]

    sub = run_command(
        ['nix-shell', '--run', ' '.join(cmd)],
        capture_output=False,
        stderr=sys.stderr,
        stdout=sys.stdout,
        cwd=opDir
    )

    if sub.returncode != 0:
        raise Exception(f"unable to deploy contracts on ETH L1, reason: {sub.stderr}")
    

def download_seq(download_url: str, version: str):
    file = f"tokenvm_{version}_linux_amd64.tar.gz"
    # e.g. https://github.com/AnomalyFi/nodekit-seq/releases/download/v0.9.5/tokenvm_0.9.5_linux_amd64.tar.gz
    url = pjoin(download_url, f"v{version}", file) 
    binDir = ".venv/bin"

    print(f'downloading nodekit binaries, version: {version}')
    # download to /tmp
    sub = run_command(
        ["wget", url, "-P", "/tmp"],
        capture_output=True
    )
    print(f'download finished')

    if sub.returncode != 0:
        raise Exception(f"cannot download nodekit binaries, reason: {sub.stderr}")
    
    print('extracting binaries')
    sub = run_command(
        ["tar", "-xzf", f"/tmp/{file}", "-C", binDir],
        capture_output=True
    )
    print('extraction finished')

    if sub.returncode != 0:
        raise Exception(f"cannot untar nodekit files, reason: {sub.stderr}")


def wait_seq(rpcURL: str, retry=180) -> bool:
    cnt = 0
    while True:
        print(f'cheaking if seq is launched ({cnt}/{retry})')
        healthy = seq_healthy(rpcURL) 
        if healthy:
            return True
        else:
            cnt += 1
            time.sleep(1) 
        
        if cnt >= retry:
            return False
    
# TODO: fetch some blocks here
def seq_healthy(rpcURL: str) -> bool:
    resp = requests.post(url=rpcURL,
        json={"id":1, "jsonrpc":"2.0", "method": "hypersdk.network", "params":[]}) 
    
    if resp.status_code != 200:
        return False

    return True

    
def getChainIDFromCreationLog(log: str) -> str:
    # TODO: more elligant regex is needed
    p1 = re.compile(r'TASK \[Display Subnet information\](.|\n)*(?:TASK)')
    matches = p1.search(log)
    subnetInfoChunk = matches[0]
    p2 = re.compile(r'msg:(.|\n)*(?:\n)')
    matches = p2.search(subnetInfoChunk)
    # should in format like 
    # msg: 
    #   blockchains:
    #   - id: xxx
    #     subnetID: xxx
    # ...
    subnetInfo = matches[0]
    y = yaml.safe_load(subnetInfo)

    chainID = y['msg']['blockchains'][0]['id']
    return chainID

def getSubnetIDfromCreationLog(log: str) -> str:
    p1 = re.compile(r'TASK \[Display Subnet information\](.|\n)*(?:TASK)')
    matches = p1.search(log)
    subnetInfoChunk = matches[0]
    p2 = re.compile(r'msg:(.|\n)*(?:\n)')
    matches = p2.search(subnetInfoChunk)
    # should in format like 
    # msg: 
    #   blockchains:
    #   - id: xxx
    #     subnetID: xxx
    # ...
    subnetInfo = matches[0]
    y = yaml.safe_load(subnetInfo)

    subnetID = y['msg']['blockchains'][0]['subnetID']
    return subnetID


def getEthL1IP(terraformWorkingDir: str) -> str:
    sub = run_command(
        ['terraform', f'-chdir={terraformWorkingDir}', 'output', '-json'],
        capture_output=True
    )

    terraOut = json.loads(sub.stdout)
    ethL1IP = terraOut['frontend_ip']['value']

    return ethL1IP

def getValidatorIPs(terraformWorkingDir: str) -> typing.List[str]:
    sub = run_command(
        ['terraform', f'-chdir={terraformWorkingDir}', 'output', '-json'],
        capture_output=True
    )

    terraOut = json.loads(sub.stdout)
    validatorIPs = terraOut['validators_ips']['value']

    return validatorIPs


def run_command(args, check=True, shell=False, cwd=None, env=None, timeout=None, capture_output=False, stdout=None , stderr=None):
    env = env if env else {}
    return subprocess.run(
        args,
        check=check,
        shell=shell,
        capture_output=capture_output,
        env={
            **os.environ,
            **env
        },
        cwd=cwd,
        timeout=timeout,
        stdout=stdout,
        stderr=stderr
    )