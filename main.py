import os
import time
import typer
from typing_extensions import Annotated
import utils
import websockets.sync.client as wsclient
import logging

app = typer.Typer()
state = {
    "ansibleDir": "ansible-avalanche-getting-started",
    "opDir": "op-integration",
    "cloudProvider": "multipass",
    "terraformWorkingDir": "ansible-avalanche-getting-started/terraform/multipass",
    "seqDownloadAddr": "https://github.com/AnomalyFi/nodekit-seq/releases/download",
    "seqVersion": "0.9.5",
    "inventoryDir": "inventories/local",
    "nodekitL1Dir": "nodekit-l1",
    "nodekitZKDir": "nodekit-zk",
    "mnenoic": "test test test test test test test test test test test junk",
    "l2storage": ".l2chains",

    # if manual is enabled, seq and eth ip will be overrided accordingly
    "manual": False,
    "ethL1IP": '',
    "seqRPC": '',
}


pjoin = os.path.join

@app.command()
def deploy():
    print('reset avalanche node config')
    utils.setDefaultAvaNodesConfig(state['ansibleDir'], state['inventoryDir'])

    print('deploying eth l1')
    utils.deployEthL1(state['ansibleDir'], state['inventoryDir'])
    ethL1IP = utils.getEthL1IP(state['terraformWorkingDir'])
    print('bootstraping avalanchego validators')
    utils.bootstrapValidators(state['ansibleDir'], state['inventoryDir'])
    # wait bootstraping to be stable
    print('boostraping finished, waiting 30s to let it become stable to bootstrap a subnet')
    time.sleep(30)
    print('creating nodekit-seq subnet, here we are not directing stdout and stderr since we need to capture output')
    log = utils.createAvalancheSubnet(state['ansibleDir'], state["inventoryDir"])
    chainID = utils.getChainIDFromCreationLog(log)
    subnetID = utils.getSubnetIDfromCreationLog(log)
    print(f'updating avalanche nodes config chainID: {chainID}, subnetID: {subnetID}, ETH L1 IP: {ethL1IP}')
    utils.updateTrackedSubnetNChainConfig(state['ansibleDir'], state['inventoryDir'], subnetID, chainID, ethL1IP)
    print('provision avalanche nodes to start nodekit-seq subnet')
    utils.provisionAvaNodes(state['ansibleDir'], state['inventoryDir'])

    validatorIPs = utils.getValidatorIPs(state['terraformWorkingDir'])
    seqRPCURL = f"http://{validatorIPs[0]}:9650/ext/bc/{chainID}"

    # default timeout is 10(times) x 5s
    seqIsUp = utils.wait_seq(seqRPCURL)
    cnt = 0
    retry = 3
    # must restart avalanchego at least once
    while not seqIsUp:
        utils.restartAvalancheGo(state['ansibleDir'], state['inventoryDir'])
        seqIsUp = utils.wait_seq(seqRPCURL)
        cnt += 1
        if cnt >= retry:
            print("cannot launch nodekit-seq")
        
    ethL1RPC = f'http://{ethL1IP}:8545'
    ethL1WS = f'ws://{ethL1IP}:8546'
    # deploy zk contracts
    utils.deployNodekitZKContracts(state['nodekitZKDir'], ethL1RPC, mnenoic='test test test test test test test test test test test junk')
    commitmentContractAddr = utils.getNodekitZKContractAddr(state['nodekitZKDir'])
    print(f'zk contract deployed addr: {commitmentContractAddr}')
    utils.deployNodekitL1(state['nodekitL1Dir'], seqRPCURL, ethL1RPC, commitmentContractAddr)
    print('nodekit l1 deployed')

    print('deploying op contracts')
    utils.deployContractsOnL1(state['opDir'], ethL1RPC)
    print('launching op stack')
    utils.deployOPL2(state['opDir'], ethL1RPC, ethL1WS, seqRPCURL)

@app.command()
def launch_l2(chain_id: str):
    validatorIPs = utils.getValidatorIPs(state['terraformWorkingDir'])
    seqRPCURL = f"http://{validatorIPs[0]}:9650/ext/bc/{chain_id}"
    ethL1IP = utils.getEthL1IP(state['terraformWorkingDir'])

    ethL1RPC = f'http://{ethL1IP}:8545'
    ethL1WS = f'ws://{ethL1IP}:8546'
    # utils.deployContractsOnL1(state['opDir'], ethL1RPC)
    utils.deployNodekitL1(state['opDir'], ethL1RPC, seqRPCURL)
    utils.deployOPL2(state['opDir'], ethL1RPC, ethL1WS, seqRPCURL)

@app.command()
def deploy_seq():
    print('reset avalanche node config')
    utils.setDefaultAvaNodesConfig(state['ansibleDir'], state['inventoryDir'])

    print('deploying eth l1')
    utils.deployEthL1(state['ansibleDir'], state['inventoryDir'])
    ethL1IP = utils.getEthL1IP(state['terraformWorkingDir'])
    print('bootstraping avalanchego validators')
    utils.bootstrapValidators(state['ansibleDir'], state['inventoryDir'])
    # wait bootstraping to be stable
    print('boostraping finished, waiting 30s to let it become stable to bootstrap a subnet')
    time.sleep(30)
    print('creating nodekit-seq subnet, here we are not directing stdout and stderr since we need to capture output')
    log = utils.createAvalancheSubnet(state['ansibleDir'], state["inventoryDir"])
    chainID = utils.getChainIDFromCreationLog(log)
    subnetID = utils.getSubnetIDfromCreationLog(log)
    print(f'updating avalanche nodes config chainID: {chainID}, subnetID: {subnetID}, ETH L1 IP: {ethL1IP}')
    utils.updateTrackedSubnetNChainConfig(state['ansibleDir'], state['inventoryDir'], subnetID, chainID, ethL1IP)
    print('provision avalanche nodes to start nodekit-seq subnet')
    utils.provisionAvaNodes(state['ansibleDir'], state['inventoryDir'])

    validatorIPs = utils.getValidatorIPs(state['terraformWorkingDir'])
    seqRPCURL = f"http://{validatorIPs[0]}:9650/ext/bc/{chainID}"

    # default timeout is 10(times) x 5s
    seqIsUp = utils.wait_seq(seqRPCURL)
    cnt = 0
    retry = 3
    # must restart avalanchego at least once
    while not seqIsUp:
        utils.restartAvalancheGo(state['ansibleDir'], state['inventoryDir'])
        seqIsUp = utils.wait_seq(seqRPCURL)
        cnt += 1
        if cnt >= retry:
            print("cannot launch nodekit-seq")

    print(f'Deployed L1 at IP: {ethL1IP}, with default ports 8545 and 8546')
    print(f'Deployed Seq with IPs: {validatorIPs}')
    
@app.command()
def deploy_zk_contracts():
    l1IP = utils.getEthL1IP(state['terraformWorkingDir'])
    ethL1RPC = f'http://{l1IP}:8545'
    utils.deployNodekitZKContracts(state['nodekitZKDir'], ethL1RPC, mnenoic='test test test test test test test test test test test junk')
    addr = utils.getNodekitZKContractAddr(state['nodekitZKDir'])
    print(f'zk deployed addr: {addr}')

@app.command()
def deploy_op_contracts(l2_chain_id='45200'):
    ethL1IP = getETHIP()
    ethL1RPC = f'http://{ethL1IP}:8545'
    commitmentAddr = utils.getNodekitZKContractAddr(state['nodekitZKDir'])
    utils.deployContractsOnL1(state['opDir'], ethL1RPC, commitmentAddr, l2ChainID=l2_chain_id)

@app.command()
def deploy_nodekit_l1():
    chainID, ips = utils.getChainInfo(state['ansibleDir'], state['inventoryDir'], state['terraformWorkingDir'])
    seqRPCUrl = f'http://{ips[0]}:9650/ext/bc/{chainID}'
    commitmentAddr = utils.getNodekitZKContractAddr(state['nodekitZKDir'])
    ethL1IP = utils.getEthL1IP(state['terraformWorkingDir'])
    ethL1RPC = f'http://{ethL1IP}:8545'

    utils.deployNodekitL1(state['nodekitL1Dir'], seqRPCUrl, ethL1RPC, commitmentAddr)

@app.command()
def deploy_op_l2(l2_chain_id='45200'):
    if state['manual']:
        seqRPCURL = state['seqRPC']
    else:
        chainID, validatorIPs = utils.getChainInfo(state['ansibleDir'], state['inventoryDir'], state['terraformWorkingDir'])
        seqRPCURL = f"http://{validatorIPs[0]}:9650/ext/bc/{chainID}"


    ethL1IP = getETHIP()
    ethL1RPC = f'http://{ethL1IP}:8545'
    ethL1WS = f'ws://{ethL1IP}:8546'

    utils.deployOPL2(state['opDir'], ethL1RPC, ethL1WS, seqRPCURL, l2ChainID=l2_chain_id)

@app.command()
def deploy_op_chain(inc: int = 0):
    l2_chain_id = str(45200 + inc)
    print(f'deploying op chain with chainID: {l2_chain_id}')
    # deploy op contracts
    ethL1IP = getETHIP()
    ethL1RPC = f'http://{ethL1IP}:8545'
    ethL1WS = f'ws://{ethL1IP}:8546'
    seqRPCURL = getSeqRPC()

    print('deploying op contracts')
    commitmentAddr = utils.getNodekitZKContractAddr(state['nodekitZKDir'])
    utils.deployContractsOnL1(state['opDir'], ethL1RPC, commitmentAddr, l2ChainID=l2_chain_id)
    print('deploying op l2')
    utils.deployOPL2(state['opDir'], ethL1RPC, ethL1WS, seqRPCURL, l2ChainID=l2_chain_id, portIncrement=inc)

    utils.saveOpDevnetInfo(state['opDir'], state['l2storage'], l2_chain_id)

@app.command()
def launch_celestia_light():
    utils.deployCelestiaLightNode() 

@app.command()
def create_ava_subnet():
    log = utils.createAvalancheSubnet(state['ansibleDir'], state['inventoryDir'])
    print(log)
    
@app.command()
def restart_avalanchego():
    utils.restartAvalancheGo(state['ansibleDir'], state['inventoryDir'])

@app.command()
def hello(name: str):
    print(f"hello {name}")

@app.command()
def get_eth_l1_ip():
    ip = utils.getEthL1IP(state['terraformWorkingDir'])
    print(f'ip: {ip}')

@app.command()
def get_validator_ips():
    ips = utils.getValidatorIPs(state['terraformWorkingDir'])
    print(f"ips :{ips}")

@app.command()
def seq_info():
    rpcEndpoint = 'http://{ip}:9650/ext/bc/{id}'

    chainID, ips = utils.getChainInfo(state['ansibleDir'], state['inventoryDir'], state['terraformWorkingDir'])

    print(f'ChainID: {chainID}')
    print('api endpoints:')
    for ip in ips:
        print(rpcEndpoint.format(ip=ip, id=chainID))


@app.command()
def init():
    utils.download_seq(state['seqDownloadAddr'], state['seqVersion'])

@app.command()
def flags():
    print(state) 

@app.command()
def seq_healthy(url: str):
    print(utils.seq_healthy(url))

@app.callback()
def main(
    manual: bool = typer.Option(
        prompt="manually input seq info and eth info, usually needed when you deploy the other rollup on another machine", 
        prompt_required=False,
        default=False),
    eth_ip: str = typer.Option(
        prompt="eth l1 ip", 
        prompt_required=False,
        default='127.0.0.1'),
    seq_rpc: str = typer.Option(
        prompt="nodekit seq rpc", 
        prompt_required=False,
        default='http://52.206.11.137:9650/ext/bc/2ArqB8j5FWQY9ZBtA3QFJgiH9EmXzbqGup5kuyPQZVZcL913Au'),
    ansibleDir: str = typer.Option(
        prompt="the ansible-avalanche-getting-started repository dir", 
        prompt_required=False,
        default="ansible-avalanche-getting-started"),
    cloudProvider: str = typer.Option(
        prompt="the provider that deployed the vm instances",
        prompt_required=False,
        default="multipass"
    ),
    # inventoryDir: str = typer.Option(
    #     prompt="inventory folder of ansible configs",
    #     prompt_required=False,
    #     default="inventories/local"
    # ),
    seqDownloadAddr: str = typer.Option(
        prompt="nodekit-seq downloading address",
        prompt_required=False,
        default="https://github.com/AnomalyFi/nodekit-seq/releases/download"
    ),
    seqVersion: str = typer.Option(
        prompt="nodekit-seq version",
        prompt_required=False,
        default="0.9.7"
    ),
):
    if cloudProvider == "multipass":
        terraformWorkingDir = pjoin(ansibleDir, "terraform/multipass")
        inventoryDir = "inventories/local"
        print('using multipass cloud provider')
    elif cloudProvider == "aws":
        terraformWorkingDir = pjoin(ansibleDir, "terraform/aws")
        inventoryDir = "inventories/aws"
        print('using aws cloud provider')
    else:
        raise Exception("unsupported cloud provider")
    
    if manual:
        print(f'using manual mode, setting eth ip to {eth_ip}, seq rpc url to {seq_rpc}')
        state['ethL1IP'] = eth_ip
        state['seqRPC'] = seq_rpc

    state["ansibleDir"] = ansibleDir
    state['cloudProvider'] = cloudProvider
    state["terraformWorkingDir"] = terraformWorkingDir
    state['seqDownloadAddr'] = seqDownloadAddr
    state['seqVersion'] = seqVersion
    state['inventoryDir'] = inventoryDir
    state['manual'] = manual


def getETHIP():
    if state['manual']:
        l1IP = state['ethL1IP']
    else:
        l1IP = utils.getEthL1IP(state['terraformWorkingDir'])

    return l1IP

@app.command()
def getSeqRPC():
    if state['manual']:
        seqRPCURL = state['seqRPC']
    else:
        chainID, validatorIPs = utils.getChainInfo(state['ansibleDir'], state['inventoryDir'], state['terraformWorkingDir'])
        seqRPCURL = f"http://{validatorIPs[0]}:9650/ext/bc/{chainID}"
    
    print(seqRPCURL)
    return seqRPCURL

if __name__ == "__main__":
    app()