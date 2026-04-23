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

export function makeAgentCompositeId(sellerId, agentId) {
  return `${sellerId}:${agentId}`
}

function createMappedAgent({ seller, agent, tools, index }) {
  const compositeId = makeAgentCompositeId(seller.id, agent.id)
  const tags = Array.from(new Set(tools.map((tool) => toTitleCase(tool.toolKey))))
  const minPrice = Math.min(...tools.map((tool) => Number(tool.priceUSDC)))

  const metadata = {
    compositeId,
    seller,
    agent,
    tools,
  }
  const fallbackServices = tools.map((tool) => tool.name).filter(Boolean)

  return {
    id: compositeId,
    sellerId: seller.id,
    agentId: agent.id,
    name: agent.name || "Unnamed Agent",
    avatarImage: agent.iconDataUrl || "",
    shortAddress: formatShortAddress(String(agent.id)),
    wallet: seller.walletAddress || "Wallet unavailable",
    owner: seller.name || "Unknown seller",
    authority: seller.validatorWalletAddress || "Not configured",
    assetType: "Core Asset",
    status: normalizeStatus(agent.status),
    description: agent.description || tools[0]?.description || "No description provided.",
    tags: tags.length ? tags : ["General"],
    categoryBadges: [
      `TOOLS ${tools.length}`,
      minPrice > 0 ? `MIN ${minPrice.toFixed(2)} USDC` : "FREE",
    ],
    avatar: initialsFromName(agent.name || ""),
    color: CARD_GRADIENTS[index % CARD_GRADIENTS.length],
    holdings: [{ amount: String(tools.length), symbol: "TOOLS" }],
    token: "Not provided by API",
    paymentProtocol: tools.length ? "x402 Enabled" : "x402 Not Enabled",
    registries: ["Arc Marketplace", "Seller API"],
    explorerLabel: "View API Details",
    marketLabel: "Invoke Tool",
    rawMetadata: JSON.stringify(metadata, null, 2),
    editable: false,
    profile: {
      category: "General",
      services: fallbackServices.length ? fallbackServices : ["Not provided by backend"],
      apiBaseUrl: "Not provided by backend",
      apiDocsUrl: "Not provided by backend",
      slaTier: "Not provided by backend",
      pricingModel: "Per invocation",
      basePriceUsdc: minPrice > 0 ? minPrice.toFixed(2) : "Not provided by backend",
      trustSignals: tags.length ? tags : ["Not provided by backend"],
      complianceNotes: "Not provided by backend",
      kycStatus: "Unknown",
      supportEmail: "Not provided by backend",
      payoutPolicy: "Not provided by backend",
    },
    searchableText: [
      agent.name,
      agent.description,
      seller.name,
      seller.walletAddress,
      tags.join(" "),
      tools.map((tool) => tool.name).join(" "),
    ]
      .join(" ")
      .toLowerCase(),
  }
}

export function mapMarketplaceToAgentCards({ tools, sellerDetailsById }) {
  const grouped = new Map()

  for (const tool of tools) {
    const seller = tool.seller || {}
    const agent = tool.agent || {}
    const key = makeAgentCompositeId(seller.id, agent.id)
    if (!grouped.has(key)) {
      grouped.set(key, {
        sellerId: seller.id,
        agentId: agent.id,
        sellerFromTool: seller,
        tools: [],
      })
    }
    grouped.get(key).tools.push(tool)
  }

  const mapped = Array.from(grouped.values()).map((group, index) => {
    const detail = sellerDetailsById[group.sellerId]
    const seller = detail?.seller || {
      id: group.sellerId,
      name: group.sellerFromTool?.name || "Unknown seller",
      walletAddress: group.sellerFromTool?.walletAddress || "",
      validatorWalletAddress: "",
      status: "active",
    }
    const detailAgent =
      detail?.agents?.find((candidate) => candidate.id === group.agentId) ||
      group.tools[0]?.agent || { id: group.agentId, name: "Unnamed Agent", description: "" }

    return createMappedAgent({
      seller,
      agent: detailAgent,
      tools: group.tools,
      index,
    })
  })

  return mapped.sort((left, right) => right.agentId - left.agentId)
}
