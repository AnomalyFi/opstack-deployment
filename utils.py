import os
import sys
import re
import time
import json
import typing
import subprocess
import requests
import yaml
import shutil

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

def setDefaultAvaNodesConfig(ansibleDir: str, inventoryDir: str):
    avaNodeConfLoc = pjoin(ansibleDir, inventoryDir, 'group_vars/avalanche_nodes.yml')
    with open(avaNodeConfLoc, 'r+') as f:
        nodeConf = yaml.safe_load(f)
        # clean existing tracked subnets and chain configs then assign new
        nodeConf['avalanchego_track_subnets'] = []

        # clean existing content
        f.truncate(0)
        f.seek(0)

        yaml.safe_dump(nodeConf, f)
    

# TODO: make config to a class then pass it
def updateTrackedSubnetNChainConfig(ansibleDir: str, inventoryDir: str, subnetID: str, chainID: str, ethl1IP: str):
    avaNodeConfLoc = pjoin(ansibleDir, inventoryDir, 'group_vars/avalanche_nodes.yml')
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
            'ethWSAddr': f'ws://{ethl1IP}:8546',
            'mempoolSize': 256,
            'archiverConfig': {
                'enabled': True,
                'archiverType': 'sqlite',
                'dsn': '/tmp/default.db',
            }
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

def deployContractsOnL1(opDir: str, l1RPC: str, nodekitContractAddr: str, l2ChainID: str='45200'):
    cmd = ['python', 'bedrock-devnet/main.py', '--monorepo-dir=.', '--deploy-contracts', f'--l1-rpc-url={l1RPC}', f'--l2-chain-id={l2ChainID}', f'--nodekit-contract={nodekitContractAddr}']
    cmdStr = ' '.join(cmd)
    print(cmdStr)
    sub = run_command(
        # TODO: to be removed since foundryrs by nix-foundryrs version is not correct and leads cast send to fail
        # ['nix-shell', '--run', cmdStr],
        cmd,
        capture_output=False,
        stderr=sys.stderr,
        stdout=sys.stdout,
        cwd=opDir
    )

    if sub.returncode != 0:
        raise Exception(f"unable to deploy contracts on ETH L1, reason: {sub.stderr}")

def deployNodekitL1(nodekit_l1_dir: str, 
                    seq_url: str,
                    l1_rpc: str,
                    commitment_contract_addr: str,
                    commitment_contract_wallet: str = 'ac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80',
                    l1_chain_id: str = '32382'):
    seq_chain_id: str = seq_url.split('/')[-1]

    env = {
        'SEQ_ADDR': seq_url,
        'CHAIN_ID': seq_chain_id,
        'CONTRACT_ADDR': commitment_contract_addr,
        # lstrip or `Failed to convert from hex to ECDSA: invalid hex character 'x' in private key`
        'CONTRACT_WALLET': commitment_contract_wallet.lstrip('0x'),
        'CHAIN_ID_L1': l1_chain_id,
        'L1_RPC': l1_rpc
    }

    print(f'using config to deploy nodekit l1: {env}')

    sub = run_command(['docker', 'compose', 'up', '-d'], cwd=nodekit_l1_dir, env=env, capture_output=False, stdout=sys.stdout, stderr=sys.stderr)

    if sub.returncode != 0:
        raise Exception(f'error deploying nodekit l1: {sub.stderr}')

def deployNodekitZKContracts(nodekitZKDir: str, l1PRC: str, mnenoic: str):
    sub = run_command([
            'forge', 'script', 'DeploySequencer', '--broadcast',
            '--rpc-url', l1PRC, '--legacy'
        ], env={
            'MNEMONIC': mnenoic
        }, cwd=nodekitZKDir, capture_output=False, stderr=sys.stderr, stdout=sys.stdout) 
    
    if sub.returncode != 0:
        raise Exception(f"error deploying nodekit zk contracts: {sub.stderr}")
    
# python 
# bedrock-devnet/main.py 
# --monorepo-dir=. 
# --launch-l2 
# --l1-rpc-url="http://10.153.238.182:8545" 
# --l1-ws-url="ws://10.153.238.182:8546"
# --seq-url="http://10.153.238.150:9650/ext/bc/24ummBEhg4mA8DV1ojNjpHpQVipSiVZUB1zhcmgLF7woWFmgDz"
def deployOPL2(opDir: str, gethProxyDir: str,l1RPC: str, l1WS: str, seqRPC: str, l2ChainID='45200', portIncrement=0):
    # for internal op-stack communication
    subnet = [172, 20]
    subnet[1] += portIncrement
    subnetStr = '.'.join([str(x) for x in subnet])

    # launch op-geth, op-node, op-proposer and op-batcher
    cmd = ['python', 
           'bedrock-devnet/main.py', 
           '--monorepo-dir=.', 
           '--launch-l2',
           f'--l1-rpc-url={l1RPC}',
           f"--l1-ws-url={l1WS}",
           f"--seq-url={seqRPC}",
           f"--l2-chain-id={l2ChainID}",
           f"--l2-provider-url=http://localhost:{19545+portIncrement}",
           f"--subnet={subnetStr}"
           ]
    
    cmdStr = ' '.join(cmd)
    print(cmdStr)
    configureOPL2Port(opDir, portIncrement)
    sub = run_command(
        # ['nix-shell', '--run', cmdStr],
        cmd,
        capture_output=False,
        stderr=sys.stderr,
        stdout=sys.stdout,
        cwd=opDir,
    )

    if sub.returncode != 0:
        raise Exception(f"unable to launch op stack, reason: {sub.stderr}")

    configureOpGethProxy(gethProxyDir, seqRPC, portIncrement)
    
    cmd = ['docker', 'compose', 'up', '-d']
    sub = run_command(
        cmd,
        stderr=sys.stderr,
        stdout=sys.stdout,
        cwd=gethProxyDir,
        env={
            'COMPOSE_PROJECT_NAME': f'proxy-{l2ChainID}'
        }
    )

def clean_op_deployment_temp_files(opDir: str):
    tempfile_dir = pjoin(opDir, '.devnet')
    os.system(f'rm {tempfile_dir}/*') 

def deployCelestiaLightNode(nodeStore: str = './.node-store', nodeVersion: str = 'v0.12.4', port: int = 26658, network: str = 'arabica', rpcUrl: str = 'validator-1.celestia-arabica-11.com'):
    # docker run -v $NODE_STORE:/home/celestia -p 26658:26658 -e NODE_TYPE=$NODE_TYPE -e P2P_NETWORK=$NETWORK \
    #     ghcr.io/celestiaorg/celestia-node:v0.12.4 \
    #     celestia $NODE_TYPE start --core.ip $RPC_URL --p2p.network $NETWORK --rpc.addr 0.0.0.0
    # cmd = ['sudo', 'mkdir', nodeStore]

    # sub = run_command(cmd, capture_output=True)
    # if sub.returncode != 0:
    #     print(f'unable to mkdir {nodeStore}, reason: {sub.stderr}')
    #     return

    # cmd = ['sudo', 'chmod', '777', nodeStore]
    # sub = run_command(cmd, capture_output=True)
    # if sub.returncode != 0:
    #     print(f'unable to give permission to {nodeStore}, reason: {sub.stderr}')
    #     return

    cmd = ['docker', 'run', '-v', f'{nodeStore}:/home/celestia', 
           '-p', f'{port}:26658', '-e', 'NODE_TYPE=light', 
           f'ghcr.io/celestiaorg/celestia-node:{nodeVersion}',
           'celestia', 'light', 'start', '--core.ip', rpcUrl, '--p2p.network', network, '--rpc.addr', '0.0.0.0']

    sub = run_command(cmd, capture_output=False, stderr=sys.stderr, stdout=sys.stdout)

    if sub.returncode != 0:
        print(f'unable to start node, reason: {sub.stderr}')
        return

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

def wait_seq(rpcURL: str, retry=10) -> bool:
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
    
def seq_healthy(rpcURL: str) -> bool:
    url = pjoin(rpcURL, 'coreapi')
    resp = requests.post(url=url,
        json={"id":1, "jsonrpc":"2.0", "method": "hypersdk.lastAccepted", "params":[]}) 

    if resp.status_code != 200:
        return False
    
    # fetch two blocks to check if running expectedly
    try:
        hStart = resp.json()['result']['height']
        time.sleep(5)
        resp = requests.post(url=url,
            json={"id":1, "jsonrpc":"2.0", "method": "hypersdk.lastAccepted", "params":[]}) 
        h = resp.json()['result']['height']

        if h > hStart:
            return True
        else:
            return False
    except Exception as e:
        print(f'erorr {e} happened when checking seq healthy')
        return False

    
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

def getChainInfo(ansibleDir: str, inventoryDir: str, terraformWorkingDir: str):
    confPath = pjoin(ansibleDir, inventoryDir, 'group_vars/avalanche_nodes.yml')
    ips = getValidatorIPs(terraformWorkingDir)
    with open(confPath, 'r') as f:
        conf = yaml.safe_load(f)
        chainID = list(conf['avalanchego_chains_configs'].keys())[0]
    
    return chainID, ips
        
def getNodekitZKContractAddr(zkDir: str, l1ChainID: str = '32382') -> str:
    zk_dir = zkDir
    l1_chain_id = l1ChainID
    latest_run_path = os.path.join(zk_dir, f'broadcast/Sequencer.s.sol/{l1_chain_id}/run-latest.json')

    with open(latest_run_path, 'r') as f:
        runinfo_str = f.read()
        runinfo = json.loads(runinfo_str)

        return runinfo['transactions'][0]['contractAddress']

def configureOPL2Port(opDir: str, portIncrement=0):
    envPath = pjoin(opDir, 'ops-bedrock/.env')

    defaultPortMapping = {
        'OP1_CHAIN_ID': 45200,
        'OP1_L2_RPC_PORT': 19545,
        'OP1_L2_P2P_PORT': 30303,
        'OP1_NODE_RPC_PORT': 18545,
        'OP1_NODE_P2P_PORT': 40404,
        'OP1_BATCHER_RPC_PORT': 17545,
        'OP1_PROPOSER_RPC_PORT': 16545,
        'OP1_GETH_PROXY_PORT': 9090,
    }

    for key in defaultPortMapping:
        defaultPortMapping[key] += portIncrement
    
    # TODO: use `write_dotenv_conf_to` after testing
    print(f'writing .env for op chain: {defaultPortMapping}')
    with open(envPath, 'w') as f:
        for key in defaultPortMapping:
            f.write(f'{key}={defaultPortMapping[key]}\n')

def configureOpGethProxy(gethProxyDir: str, seqRpc: str, portIncrement=0):
    envPath = pjoin(gethProxyDir, '.env')

    l2ChainID = 45200 + portIncrement
    seqChainID = seqRpc.split('/')[-1]

    config={
        'OP1_GETH_PROXY_PORT': f'{9090+portIncrement}',
        'OP1_L2_ADDR': f'http://host.docker.internal:{19545+portIncrement}',
        'OP1_CHAIN_ID': f'{l2ChainID}',
        'SEQ_CHAIN_ID': seqChainID,
        'SEQ_ADDR': seqRpc,
        'RETRY': '3',
    }
    
    write_dotenv_conf_to(config, envPath)

def write_dotenv_conf_to(conf, fname):
    with open(fname, 'w') as f:
        for key in conf:
            f.write(f'{key}={conf[key]}\n')

def ensureDir(dir: str):
    if not os.path.exists(dir):
        os.mkdir(dir)
        return

    if os.path.exists(dir) and not os.path.isdir(dir):
        raise Exception(f'path {dir} exists but is not a directory')

def saveOpDevnetInfo(opDir: str, storageDir: str, chainID: str):
    ensureDir(storageDir)
    envPath = pjoin(opDir, 'ops-bedrock/.env')
    infoDir = pjoin(opDir, '.devnet')
    targetDir = pjoin(storageDir, chainID)
    print(f'copying chain info from {infoDir} to {targetDir}')
    shutil.move(infoDir, targetDir)
    shutil.move(envPath, pjoin(targetDir, '.env'))

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