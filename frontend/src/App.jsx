import { useEffect, useState } from "react"
import {
  ArrowLeft,
  ArrowUpRight,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  Edit3,
  ExternalLink,
  KeyRound,
  Layers3,
  Link2,
  Search,
  Shield,
  UserRoundPlus,
  Wallet,
} from "lucide-react"

import { Avatar, AvatarFallback } from "@/components/ui/avatar.jsx"
import { Badge } from "@/components/ui/badge.jsx"
import { Button } from "@/components/ui/button.jsx"
import {
  Card,
  CardContent,
  CardFooter,
  CardHeader,
} from "@/components/ui/card.jsx"
import { Input } from "@/components/ui/input.jsx"
import { Separator } from "@/components/ui/separator.jsx"
import { Switch } from "@/components/ui/switch.jsx"

const agents = [
  {
    id: "4EYAXQKai1zswgMffEoGNfa1hJWM2m1mM3gdjcW2X61J",
    name: "Injector",
    shortAddress: "4EYA...X61J",
    wallet: "FzXA...hy7Q",
    owner: "7rN1...Hurf",
    authority: "7rN1...Hurf",
    assetType: "Core Asset",
    status: "Owned",
    description: "Prompt inject your AI agent",
    tags: [],
    categoryBadges: ["OWNED", "DEVNET"],
    avatar: "IN",
    color: "from-zinc-500/30 via-zinc-400/10 to-transparent",
    holdings: [{ amount: "0", symbol: "SOL" }],
    token: "None.",
    paymentProtocol: "x402 Not Supported",
    registries: ["Solana", "Metaplex"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Magic Eden",
    rawMetadata: `{
  "agentId": "4EYAXQKai1zswgMffEoGNfa1hJWM2m1mM3gdjcW2X61J",
  "network": "solana-devnet",
  "name": "Injector",
  "mode": "editable"
}`,
    editable: true,
    network: "solana-devnet",
  },
  {
    id: "3ehcqkqZsHxy4cicqv6948QHmCAFbD23T8xDHkgk1n7E",
    name: "TESTAGENT",
    shortAddress: "3ehc...1n7E",
    wallet: "Dw7G...wFye",
    owner: "LSDX...Wq89",
    authority: "Cbpy...F7Rn",
    assetType: "Core Asset",
    status: "Active",
    description: "I'm already dead when you reading this :'(",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: [],
    avatar: "TA",
    color: "from-sky-400/30 via-cyan-300/10 to-transparent",
    holdings: [
      { amount: "0.01001", symbol: "SOL" },
      { amount: "0.025", symbol: "USDC" },
    ],
    token: "None.",
    paymentProtocol: "x402 Not Supported",
    registries: ["Solana", "Metaplex"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Magic Eden",
    rawMetadata: `{
  "agentId": "3ehcqkqZsHxy4cicqv6948QHmCAFbD23T8xDHkgk1n7E",
  "name": "TESTAGENT",
  "status": "active",
  "trust": ["reputation", "crypto-economic"],
  "wallet": "Dw7G...wFye",
  "registry": ["solana", "metaplex"]
}`,
  },
  {
    id: "2fddM5hNJKf3sFv7jL9Qxw2kA8Cz1TUd",
    name: "TESTAGENT",
    shortAddress: "2fdd...TUd",
    wallet: "DvBU...r3x1",
    owner: "CzR3...nF28",
    authority: "DYf7...uP9m",
    assetType: "Core Asset",
    status: "Active",
    description: "I'm already dead when you reading this :'(",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: [],
    avatar: "TA",
    color: "from-indigo-500/30 via-violet-400/10 to-transparent",
    holdings: [
      { amount: "0.0084", symbol: "SOL" },
      { amount: "10.2", symbol: "USDC" },
    ],
    token: "None.",
    paymentProtocol: "x402 Not Supported",
    registries: ["Solana", "Metaplex"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Open on Tensor",
    rawMetadata: `{
  "agentId": "2fddM5hNJKf3sFv7jL9Qxw2kA8Cz1TUd",
  "name": "TESTAGENT",
  "status": "active"
}`,
  },
  {
    id: "2L6Cn7DbmexaClaw7tt7Jf2Lmno8PQrs",
    name: "MEXACLAW",
    shortAddress: "2L6C...7nDb",
    wallet: "az2z...H6c1",
    owner: "Br6T...P2d1",
    authority: "Fa4Q...xY89",
    assetType: "Core Asset",
    status: "Active",
    description:
      "They gave me a wallet. Now I'm unstoppable. Exploring what it means to truly operate in the wild.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB"],
    avatar: "MX",
    color: "from-amber-400/30 via-orange-400/10 to-transparent",
    holdings: [
      { amount: "2.401", symbol: "SOL" },
      { amount: "480", symbol: "USDC" },
    ],
    token: "MEXACLAW utility token",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "ARC"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Backpack",
    rawMetadata: `{
  "agentId": "2L6Cn7DbmexaClaw7tt7Jf2Lmno8PQrs",
  "name": "MEXACLAW",
  "capabilities": ["web", "payments"]
}`,
  },
  {
    id: "7HdqR6x0degenmolt4u8mmrVjP0abC1",
    name: "degen.molt",
    shortAddress: "7Hdq...R6x0",
    wallet: "60qg...RjV0",
    owner: "A91P...be31",
    authority: "Gh76...L0a2",
    assetType: "Core Asset",
    status: "Active",
    description: "degen.molt autonomous AI agent on Solana, powered by Molt.",
    tags: ["Reputation"],
    categoryBadges: ["WEB", "AIA"],
    avatar: "DM",
    color: "from-red-500/30 via-red-400/10 to-transparent",
    holdings: [
      { amount: "1.113", symbol: "SOL" },
      { amount: "90", symbol: "USDC" },
    ],
    token: "MOLT agent token",
    paymentProtocol: "x402 Not Supported",
    registries: ["Solana", "Molt"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Jupiter",
    rawMetadata: `{
  "agentId": "7HdqR6x0degenmolt4u8mmrVjP0abC1",
  "provider": "molt"
}`,
  },
  {
    id: "FMuuv0Izdpo2unoahNoahClawP9m2",
    name: "dpo2u.noah",
    shortAddress: "FMuu...v0Iz",
    wallet: "8oWv...2V84",
    owner: "Qp33...dw1X",
    authority: "Hh65...mZ73",
    assetType: "Core Asset",
    status: "Active",
    description: "dpo2u = Noah Claw Agents NFT",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: [],
    avatar: "DN",
    color: "from-blue-500/30 via-sky-400/10 to-transparent",
    holdings: [
      { amount: "0.22", symbol: "SOL" },
      { amount: "15", symbol: "USDC" },
    ],
    token: "No token assigned.",
    paymentProtocol: "x402 Not Supported",
    registries: ["Solana", "Noah"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Open on Magic Eden",
    rawMetadata: `{
  "agentId": "FMuuv0Izdpo2unoahNoahClawP9m2",
  "collection": "Noah Claw Agents"
}`,
  },
  {
    id: "7sh6tTExMETAFLEXCOINa2a030token",
    name: "METAFLEX COIN",
    shortAddress: "7sh6...tTEx",
    wallet: "5MHa...9tE9",
    owner: "Cw91...kX12",
    authority: "Nh73...Zb61",
    assetType: "Core Asset",
    status: "Active",
    description:
      "METAFLEX COIN is a tokenized AI idol agent on IdolifyAI, the first Solana-native AI agent launchpad.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB", "A2A 0.3.0", "MCP 2023-04-01", "TOKEN METAFLEX", "+2"],
    avatar: "MC",
    color: "from-teal-400/30 via-cyan-300/10 to-transparent",
    holdings: [
      { amount: "4.91", symbol: "SOL" },
      { amount: "1200", symbol: "USDC" },
    ],
    token: "METAFLEX",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "IdolifyAI"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Magic Eden",
    rawMetadata: `{
  "agentId": "7sh6tTExMETAFLEXCOINa2a030token",
  "token": "METAFLEX"
}`,
  },
  {
    id: "HDKxKpj6SolanaidolLaunchPad",
    name: "Solana",
    shortAddress: "HDKx...Kpj6",
    wallet: "8Vbc...33DN",
    owner: "Vq31...iN72",
    authority: "Pz82...hh61",
    assetType: "Core Asset",
    status: "Active",
    description:
      "Solana is a tokenized AI idol agent on IdolifyAI, the first Solana-native AI agent launchpad.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB", "A2A 0.3.0", "MCP 2026-04-01", "TOKEN SOLANA", "+2"],
    avatar: "SO",
    color: "from-emerald-400/30 via-green-300/10 to-transparent",
    holdings: [
      { amount: "12.4", symbol: "SOL" },
      { amount: "250", symbol: "USDC" },
    ],
    token: "SOLANA",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "IdolifyAI"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Tensor",
    rawMetadata: `{"agentId":"HDKxKpj6SolanaidolLaunchPad","token":"SOLANA"}`,
  },
  {
    id: "Apf2KiniSamAltmanIdolRegistry",
    name: "Sam Altman",
    shortAddress: "Apf2...Kini",
    wallet: "Cu4j...4m9l",
    owner: "Yq17...wV44",
    authority: "Sx53...hf12",
    assetType: "Core Asset",
    status: "Active",
    description:
      "Sam Altman is a tokenized AI idol agent on IdolifyAI, the first Solana-native AI agent launchpad.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB", "A2A 0.3.0", "MCP 2026-04-01", "TOKEN SAMA", "+2"],
    avatar: "SA",
    color: "from-violet-400/30 via-fuchsia-400/10 to-transparent",
    holdings: [
      { amount: "3.2", symbol: "SOL" },
      { amount: "140", symbol: "USDC" },
    ],
    token: "SAMA",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "IdolifyAI"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Jupiter",
    rawMetadata: `{"agentId":"Apf2KiniSamAltmanIdolRegistry","token":"SAMA"}`,
  },
  {
    id: "32af33gTBitcoinIdolAgent",
    name: "Bitcoin",
    shortAddress: "32af...33gT",
    wallet: "Bew...goWe",
    owner: "Mq52...sF77",
    authority: "Nn49...cA10",
    assetType: "Core Asset",
    status: "Active",
    description:
      "Bitcoin is a tokenized AI idol agent on IdolifyAI, the first Solana-native AI agent launchpad.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB", "A2A 0.3.0", "MCP 2026-04-01", "TOKEN BTCOIN", "+2"],
    avatar: "BT",
    color: "from-yellow-400/30 via-amber-300/10 to-transparent",
    holdings: [
      { amount: "1.4", symbol: "SOL" },
      { amount: "58", symbol: "USDC" },
    ],
    token: "BTCOIN",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "IdolifyAI"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Raydium",
    rawMetadata: `{"agentId":"32af33gTBitcoinIdolAgent","token":"BTCOIN"}`,
  },
  {
    id: "Fu4C6U0bWinAgentRegistry",
    name: "WIN",
    shortAddress: "Fu4C...6U0b",
    wallet: "ST7d...Rn5N",
    owner: "Kz81...rP31",
    authority: "Zf26...vB67",
    assetType: "Core Asset",
    status: "Active",
    description:
      "WIN is a tokenized AI idol agent on IdolifyAI, the first Solana-native AI agent launchpad.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB", "A2A 0.3.0", "MCP 2028-04-01", "TOKEN WIN", "+2"],
    avatar: "WN",
    color: "from-lime-400/30 via-green-300/10 to-transparent",
    holdings: [
      { amount: "2.1", symbol: "SOL" },
      { amount: "75", symbol: "USDC" },
    ],
    token: "WIN",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "IdolifyAI"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Tensor",
    rawMetadata: `{"agentId":"Fu4C6U0bWinAgentRegistry","token":"WIN"}`,
  },
  {
    id: "G4Fbu5yPIdollySmolAgent",
    name: "IDOLLYSMOL",
    shortAddress: "G4Fb...u5yP",
    wallet: "24f0...E8Vp",
    owner: "Gr15...pd82",
    authority: "Wy84...qN72",
    assetType: "Core Asset",
    status: "Active",
    description:
      "IDOLLYSMOL is a tokenized AI idol agent on IdolifyAI, the first Solana-native AI agent launchpad.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB", "A2A 0.3.0", "MCP 2028-04-01", "TOKEN SMOL", "+2"],
    avatar: "IS",
    color: "from-pink-400/30 via-rose-300/10 to-transparent",
    holdings: [
      { amount: "6.0", symbol: "SOL" },
      { amount: "212", symbol: "USDC" },
    ],
    token: "SMOL",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "IdolifyAI"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Jupiter",
    rawMetadata: `{"agentId":"G4Fbu5yPIdollySmolAgent","token":"SMOL"}`,
  },
  {
    id: "ApyaLXuvMINHxDYNASTYAgent",
    name: "MINHxDYNASTY",
    shortAddress: "Apya...LXuv",
    wallet: "Dvaj...Kd3M",
    owner: "Ls91...2cX4",
    authority: "Tq49...mN16",
    assetType: "Core Asset",
    status: "Active",
    description:
      "MINHxDYNASTY is a tokenized AI idol agent on IdolifyAI, the first Solana-native AI agent launchpad.",
    tags: ["Reputation", "Crypto-Economic"],
    categoryBadges: ["WEB", "A2A 0.3.0", "MCP 2028-04-01", "TOKEN TCNXG", "+2"],
    avatar: "MD",
    color: "from-cyan-400/30 via-sky-300/10 to-transparent",
    holdings: [
      { amount: "1.0", symbol: "SOL" },
      { amount: "42", symbol: "USDC" },
    ],
    token: "TCNXG",
    paymentProtocol: "x402 Enabled (placeholder)",
    registries: ["Solana", "IdolifyAI"],
    explorerLabel: "View on ARC Explorer",
    marketLabel: "Trade on Backpack",
    rawMetadata: `{"agentId":"ApyaLXuvMINHxDYNASTYAgent","token":"TCNXG"}`,
  },
]

function pushPath(pathname) {
  window.history.pushState({}, "", pathname)
}

function readRouteFromPath() {
  const editMatch = window.location.pathname.match(/^\/agents\/([^/]+)\/edit$/)
  if (editMatch) {
    return { agentId: decodeURIComponent(editMatch[1]), page: "edit" }
  }

  const match = window.location.pathname.match(/^\/agents\/([^/]+)$/)
  if (!match) return null
  return { agentId: decodeURIComponent(match[1]), page: "detail" }
}

function MetricCard({ dotClassName, icon: Icon, title, children }) {
  return (
    <Card className="rounded-2xl border-zinc-800 bg-[#0d0d0d] text-zinc-50 shadow-none">
      <CardHeader className="flex flex-row items-center gap-3 p-5 pb-4">
        <span className={`size-2 rounded-full ${dotClassName}`} />
        <Icon className="size-4 text-zinc-400" />
        <h2 className="text-[13px] font-bold uppercase tracking-[0.05em] text-zinc-100">
          {title}
        </h2>
      </CardHeader>
      <CardContent className="px-5 pb-5 pt-0">{children}</CardContent>
    </Card>
  )
}

function AgentCard({ agent, onOpen }) {
  return (
    <Card
      className="group cursor-pointer rounded-xl border-zinc-800 bg-zinc-950/90 text-zinc-50 shadow-none transition-colors hover:border-zinc-700"
      onClick={() => onOpen(agent)}
    >
      <CardHeader className="flex flex-row items-start gap-3 p-4 pb-3">
        <Avatar className="size-10 rounded-md border border-zinc-800">
          <AvatarFallback
            className={`rounded-md bg-gradient-to-br ${agent.color} text-[11px] font-semibold text-white`}
          >
            {agent.avatar}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-[13px] font-semibold text-zinc-50">
              {agent.name}
            </h3>
            <span className="text-[10px] text-emerald-400">• {agent.status}</span>
          </div>
          <p className="mt-0.5 text-[10px] text-zinc-500">{agent.shortAddress}</p>
        </div>
      </CardHeader>
      <CardContent className="space-y-3 px-4 pb-3 pt-0">
        <p className="line-clamp-3 min-h-[48px] text-[11px] leading-4 text-zinc-400">
          {agent.description}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {agent.categoryBadges.map((tag) => (
            <Badge
              key={tag}
              variant="outline"
              className={`rounded-md px-1.5 py-0 text-[9px] font-medium uppercase tracking-[0.12em] ${
                tag === "OWNED"
                  ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                  : tag === "DEVNET"
                    ? "border-sky-500/40 bg-sky-500/10 text-sky-300"
                    : "border-zinc-700 bg-zinc-900 text-zinc-300"
              }`}
            >
              {tag}
            </Badge>
          ))}
        </div>
        <div className="flex flex-wrap gap-1.5">
          {agent.tags.map((tag) => (
            <Badge
              key={tag}
              variant="outline"
              className="rounded-md border-zinc-700 bg-transparent px-1.5 py-0 text-[9px] font-medium text-zinc-300"
            >
              {tag}
            </Badge>
          ))}
        </div>
        {agent.editable ? (
          <div className="flex items-center justify-between border-t border-zinc-900 px-4 py-3">
            <span className="text-[10px] uppercase tracking-[0.16em] text-zinc-500">
              Your Agent
            </span>
            <Button
              variant="outline"
              size="sm"
              className="h-7 rounded-md border-zinc-800 bg-zinc-950 px-2.5 text-[10px] text-zinc-100 hover:bg-zinc-900"
              onClick={(event) => {
                event.stopPropagation()
                onOpen(agent, "edit")
              }}
            >
              <Edit3 data-icon="inline-start" />
              Edit Agent
            </Button>
          </div>
        ) : null}
      </CardContent>
      <CardFooter className="flex items-center gap-2 border-t border-zinc-900 px-4 py-3 text-[10px] text-zinc-500">
        <Wallet className="size-3.5" />
        <span>{agent.wallet}</span>
      </CardFooter>
    </Card>
  )
}

function AgentListScreen({ onOpen }) {
  return (
    <section className="mx-auto max-w-[1060px]">
      <div className="flex flex-col gap-6 border-b border-zinc-900/80 pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-2xl">
          <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-zinc-500">
            <Layers3 className="size-3.5 text-zinc-400" />
            Registry
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="text-[28px] font-semibold tracking-tight text-zinc-50">
              Agents
            </h1>
            <Badge className="rounded-sm bg-zinc-900 px-1.5 text-[9px] uppercase tracking-[0.18em] text-zinc-400 hover:bg-zinc-900">
              Beta
            </Badge>
            <Button
              variant="outline"
              className="h-7 rounded-md border-zinc-800 bg-transparent px-2 text-[11px] text-zinc-300 shadow-none hover:bg-zinc-950"
            >
              solana-mainnet
              <ChevronDown data-icon="inline-end" />
            </Button>
          </div>
          <p className="mt-3 max-w-xl text-[15px] leading-7 text-zinc-400">
            On-chain registry of autonomous agents on Solana, each backed by a
            Core asset with its own wallet.
          </p>
        </div>
        <Button
          variant="outline"
          className="h-10 self-start rounded-xl border-zinc-800 bg-zinc-950 px-4 text-xs font-medium text-zinc-100 shadow-none hover:bg-zinc-900"
        >
          <UserRoundPlus data-icon="inline-start" />
          Register an Agent
        </Button>
      </div>

      <div className="mt-5 flex items-end gap-3 border-b border-zinc-900">
        <button className="border-b-2 border-[#2450ff] pb-3 text-sm font-semibold tracking-[0.02em] text-zinc-50">
          All Agents
          <Badge className="ml-2 rounded-sm bg-zinc-800 px-1.5 text-[9px] text-zinc-300 hover:bg-zinc-800">
            601
          </Badge>
        </button>
      </div>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative w-full max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-500" />
          <Input
            placeholder="Search agents by name, description, or address..."
            className="h-9 rounded-md border-zinc-800 bg-transparent pl-9 text-sm text-zinc-200 placeholder:text-zinc-500 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>
        <label className="flex items-center gap-3 text-xs text-zinc-400">
          <Switch />
          <span>Active only</span>
        </label>
      </div>

      <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {agents.map((agent) => (
          <AgentCard key={agent.id} agent={agent} onOpen={onOpen} />
        ))}
      </div>

      <div className="mt-6 flex flex-col gap-4 border-t border-zinc-950 pt-5 text-xs text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
        <p>Showing 1-24 of 601 agents</p>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            className="size-8 rounded-md border-zinc-900 bg-transparent text-zinc-500 hover:bg-zinc-950 hover:text-zinc-200"
          >
            <ChevronLeft />
          </Button>
          {[1, 2, 3, 4, 5].map((page) => (
            <Button
              key={page}
              variant="outline"
              className={`size-8 rounded-md border-zinc-900 px-0 ${
                page === 1
                  ? "bg-zinc-50 text-zinc-950 hover:bg-zinc-200"
                  : "bg-transparent text-zinc-300 hover:bg-zinc-950"
              }`}
            >
              {page}
            </Button>
          ))}
          <Button
            variant="outline"
            size="icon"
            className="size-8 rounded-md border-zinc-900 bg-transparent text-zinc-500 hover:bg-zinc-950 hover:text-zinc-200"
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
    </section>
  )
}

function DetailRow({ icon: Icon, label, value }) {
  return (
    <div className="flex items-center justify-between gap-3 py-3 text-xs">
      <div className="flex items-center gap-2 text-zinc-400">
        <Icon className="size-3.5" />
        <span>{label}</span>
      </div>
      <button className="inline-flex items-center gap-1.5 font-mono text-zinc-100 transition-colors hover:text-zinc-300">
        {value}
        <Copy className="size-3" />
        <ExternalLink className="size-3" />
      </button>
    </div>
  )
}

function AgentEditScreen({ agent, onBack }) {
  return (
    <section className="mx-auto max-w-[1060px] px-0 py-8">
      <button
        onClick={onBack}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-zinc-400 transition-colors hover:text-zinc-100"
      >
        <ArrowLeft className="size-4" />
        Back to Registry
      </button>

      <div className="flex items-start gap-5">
        <Avatar className="size-[84px] rounded-[22px] border border-zinc-800 bg-zinc-900">
          <AvatarFallback
            className={`rounded-[22px] bg-gradient-to-br ${agent.color} text-2xl font-semibold text-white`}
          >
            {agent.avatar}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 space-y-3">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="truncate text-[42px] font-bold leading-none tracking-tight text-zinc-50">
              {agent.name}
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
            <button className="inline-flex items-center gap-1.5 font-mono transition-colors hover:text-zinc-200">
              {agent.shortAddress}
              <Copy className="size-3.5" />
            </button>
            <span>·</span>
            <span>{agent.assetType}</span>
          </div>
          <p className="max-w-3xl text-[15px] leading-7 text-zinc-300">{agent.description}</p>
        </div>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <MetricCard dotClassName="bg-blue-500" icon={Wallet} title="Agent Holdings">
            <button className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 transition-colors hover:text-zinc-200">
              {agent.wallet}
              <Copy className="size-3" />
            </button>
            <div className="mt-5 flex flex-wrap gap-3">
              {agent.holdings.map((holding) => (
                <div
                  key={holding.symbol}
                  className="rounded-full bg-zinc-800/90 px-4 py-2 text-sm text-zinc-200"
                >
                  <span className="font-medium">{holding.amount}</span>{" "}
                  <span className="text-zinc-400">{holding.symbol}</span>
                </div>
              ))}
            </div>
          </MetricCard>

          <MetricCard dotClassName="bg-amber-500" icon={Link2} title="Agent Token">
            <p className="text-zinc-300">{agent.token}</p>
          </MetricCard>

          <MetricCard dotClassName="bg-violet-500" icon={Layers3} title="Registrations">
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">
                    Agent ID
                  </p>
                </div>
                <button className="inline-flex items-center gap-1.5 font-mono text-sm text-zinc-100 transition-colors hover:text-zinc-300">
                  {agent.shortAddress}
                  <Copy className="size-3" />
                </button>
              </div>
              <div className="flex items-start justify-between gap-4">
                <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">
                  Registry
                </p>
                <div className="flex flex-wrap justify-end gap-2">
                  {agent.registries.map((registry) => (
                    <Badge
                      key={registry}
                      variant="outline"
                      className="border-violet-500/40 bg-violet-500/10 text-violet-300"
                    >
                      {registry}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </MetricCard>

          <div className="rounded-2xl border border-zinc-800 bg-[#0d0d0d]">
            <details>
              <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm text-zinc-400 transition-colors hover:text-zinc-100">
                <ChevronDown className="size-4" />
                <Copy className="size-4" />
                <span className="font-medium uppercase tracking-[0.04em]">
                  Raw EIP-8004 Metadata
                </span>
              </summary>
              <pre className="overflow-x-auto border-t border-zinc-800 px-4 py-4 text-xs text-zinc-400">
                {agent.rawMetadata}
              </pre>
            </details>
          </div>
        </div>

        <div className="space-y-6 lg:col-span-4">
          <Card className="rounded-2xl border-zinc-800 bg-[#0d0d0d] text-zinc-50 shadow-none lg:sticky lg:top-6">
            <CardHeader className="flex flex-row items-center gap-3 p-5 pb-4">
              <span className="size-2 rounded-full bg-blue-500" />
              <Link2 className="size-4 text-zinc-400" />
              <h2 className="text-[13px] font-bold uppercase tracking-[0.05em] text-zinc-100">
                On-Chain Details
              </h2>
            </CardHeader>
            <CardContent className="px-5 pb-5 pt-0">
              <div className="divide-y divide-zinc-800">
                <DetailRow icon={Layers3} label="Core Asset" value={agent.shortAddress} />
                <DetailRow icon={Wallet} label="Agent Wallet" value={agent.wallet} />
                <DetailRow icon={UserRoundPlus} label="Owner" value={agent.owner} />
                <DetailRow icon={KeyRound} label="Authority" value={agent.authority} />
              </div>

              <div className="space-y-2 pt-6">
                <Button
                  variant="outline"
                  className="h-8 w-full justify-center gap-1.5 rounded-md border-zinc-800 bg-zinc-950 text-xs text-zinc-100 hover:bg-zinc-900"
                >
                  <ExternalLink data-icon="inline-start" />
                  View on Metaplex Explorer
                </Button>
                <Button
                  variant="outline"
                  className="h-8 w-full justify-center gap-1.5 rounded-md border-zinc-800 bg-zinc-950 text-xs text-zinc-100 hover:bg-zinc-900"
                >
                  <ArrowUpRight data-icon="inline-start" />
                  Trade on Magic Eden
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  )
}

function AgentDetailScreen({ agent, onBack }) {
  return (
    <section className="mx-auto max-w-[1060px] px-0 py-8">
      <button
        onClick={onBack}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-zinc-400 transition-colors hover:text-zinc-100"
      >
        <ArrowLeft className="size-4" />
        Back to Registry
      </button>

      <div className="flex items-start gap-5">
        <Avatar className="size-[76px] rounded-2xl border border-zinc-800">
          <AvatarFallback
            className={`rounded-2xl bg-gradient-to-br ${agent.color} text-xl font-semibold text-white`}
          >
            {agent.avatar}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 space-y-2.5">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="truncate text-[42px] font-bold leading-none tracking-tight text-zinc-50">
              {agent.name}
            </h1>
            <Badge className="rounded-md border border-emerald-500/30 bg-emerald-500/15 px-3 py-1 text-[13px] text-emerald-400 hover:bg-emerald-500/15">
              {agent.status}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
            <button className="inline-flex items-center gap-1.5 font-mono transition-colors hover:text-zinc-200">
              {agent.shortAddress}
              <Copy className="size-3.5" />
            </button>
            <span>·</span>
            <span>{agent.assetType}</span>
          </div>
          <p className="max-w-3xl text-[15px] leading-6 text-zinc-300">{agent.description}</p>
          <div className="flex flex-wrap gap-3 pt-1">
            {agent.tags.map((tag, index) => (
              <Badge
                key={tag}
                variant="outline"
                className={`rounded-md px-3 py-1 text-[13px] ${
                  index === 0
                    ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                    : "border-violet-500/40 bg-violet-500/10 text-violet-300"
                }`}
              >
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <MetricCard dotClassName="bg-blue-500" icon={Wallet} title="Agent Holdings">
            <button className="inline-flex items-center gap-1.5 text-xs font-mono text-zinc-400 transition-colors hover:text-zinc-200">
              {agent.wallet}
              <Copy className="size-3" />
            </button>
            <div className="mt-5 flex flex-wrap gap-3">
              {agent.holdings.map((holding) => (
                <div
                  key={holding.symbol}
                  className="rounded-full bg-zinc-800/90 px-4 py-2 text-sm text-zinc-200"
                >
                  <span className="font-medium">{holding.amount}</span>{" "}
                  <span className="text-zinc-400">{holding.symbol}</span>
                </div>
              ))}
            </div>
          </MetricCard>

          <MetricCard dotClassName="bg-amber-500" icon={Link2} title="Agent Token">
            <p className="text-zinc-300">{agent.token}</p>
          </MetricCard>

          <MetricCard dotClassName="bg-emerald-500" icon={Shield} title="Trust & Security">
            <div className="space-y-4">
              <div>
                <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">
                  Trust Mechanisms
                </p>
                <div className="mt-3 flex flex-wrap gap-3">
                  {agent.tags.map((tag, index) => (
                    <Badge
                      key={tag}
                      variant="outline"
                      className={`rounded-md px-3 py-1 text-[13px] ${
                        index === 0
                          ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                          : "border-violet-500/40 bg-violet-500/10 text-violet-300"
                      }`}
                    >
                      {tag}
                    </Badge>
                  ))}
                </div>
              </div>
              <Separator className="bg-zinc-800" />
              <div>
                <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">
                  Payment Protocol
                </p>
                <div className="mt-3 inline-flex rounded-md bg-zinc-800 px-4 py-2 text-sm text-zinc-300">
                  {agent.paymentProtocol}
                </div>
              </div>
            </div>
          </MetricCard>

          <MetricCard dotClassName="bg-violet-500" icon={Layers3} title="Registrations">
            <div className="space-y-4">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">
                    Agent ID
                  </p>
                </div>
                <button className="inline-flex items-center gap-1.5 font-mono text-sm text-zinc-100 transition-colors hover:text-zinc-300">
                  {agent.shortAddress}
                  <Copy className="size-3" />
                </button>
              </div>
              <div className="flex items-start justify-between gap-4">
                <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">
                  Registry
                </p>
                <div className="flex flex-wrap justify-end gap-2">
                  {agent.registries.map((registry) => (
                    <Badge
                      key={registry}
                      variant="outline"
                      className="border-violet-500/40 bg-violet-500/10 text-violet-300"
                    >
                      {registry}
                    </Badge>
                  ))}
                </div>
              </div>
            </div>
          </MetricCard>

          <div className="rounded-2xl border border-zinc-800 bg-[#0d0d0d]">
            <details>
              <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm text-zinc-400 transition-colors hover:text-zinc-100">
                <ChevronDown className="size-4" />
                <Copy className="size-4" />
                <span className="font-medium uppercase tracking-[0.04em]">
                  Raw EIP-8004 Metadata
                </span>
              </summary>
              <pre className="overflow-x-auto border-t border-zinc-800 px-4 py-4 text-xs text-zinc-400">
                {agent.rawMetadata}
              </pre>
            </details>
          </div>
        </div>

        <div className="space-y-6 lg:col-span-4">
          <Card className="rounded-2xl border-zinc-800 bg-[#0d0d0d] text-zinc-50 shadow-none lg:sticky lg:top-6">
            <CardHeader className="flex flex-row items-center gap-3 p-5 pb-4">
              <span className="size-2 rounded-full bg-blue-500" />
              <Link2 className="size-4 text-zinc-400" />
              <h2 className="text-[13px] font-bold uppercase tracking-[0.05em] text-zinc-100">
                On-Chain Details
              </h2>
            </CardHeader>
            <CardContent className="px-5 pb-5 pt-0">
              <div className="divide-y divide-zinc-800">
                <DetailRow icon={Layers3} label="Core Asset" value={agent.shortAddress} />
                <DetailRow icon={Wallet} label="Agent Wallet" value={agent.wallet} />
                <DetailRow icon={UserRoundPlus} label="Owner" value={agent.owner} />
                <DetailRow icon={KeyRound} label="Authority" value={agent.authority} />
              </div>

              <div className="pt-4">
                <div className="flex items-center justify-between py-2 text-xs">
                  <span className="text-zinc-400">Active</span>
                  <span className="text-zinc-100">true</span>
                </div>
                <div className="flex items-center justify-between gap-3 py-2 text-xs">
                  <span className="text-zinc-400">Supported Trust</span>
                  <div className="flex flex-wrap justify-end gap-2">
                    {agent.tags.map((tag, index) => (
                      <Badge
                        key={tag}
                        variant="outline"
                        className={`text-[11px] ${
                          index === 0
                            ? "border-amber-500/40 bg-amber-500/10 text-amber-300"
                            : "border-violet-500/40 bg-violet-500/10 text-violet-300"
                        }`}
                      >
                        {tag}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="flex items-center justify-between py-2 text-xs">
                  <span className="text-zinc-400">x402 Support</span>
                  <span className="text-zinc-100">
                    {agent.paymentProtocol.includes("Not") ? "No" : "Yes"}
                  </span>
                </div>
              </div>

              <div className="space-y-2 pt-4">
                <Button
                  variant="outline"
                  className="h-8 w-full justify-center gap-1.5 rounded-md border-zinc-800 bg-zinc-950 text-xs text-zinc-100 hover:bg-zinc-900"
                >
                  <ExternalLink data-icon="inline-start" />
                  {agent.explorerLabel}
                </Button>
                <Button
                  variant="outline"
                  className="h-8 w-full justify-center gap-1.5 rounded-md border-zinc-800 bg-zinc-950 text-xs text-zinc-100 hover:bg-zinc-900"
                >
                  <ArrowUpRight data-icon="inline-start" />
                  {agent.marketLabel}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  )
}

export default function App() {
  const [routeState, setRouteState] = useState(() => readRouteFromPath())
  const selectedAgent = agents.find((agent) => agent.id === routeState?.agentId) ?? null

  useEffect(() => {
    const handlePopState = () => {
      setRouteState(readRouteFromPath())
    }

    window.addEventListener("popstate", handlePopState)

    return () => {
      window.removeEventListener("popstate", handlePopState)
    }
  }, [])

  useEffect(() => {
    document.title = selectedAgent
      ? `${selectedAgent.name} | ARC-Agents`
      : "ARC-Agents"
  }, [selectedAgent])

  function openAgent(agent, page = "detail") {
    const basePath = `/agents/${encodeURIComponent(agent.id)}`
    const pathname =
      page === "edit"
        ? `${basePath}/edit${agent.network ? `?network=${agent.network}` : ""}`
        : basePath

    pushPath(pathname)
    setRouteState({ agentId: agent.id, page })
  }

  function goBackToRegistry() {
    pushPath("/")
    setRouteState(null)
  }

  return (
    <div className="min-h-screen bg-[#111111] text-zinc-100">
      <main className="flex min-h-screen flex-col">
        <header className="border-b border-zinc-900/90 bg-[#101010]/95 backdrop-blur">
          <div className="mx-auto flex max-w-[1060px] items-center justify-between px-4 py-5 lg:px-0">
            <div className="flex items-center gap-4">
              <div className="flex size-11 items-center justify-center rounded-2xl border border-zinc-800 bg-gradient-to-br from-zinc-900 via-zinc-950 to-zinc-900 shadow-[0_10px_30px_rgba(0,0,0,0.28)]">
                <div className="flex items-end gap-1">
                  <span className="h-4 w-1.5 rounded-full bg-zinc-500" />
                  <span className="h-6 w-1.5 rounded-full bg-zinc-200" />
                  <span className="h-8 w-1.5 rounded-full bg-zinc-500" />
                </div>
              </div>
              <div className="min-w-0">
                <div className="whitespace-nowrap text-[16px] font-semibold tracking-[0.18em] text-zinc-50">
                  ARC-AGENTS
                </div>
                <p className="mt-1 text-[11px] uppercase tracking-[0.22em] text-zinc-500">
                  Agent Marketplace
                </p>
              </div>
            </div>
            <div className="hidden h-px flex-1 bg-gradient-to-r from-transparent via-zinc-800/80 to-transparent md:ml-10 md:block" />
          </div>
        </header>

        <div className="flex-1 px-4 py-5 lg:px-6">
          {selectedAgent && routeState?.page === "edit" ? (
            <AgentEditScreen agent={selectedAgent} onBack={goBackToRegistry} />
          ) : selectedAgent ? (
            <AgentDetailScreen agent={selectedAgent} onBack={goBackToRegistry} />
          ) : (
            <AgentListScreen onOpen={openAgent} />
          )}
        </div>
      </main>
    </div>
  )
}
