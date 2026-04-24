#!/usr/bin/env node

const action = process.argv[2];

function readPayload() {
  const raw = process.env.ARC_BRIDGE_WORKER_PAYLOAD || "{}";
  return JSON.parse(raw);
}

function writeJson(payload) {
  process.stdout.write(
    `${JSON.stringify(payload, (_, value) => (typeof value === "bigint" ? value.toString() : value))}\n`,
  );
}

function fail(message, status = 1) {
  writeJson({ error: message });
  process.exit(status);
}

function validatePayload(payload) {
  const required = ["sourceChain", "destinationChain", "destinationAddress", "amountUSDC"];
  for (const key of required) {
    if (!payload[key]) fail(`Missing required bridge payload field: ${key}`);
  }
  if (payload.destinationChain !== "Arc_Testnet") {
    fail("External buyer funding must settle to Arc_Testnet");
  }
}

function mockResult(payload, state = "success") {
  const txHash = `0x${"1".repeat(64)}`;
  return {
    amount: payload.amountUSDC,
    token: "USDC",
    state,
    provider: "MockArcAppKitBridge",
    source: {
      address: "mock-source-address",
      chain: { chain: payload.sourceChain },
    },
    destination: {
      address: payload.destinationAddress,
      chain: { chain: payload.destinationChain },
    },
    config: { transferSpeed: payload.transferSpeed || "FAST" },
    steps: [
      {
        name: "mockBridge",
        state,
        txHash,
        explorerUrl: `https://testnet.arcscan.app/tx/${txHash}`,
      },
    ],
  };
}

async function run() {
  if (!["estimate", "bridge"].includes(action)) {
    fail("Usage: node arc_app_kit_bridge_worker.mjs <estimate|bridge>");
  }

  const payload = readPayload();
  validatePayload(payload);

  if (process.env.ARC_BRIDGE_WORKER_MODE === "mock") {
    if (action === "estimate") {
      writeJson({
        mode: "mock",
        sourceChain: payload.sourceChain,
        destinationChain: payload.destinationChain,
        destinationAddress: payload.destinationAddress,
        amountUSDC: payload.amountUSDC,
        token: "USDC",
        transferSpeed: payload.transferSpeed || "FAST",
        fees: [],
        gas: [],
      });
      return;
    }
    writeJson({ mode: "mock", bridgeResult: mockResult(payload) });
    return;
  }

  const [{ AppKit }, { createViemAdapterFromPrivateKey }] = await Promise.all([
    import("@circle-fin/app-kit"),
    import("@circle-fin/adapter-viem-v2"),
  ]).catch((error) => {
    fail(`Arc App Kit bridge dependencies are not installed: ${error.message}`);
  });

  const privateKey = process.env.ARC_BRIDGE_EVM_PRIVATE_KEY || process.env.PRIVATE_KEY;
  if (!privateKey) {
    fail("ARC_BRIDGE_EVM_PRIVATE_KEY or PRIVATE_KEY is required for real EVM bridge execution");
  }

  const kit = new AppKit();
  const adapter = createViemAdapterFromPrivateKey({ privateKey });
  const params = {
    from: { adapter, chain: payload.sourceChain },
    to: {
      chain: payload.destinationChain,
      recipientAddress: payload.destinationAddress,
      useForwarder: true,
    },
    amount: payload.amountUSDC,
    token: "USDC",
    config: { transferSpeed: payload.transferSpeed || "FAST" },
    invocationMeta: payload.transferRef ? { traceId: payload.transferRef } : undefined,
  };

  if (action === "estimate") {
    const estimate = typeof kit.estimateBridge === "function"
      ? await kit.estimateBridge(params)
      : await kit.estimate(params);
    writeJson(estimate);
    return;
  }

  const bridgeResult = await kit.bridge(params);
  writeJson({ bridgeResult });
}

run().catch((error) => fail(error instanceof Error ? error.message : String(error)));
