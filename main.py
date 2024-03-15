import os
import time
import typer
from typing_extensions import Annotated
import utils

app = typer.Typer()
state = {
    "ansibleDir": "ansible-avalanche-getting-started",
    "cloudProvider": "multipass",
    "terraformWorkingDir": "ansible-avalanche-getting-started/terraform/multipass",
    "seqDownloadAddr": "https://github.com/AnomalyFi/nodekit-seq/releases/download",
    "seqVersion": "0.9.5",
    "inventoryDir": "inventories/local"
}


pjoin = os.path.join

@app.command()
def deploy():
    print('deploying eth l1')
    utils.deployEthL1(state['ansibleDir'], state['inventoryDir'])
    return
    ethL1IP = utils.getEthL1IP(state['terraformWorkingDir'])
    print('bootstraping avalanchego validators')
    utils.bootstrapValidators(state['ansibleDir'], state['inventoryDir'])
    print('creating nodekit-seq subnet')
    log = utils.createAvalancheSubnet(state['ansibleDir'], state["inventoryDir"])
    chainID = utils.getChainIDFromCreationLog(log)
    subnetID = utils.getSubnetIDfromCreationLog(log)
    print(f'updating avalanche nodes config chainID: {chainID}, subnetID: {subnetID}, ETH L1 IP: {ethL1IP}')
    utils.updateTrackedSubnetNChainConfig(state['ansibleDir'], state['inventoryDir'], subnetID, chainID, ethL1IP)
    print('provision avalanche nodes to start nodekit-seq subnet')
    utils.provisionAvaNodes(state['ansibleDir'], state['inventoryDir'])

    validatorIPs = utils.getValidatorIPs(state['terraformWorkingDir'])
    seqRPCURL = f"http://{validatorIPs[0]}:9650/ext/bc/{chainID}"

    seqIsUp = False
    cnt = 0
    retry = 3
    while not seqIsUp:
        utils.restartAvalancheGo(state['ansibleDir'], state['inventoryDir'])
        seqIsUp = utils.wait_seq(seqRPCURL)
        cnt += 1
        if cnt > retry:
            print("cannot launch nodekit-seq")

    

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
def init():
    utils.download_seq(state['seqDownloadAddr'], state['seqVersion'])

@app.command()
def flags():
    print(state) 

@app.callback()
def main(
    ansibleDir: str = typer.Option(
        prompt="the ansible-avalanche-getting-started repository dir", 
        prompt_required=False,
        default="ansible-avalanche-getting-started"),
    cloudProvider: str = typer.Option(
        prompt="the provider that deployed the vm instances",
        prompt_required=False,
        default="multipass"
    ),
    inventoryDir: str = typer.Option(
        prompt="inventory folder of ansible configs",
        prompt_required=False,
        default="inventories/local"
    ),
    seqDownloadAddr: str = typer.Option(
        prompt="nodekit-seq downloading address",
        prompt_required=False,
        default="https://github.com/AnomalyFi/nodekit-seq/releases/download"
    ),
    seqVersion: str = typer.Option(
        prompt="nodekit-seq version",
        prompt_required=False,
        default="0.9.5"
    ),
):
    if cloudProvider == "multipass":
        terraformWorkingDir = pjoin(ansibleDir, "terraform/multipass")
    elif cloudProvider == "aws":
        terraformWorkingDir = pjoin(ansibleDir, "terraform/aws")
    else:
        raise Exception("unsupported cloud provider")

    state["ansibleDir"] = ansibleDir
    state['cloudProvider'] = cloudProvider
    state["terraformWorkingDir"] = terraformWorkingDir
    state['seqDownloadAddr'] = seqDownloadAddr
    state['seqVersion'] = seqVersion
    state['inventoryDir'] = inventoryDir

if __name__ == "__main__":
    app()