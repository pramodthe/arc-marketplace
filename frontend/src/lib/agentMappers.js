const CARD_GRADIENTS = [
  "from-sky-400/30 via-cyan-300/10 to-transparent",
  "from-indigo-500/30 via-violet-400/10 to-transparent",
  "from-amber-400/30 via-orange-400/10 to-transparent",
  "from-red-500/30 via-red-400/10 to-transparent",
  "from-teal-400/30 via-cyan-300/10 to-transparent",
  "from-violet-400/30 via-fuchsia-400/10 to-transparent",
]

function formatShortAddress(value) {
  if (!value) return "Pending"
  if (value.length <= 10) return value
  return `${value.slice(0, 4)}...${value.slice(-4)}`
}

function toTitleCase(value) {
  return value
    .split(/[-_ ]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ")
}

function formatOfferingType(value) {
  const normalized = String(value || "agent").toLowerCase()
  if (normalized === "mcp_service") return "MCP Service"
  return toTitleCase(normalized)
}

function initialsFromName(name) {
  return (
    name
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "AG"
  )
}

function normalizeStatus(status) {
  if (!status) return "Active"
  const normalized = status.toLowerCase()
  if (normalized === "created") return "Created"
  if (normalized === "draft") return "Draft"
  if (normalized === "registered") return "Registered"
  if (normalized === "inactive") return "Inactive"
  return "Active"
}

function formatPrice(value) {
  const number = Number(value)
  if (!Number.isFinite(number)) return "0.00"
  return number.toFixed(number < 0.01 && number > 0 ? 6 : 2)
}

export function makeAgentCompositeId(sellerId, agentId) {
  return `${sellerId}:${agentId}`
}

export function mapMarketplaceAgentsToCards(marketplaceAgents) {
  return marketplaceAgents.map((entry, index) => {
    const seller = entry.seller || {}
    const commerce = entry.commerce || {}
    const arc = entry.arc || {}
    const tools = entry.tools || []
    const minPrice = Number(commerce.minPriceUSDC || 0)
    const category = entry.category || "General"
    const offeringType = entry.offeringType || "agent"
    const protocolType = entry.protocolType || "http"
    const endpointHost = entry.endpointHost || "Endpoint unavailable"
    const tags = Array.from(
      new Set([category, ...tools.map((tool) => toTitleCase(tool.toolKey || tool.name || ""))].filter(Boolean)),
    )

    return {
      id: entry.id || makeAgentCompositeId(entry.sellerId, entry.agentId),
      sellerId: entry.sellerId,
      agentId: entry.agentId,
      name: entry.name || "Unnamed Agent",
      avatarImage: entry.iconDataUrl || "",
      shortAddress: arc.agentId ? `Arc #${arc.agentId}` : formatShortAddress(String(entry.agentId || "")),
      wallet: seller.walletAddress || "Wallet pending",
      owner: seller.name || "Unknown seller",
      authority: seller.validatorWalletAddress || "Validator pending",
      assetType: `${formatOfferingType(offeringType)} (${String(protocolType).toUpperCase()})`,
      status: normalizeStatus(entry.status),
      description: entry.description || "No description provided.",
      tags: Array.from(new Set([...(tags.length ? tags : ["General"]), formatOfferingType(offeringType), String(protocolType).toUpperCase()])),
      categoryBadges: [
        category.toUpperCase(),
        `${formatPrice(minPrice)} USDC`,
        arc.registered ? "ARC REGISTERED" : "ARC PENDING",
      ],
      avatar: initialsFromName(entry.name || ""),
      color: CARD_GRADIENTS[index % CARD_GRADIENTS.length],
      holdings: [{ amount: String(commerce.toolCount || tools.length), symbol: "TOOLS" }],
      toolCount: commerce.toolCount || tools.length,
      token: arc.agentId || "Pending Arc ID",
      paymentProtocol: commerce.paymentProtocol === "arc-usdc" ? "Arc USDC Settlement" : "x402 Pending",
      registries: ["Arc ERC-8004", "A2A Discovery", "Circle Wallets"],
      explorerLabel: "Copy Invoke URL",
      marketLabel: "Invoke Tool",
      rawMetadata: JSON.stringify(entry, null, 2),
      editable: false,
      invokePath: tools[0]?.invokePath || "",
      tools,
      profile: {
        category,
        offeringType,
        protocolType,
        services: tools.length ? tools.map((tool) => tool.name) : [entry.name || "Provider endpoint"],
        apiBaseUrl: endpointHost,
        apiDocsUrl: entry.apiDocsUrl || "",
        endpointUrl: entry.endpointUrl || "",
        httpMethod: entry.httpMethod || "POST",
        healthStatus: entry.healthStatus || "unchecked",
        pricingModel: commerce.pricingModel || "On-chain metered",
        basePriceUsdc: formatPrice(minPrice),
        trustSignals: [
          arc.registered ? "Arc ERC-8004 registered" : "Arc registration pending",
          commerce.paymentProtocol === "arc-usdc" ? "Real Arc USDC settlement" : "Payment pending",
        ],
        arcAgentId: arc.agentId || "",
        identityTxHash: arc.identityTxHash || "",
        network: arc.network || "Arc Testnet",
      },
      searchableText: [
        entry.name,
        entry.description,
        category,
        endpointHost,
        seller.name,
        seller.walletAddress,
        tools.map((tool) => tool.name).join(" "),
      ]
        .join(" ")
        .toLowerCase(),
    }
  })
}
