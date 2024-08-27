CHAINID=$1

PWD=$(pwd)
OP_BEDROCK="$PWD/op-integration/ops-bedrock"
GETH_PROXY="$PWD/op-geth-proxy"
BUILDER="$PWD/javelin-op-stack"
DEVNET_DIR="$PWD/op-integration/.devnet"

rm -rf $DEVNET_DIR

cd $OP_BEDROCK
docker compose -p "op-devnet_$CHAINID" down -v

cd $GETH_PROXY
docker compose -p "proxy-$CHAINID" down -v

cd $BUILDER
docker compose -p "builder-$CHAINID" down -v
