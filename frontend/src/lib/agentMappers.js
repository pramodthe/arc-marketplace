const CARD_GRADIENTS = [
  "from-sky-400/30 via-cyan-300/10 to-transparent",
  "from-indigo-500/30 via-violet-400/10 to-transparent",
  "from-amber-400/30 via-orange-400/10 to-transparent",
  "from-red-500/30 via-red-400/10 to-transparent",
  "from-teal-400/30 via-cyan-300/10 to-transparent",
  "from-violet-400/30 via-fuchsia-400/10 to-transparent",
]

function formatShortAddress(value) {
  const text = value == null ? "" : String(value).trim()
  if (!text) return "Pending"
  if (text.length <= 10) return text
  return `${text.slice(0, 4)}...${text.slice(-4)}`
}

function toTitleCase(value) {
  const text = value == null ? "" : String(value).trim()
  if (!text) return ""
  return text
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
  const text = name == null ? "" : String(name).trim()
  if (!text) return "AG"
  return (
    text
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "AG"
  )
}

function normalizeStatus(status) {
  if (status == null || status === "") return "Active"
  const normalized = String(status).toLowerCase()
  if (normalized === "created") return "Created"
  if (normalized === "draft") return "Draft"
  if (normalized === "registering") return "Registering"
  if (normalized === "registered") return "Registered"
  if (normalized === "deleted") return "Removed"
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

export function resolveMarketplaceAgentIds(agent) {
  const seller = agent.seller || {}
  const sellerId = agent.sellerId ?? seller.id
  const agentId = agent.agentId
  const nSeller = sellerId != null ? Number(sellerId) : NaN
  const nAgent = agentId != null ? Number(agentId) : NaN
  return {
    sellerId: Number.isFinite(nSeller) ? nSeller : NaN,
    agentId: Number.isFinite(nAgent) ? nAgent : NaN,
  }
}

export function mapMarketplaceAgentsToCards(marketplaceAgents) {
  if (!Array.isArray(marketplaceAgents)) return []
  return marketplaceAgents.filter(Boolean).map((entry, index) => {
    const seller = entry.seller || {}
    const commerce = entry.commerce || {}
    const arc = entry.arc || {}
    const tools = Array.isArray(entry.tools) ? entry.tools : []
    const minPrice = Number(commerce.minPriceUSDC || 0)
    const category = String(entry.category || "General")
    const offeringType = entry.offeringType ?? "agent"
    const protocolType = entry.protocolType ?? "http"
    const endpointHost = String(entry.endpointHost || "Endpoint unavailable")
    const tags = Array.from(
      new Set([category, ...tools.map((tool) => toTitleCase(tool?.toolKey || tool?.name || ""))].filter(Boolean)),
    )

    const sellerId = entry.sellerId ?? seller.id
    const agentId = entry.agentId

    return {
      id: entry.id ?? (sellerId != null && agentId != null ? makeAgentCompositeId(sellerId, agentId) : `unknown-${index}`),
      sellerId,
      agentId,
      name: entry.name != null && String(entry.name).trim() !== "" ? String(entry.name) : "Unnamed Agent",
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
      avatar: initialsFromName(entry.name != null ? String(entry.name) : ""),
      color: CARD_GRADIENTS[index % CARD_GRADIENTS.length],
      holdings: [{ amount: String(commerce.toolCount || tools.length), symbol: "TOOLS" }],
      toolCount: commerce.toolCount || tools.length,
      token: arc.agentId || "Pending Arc ID",
      paymentProtocol: "Arc + x402",
      registries: ["Arc ERC-8004"],
      explorerLabel: "Copy Invoke URL",
      marketLabel: "Invoke Tool",
      rawMetadata: (() => {
        try {
          return JSON.stringify(entry, null, 2)
        } catch {
          return "{}"
        }
      })(),
      editable: false,
      invokePath: tools[0]?.invokePath || "",
      tools,
      profile: {
        category,
        offeringType,
        protocolType,
        services: tools.length
          ? tools.map((tool) => (tool?.name != null ? String(tool.name) : "Tool"))
          : [entry.name != null ? String(entry.name) : "Provider endpoint"],
        apiBaseUrl: endpointHost,
        apiDocsUrl: entry.apiDocsUrl || "",
        endpointUrl: entry.endpointUrl || "",
        httpMethod: entry.httpMethod || "POST",
        healthStatus: entry.healthStatus || "unchecked",
        pricingModel: "On-chain metered",
        basePriceUsdc: formatPrice(minPrice),
        trustSignals: [arc.registered ? "Arc ERC-8004 registered" : "Arc registration pending"],
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
        tools.map((tool) => (tool?.name != null ? String(tool.name) : "")).join(" "),
      ]
        .map((part) => (part == null ? "" : String(part)))
        .join(" ")
        .toLowerCase(),
    }
  })
}
