CHAINID=$1

PWD=$(pwd)
OP_BEDROCK="$PWD/op-integration/ops-bedrock"
GETH_PROXY="$PWD/op-geth-proxy"
BUILDER="$PWD/javelin-op-stack"
DEVNET_DIR="$PWD/op-integration/.devnet"
APISERVER_DIR="$PWD/hyperlane-javelin"
FAUCET_NAME="faucet-$CHAINID"

rm -rf $DEVNET_DIR

cd $OP_BEDROCK
docker compose -p "op-devnet_$CHAINID" down -v

cd $GETH_PROXY
docker compose -p "proxy-$CHAINID" down -v

cd $BUILDER
docker compose -p "builder-$CHAINID" down -v

cd $JAVELIN_RPC_DIR
docker compose down -v

cd $APISERVER_DIR
docker compose -p "apiserver-$CHAINID" down -v

docker stop $FAUCET_NAME
docker rm $FAUCET_NAME
