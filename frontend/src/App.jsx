import { useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  ArrowLeft,
  ArrowUpRight,
  CandlestickChart,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  ExternalLink,
  KeyRound,
  Layers3,
  Link2,
  Loader2,
  Radio,
  Search,
  Shield,
  Trash2,
  UserRoundPlus,
  Wallet,
} from "lucide-react"

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar.jsx"
import { Badge } from "@/components/ui/badge.jsx"
import { Button } from "@/components/ui/button.jsx"
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card.jsx"
import { Input } from "@/components/ui/input.jsx"
import { Separator } from "@/components/ui/separator.jsx"
import {
  API_BASE_URL,
  createAgent,
  deleteAgent,
  createSeller,
  getTransactions,
  getSeller,
  listMarketplaceAgents,
  updateToolPricing,
} from "@/api/marketplaceClient.js"
import { makeAgentCompositeId, mapMarketplaceAgentsToCards } from "@/lib/agentMappers.js"

const PAGE_SIZE = 9

function pushPath(pathname) {
  window.history.pushState({}, "", pathname)
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "auto" })
}

/** Full URL for POST invoke; clipboard APIs often fail silently if not awaited or if context is not secure. */
function resolveInvokeUrl(agent) {
  const path =
    agent.invokePath ||
    (agent.tools?.[0]?.toolId != null
      ? `/sellers/${agent.sellerId}/agents/${agent.agentId}/tools/${agent.tools[0].toolId}/invoke`
      : "")
  if (!path) return ""
  if (path.startsWith("http://") || path.startsWith("https://")) return path
  const normalized = path.startsWith("/") ? path : `/${path}`
  return `${API_BASE_URL}${normalized}`
}

async function copyTextToClipboard(text) {
  if (!text) return false
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text)
      return true
    }
  } catch {
    /* fall through */
  }
  try {
    const ta = document.createElement("textarea")
    ta.value = text
    ta.setAttribute("readonly", "")
    ta.style.position = "fixed"
    ta.style.left = "-9999px"
    document.body.appendChild(ta)
    ta.select()
    const ok = document.execCommand("copy")
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

function readRouteFromPath() {
  const pathname = window.location.pathname.replace(/\/+$/, "") || "/"

  if (pathname.startsWith("/transactions")) {
    return { page: "transactions" }
  }

  if (pathname === "/agents/register") {
    return { page: "register" }
  }

  const editMatch = pathname.match(/^\/agents\/([^/]+)\/edit$/)
  if (editMatch) {
    return { agentId: decodeURIComponent(editMatch[1]), page: "edit" }
  }

  const match = pathname.match(/^\/agents\/([^/]+)$/)
  if (!match) return null
  return { agentId: decodeURIComponent(match[1]), page: "detail" }
}

function normalizeSearch(value) {
  return value.trim().toLowerCase()
}

function formatClock(timestamp) {
  if (!timestamp) return "--:--:--"
  const date = new Date(timestamp)
  if (Number.isNaN(date.getTime())) return "--:--:--"
  return date.toLocaleTimeString([], { hour12: false })
}

function shortHash(value) {
  if (!value) return "Pending"
  if (value.length <= 16) return value
  return `${value.slice(0, 8)}...${value.slice(-8)}`
}

/** Arc Testnet explorer (Blockscout) — wallet + tx deep links */
const ARCSCAN_TESTNET_BASE = "https://testnet.arcscan.app"

function isHexAddress(value) {
  return typeof value === "string" && /^0x[a-fA-F0-9]{40}$/i.test(value.trim())
}

function isHexTxHash(value) {
  const raw = (value || "").trim()
  if (!raw || raw === "pending") return false
  const hex = raw.startsWith("0x") ? raw.slice(2) : raw
  return /^[a-fA-F0-9]{64}$/i.test(hex)
}

function explorerAddressUrl(address) {
  if (!isHexAddress(address)) return null
  return `${ARCSCAN_TESTNET_BASE}/address/${address.trim()}`
}

function explorerTxUrl(hash) {
  if (!isHexTxHash(hash)) return null
  const normalized = hash.trim().startsWith("0x") ? hash.trim().toLowerCase() : `0x${hash.trim().toLowerCase()}`
  return `${ARCSCAN_TESTNET_BASE}/tx/${normalized}`
}

function ExplorerAddressLink({ address, className = "" }) {
  const url = explorerAddressUrl(address)
  const label = shortHash(address)
  if (!url) {
    return <span className={`font-mono text-zinc-400 ${className}`.trim()}>{label}</span>
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer noopener"
      className={`font-mono text-sky-300 underline-offset-2 hover:text-sky-200 hover:underline ${className}`.trim()}
      title={address}
    >
      {label}
    </a>
  )
}

function ExplorerTxLink({ hash }) {
  const url = explorerTxUrl(hash)
  const label = shortHash(hash)
  if (!url) {
    return <span className="font-mono text-sky-300">{label}</span>
  }
  return (
    <a
      href={url}
      target="_blank"
      rel="noreferrer noopener"
      className="font-mono text-sky-300 underline-offset-2 hover:text-sky-200 hover:underline"
      title={hash}
    >
      {label}
    </a>
  )
}

function MetricCard({ dotClassName, icon: Icon, title, children }) {
  return (
    <Card className="rounded-2xl border-zinc-800 bg-[#0d0d0d] text-zinc-50 shadow-none">
      <CardHeader className="flex flex-row items-center gap-3 p-5 pb-4">
        <span className={`size-2 rounded-full ${dotClassName}`} />
        <Icon className="size-4 text-zinc-400" />
        <h2 className="text-[13px] font-bold uppercase tracking-[0.05em] text-zinc-100">{title}</h2>
      </CardHeader>
      <CardContent className="px-5 pb-5 pt-0">{children}</CardContent>
    </Card>
  )
}

function AgentCard({ agent, onOpen, onDelete, isDeleting }) {
  return (
    <Card
      className="group cursor-pointer rounded-xl border-zinc-800 bg-zinc-950/90 text-zinc-50 shadow-none transition-colors hover:border-zinc-700"
      onClick={() => onOpen(agent)}
      onKeyDown={(event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault()
          onOpen(agent)
        }
      }}
      role="button"
      tabIndex={0}
    >
      <CardHeader className="flex flex-row items-start gap-3 p-4 pb-3">
        <Avatar className="size-10 rounded-md border border-zinc-800">
          {agent.avatarImage ? <AvatarImage src={agent.avatarImage} alt={`${agent.name} avatar`} /> : null}
          <AvatarFallback
            className={`rounded-md bg-gradient-to-br ${agent.color} text-[11px] font-semibold text-white`}
          >
            {agent.avatar}
          </AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-[13px] font-semibold text-zinc-50">{agent.name}</h3>
            <span className="text-[10px] text-emerald-400">• {agent.status}</span>
          </div>
          <p className="mt-0.5 text-[10px] text-zinc-500">{agent.shortAddress}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          disabled={isDeleting}
          className="size-8 shrink-0 rounded-md text-zinc-500 hover:bg-zinc-900 hover:text-red-300"
          onClick={(event) => {
            event.preventDefault()
            event.stopPropagation()
            onDelete(agent)
          }}
          aria-label={`Delete ${agent.name}`}
        >
          {isDeleting ? <Loader2 className="size-4 animate-spin" /> : <Trash2 className="size-4" />}
        </Button>
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
              className="rounded-md border-zinc-700 bg-zinc-900 px-1.5 py-0 text-[9px] font-medium uppercase tracking-[0.12em] text-zinc-300"
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
      </CardContent>
      <CardFooter className="flex items-center gap-2 border-t border-zinc-900 px-4 py-3 text-[10px] text-zinc-500">
        <Wallet className="size-3.5" />
        <span>{agent.wallet}</span>
      </CardFooter>
    </Card>
  )
}

function AgentListScreen({
  agents,
  allCount,
  query,
  onQueryChange,
  onOpen,
  onRegister,
  page,
  pageCount,
  isLoading,
  loadError,
  onRetry,
  onPrevPage,
  onNextPage,
  onSelectPage,
  onDelete,
  deletingAgentIds,
}) {
  const pageStart = allCount === 0 ? 0 : (page - 1) * PAGE_SIZE + 1
  const pageEnd = Math.min(page * PAGE_SIZE, allCount)

  return (
    <section className="mx-auto max-w-[1060px]">
      <div className="flex flex-col gap-6 border-b border-zinc-900/80 pb-7 sm:flex-row sm:items-end sm:justify-between">
        <div className="max-w-2xl">
          <div className="mb-3 flex items-center gap-2 text-[11px] uppercase tracking-[0.22em] text-zinc-500">
            <Layers3 className="size-3.5 text-zinc-400" />
            Registry
          </div>
          <h1 className="text-[28px] font-semibold tracking-tight text-zinc-50">Agents</h1>
          <p className="mt-3 max-w-xl text-[15px] leading-7 text-zinc-400">
            On-chain registry of autonomous agents available through the Arc marketplace API.
          </p>
        </div>
        <Button
          variant="outline"
          className="h-10 self-start rounded-xl border-zinc-800 bg-zinc-950 px-4 text-xs font-medium text-zinc-100 shadow-none hover:bg-zinc-900"
          onClick={onRegister}
        >
          <UserRoundPlus data-icon="inline-start" />
          Register an Agent
        </Button>
      </div>

      <div className="mt-5 flex items-end gap-3 border-b border-zinc-900">
        <button className="border-b-2 border-[#2450ff] pb-3 text-sm font-semibold tracking-[0.02em] text-zinc-50">
          All Agents
          <Badge className="ml-2 rounded-sm bg-zinc-800 px-1.5 text-[9px] text-zinc-300 hover:bg-zinc-800">
            {allCount}
          </Badge>
        </button>
      </div>

      <div className="mt-4">
        <div className="relative w-full max-w-md">
          <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-500" />
          <Input
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder="Search agents by name, description, wallet, or tool..."
            className="h-9 rounded-md border-zinc-800 bg-transparent pl-9 text-sm text-zinc-200 placeholder:text-zinc-500 focus-visible:ring-0 focus-visible:ring-offset-0"
          />
        </div>
      </div>

      {isLoading ? (
        <div className="mt-8 flex items-center gap-2 text-sm text-zinc-400">
          <Loader2 className="size-4 animate-spin" />
          Loading agents from backend...
        </div>
      ) : null}

      {loadError ? (
        <div className="mt-8 rounded-xl border border-red-900/60 bg-red-950/20 p-4 text-sm text-red-200">
          <div className="flex items-start gap-2">
            <AlertCircle className="mt-0.5 size-4 shrink-0" />
            <div>
              <p className="font-medium">Could not load marketplace agents.</p>
              <p className="mt-1 text-red-300/90">{loadError}</p>
              <Button
                variant="outline"
                className="mt-3 h-8 rounded-md border-red-800 bg-red-950 px-3 text-xs text-red-100 hover:bg-red-900"
                onClick={onRetry}
              >
                Retry
              </Button>
            </div>
          </div>
        </div>
      ) : null}

      {!isLoading && !loadError && agents.length === 0 ? (
        <div className="mt-8 rounded-xl border border-zinc-800 bg-zinc-950/60 p-6 text-sm text-zinc-400">
          No agents found for this search.
        </div>
      ) : null}

      {!loadError ? (
        <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onOpen={onOpen}
              onDelete={onDelete}
              isDeleting={deletingAgentIds.has(agent.id)}
            />
          ))}
        </div>
      ) : null}

      <div className="mt-6 flex flex-col gap-4 border-t border-zinc-950 pt-5 text-xs text-zinc-500 sm:flex-row sm:items-center sm:justify-between">
        <p>
          Showing {pageStart}-{pageEnd} of {allCount} agents
        </p>
        <div className="flex items-center gap-1">
          <Button
            variant="outline"
            size="icon"
            disabled={page <= 1 || isLoading}
            onClick={onPrevPage}
            className="size-8 rounded-md border-zinc-900 bg-transparent text-zinc-500 hover:bg-zinc-950 hover:text-zinc-200 disabled:opacity-40"
          >
            <ChevronLeft />
          </Button>
          {Array.from({ length: pageCount }, (_, idx) => idx + 1).map((pageNumber) => (
            <Button
              key={pageNumber}
              variant="outline"
              disabled={isLoading}
              onClick={() => onSelectPage(pageNumber)}
              className={`size-8 rounded-md border-zinc-900 px-0 ${
                pageNumber === page
                  ? "bg-zinc-50 text-zinc-950 hover:bg-zinc-200"
                  : "bg-transparent text-zinc-300 hover:bg-zinc-950"
              }`}
            >
              {pageNumber}
            </Button>
          ))}
          <Button
            variant="outline"
            size="icon"
            disabled={page >= pageCount || isLoading}
            onClick={onNextPage}
            className="size-8 rounded-md border-zinc-900 bg-transparent text-zinc-500 hover:bg-zinc-950 hover:text-zinc-200 disabled:opacity-40"
          >
            <ChevronRight />
          </Button>
        </div>
      </div>
    </section>
  )
}

function RegisterAgentScreen({ onBack, onSubmit, isSubmitting, submitError }) {
  const steps = ["Identity", "Endpoint", "Review"]
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    imageName: "",
    imagePreviewDataUrl: "",
    agentName: "",
    agentDescription: "",
    wallet: "",
    metadataUri: "",
    apiDocsUrl: "",
    capabilities: [
      {
        toolKey: "invoke",
        name: "",
        description: "",
        category: "General",
        endpointUrl: "",
        httpMethod: "POST",
        priceUsdc: "0.01",
        runtimePriceUsdc: "0.00",
      },
    ],
  })

  function updateField(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
  }

  function updateCapability(index, key, value) {
    setForm((current) => ({
      ...current,
      capabilities: current.capabilities.map((capability, capabilityIndex) =>
        capabilityIndex === index ? { ...capability, [key]: value } : capability,
      ),
    }))
  }

  function addCapability() {
    setForm((current) => ({
      ...current,
      capabilities: [
        ...current.capabilities,
        {
          toolKey: `tool-${current.capabilities.length + 1}`,
          name: "",
          description: "",
          category: "General",
          endpointUrl: "",
          httpMethod: "POST",
          priceUsdc: "0.01",
          runtimePriceUsdc: "0.00",
        },
      ],
    }))
  }

  function removeCapability(index) {
    setForm((current) => ({
      ...current,
      capabilities:
        current.capabilities.length === 1
          ? current.capabilities
          : current.capabilities.filter((_, capabilityIndex) => capabilityIndex !== index),
    }))
  }

  function nextStep() {
    setStep((current) => Math.min(current + 1, steps.length - 1))
  }

  function previousStep() {
    if (step === 0) {
      onBack()
      return
    }
    setStep((current) => Math.max(current - 1, 0))
  }

  function finishRegistration() {
    onSubmit(form)
  }

  function handleImageChange(event) {
    const file = event.target.files?.[0]
    if (!file) return
    updateField("imageName", file.name)

    const reader = new FileReader()
    reader.onload = () => {
      updateField("imagePreviewDataUrl", typeof reader.result === "string" ? reader.result : "")
    }
    reader.readAsDataURL(file)
  }

  const progress = ((step + 1) / steps.length) * 100
  const initials =
    form.agentName
      .split(" ")
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join("") || "AG"

  return (
    <section className="mx-auto max-w-[860px] py-8">
      <div className="rounded-[28px] border border-zinc-800 bg-[#0f0f10] px-6 py-7 shadow-none sm:px-8">
        <div className="flex flex-col gap-4">
          <h1 className="text-[24px] font-semibold tracking-tight text-zinc-50">Create Agent</h1>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {steps.map((label, index) => (
            <div
              key={label}
              className={`rounded-full px-4 py-1.5 text-sm ${
                index === step
                  ? "border border-zinc-700 bg-[#111214] text-zinc-50"
                  : "bg-zinc-800 text-zinc-400"
              }`}
            >
              {`${index + 1}.${label}`}
            </div>
          ))}
        </div>

        <div className="mt-4 h-2 overflow-hidden rounded-full bg-zinc-800">
          <div className="h-full bg-[#2450ff] transition-all" style={{ width: `${progress}%` }} />
        </div>

        {submitError ? (
          <div className="mt-5 rounded-xl border border-red-900/60 bg-red-950/20 p-3 text-sm text-red-200">
            {submitError}
          </div>
        ) : null}

        <div className="mt-8">
          {step === 0 ? (
            <div className="space-y-6">
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">Agent Icon (optional)</span>
                <label className="flex min-h-[120px] cursor-pointer items-center justify-center rounded-2xl border border-dashed border-zinc-800 bg-[#111111] px-6 text-center">
                  <input type="file" accept="image/*" className="hidden" onChange={handleImageChange} />
                  <div>
                    {form.imagePreviewDataUrl ? (
                      <img
                        src={form.imagePreviewDataUrl}
                        alt="Agent icon preview"
                        className="mx-auto mb-3 h-12 w-12 rounded-xl border border-zinc-700 object-cover"
                      />
                    ) : (
                      <div className="mx-auto mb-3 flex size-10 items-center justify-center rounded-xl border border-zinc-700 text-zinc-500">
                        +
                      </div>
                    )}
                    <p className="text-sm text-zinc-400">
                      {form.imageName || "Click to upload PNG/JPG/WebP/GIF"}
                    </p>
                  </div>
                </label>
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Agent Name <span className="text-red-400">*</span>
                </span>
                <Input
                  value={form.agentName}
                  onChange={(event) => updateField("agentName", event.target.value)}
                  placeholder="Liquidity Sentinel"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Agent Description <span className="text-red-400">*</span>
                </span>
                <textarea
                  value={form.agentDescription}
                  onChange={(event) => updateField("agentDescription", event.target.value)}
                  className="min-h-[140px] w-full rounded-xl border border-zinc-800 bg-[#111111] px-4 py-3 text-sm text-zinc-100 outline-none transition-colors focus:border-zinc-700"
                />
              </label>
            </div>
          ) : null}

          {step === 1 ? (
            <div className="space-y-5">
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Wallet Address (optional)
                </span>
                <Input
                  value={form.wallet}
                  onChange={(event) => updateField("wallet", event.target.value)}
                  placeholder="0x..."
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
                <p className="mt-2 text-xs text-zinc-500">
                  Circle wallets are provisioned automatically if this is empty.
                </p>
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">API Docs URL</span>
                <Input
                  value={form.apiDocsUrl}
                  onChange={(event) => updateField("apiDocsUrl", event.target.value)}
                  placeholder="https://docs.example.com"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Metadata / A2A URL
                </span>
                <Input
                  value={form.metadataUri}
                  onChange={(event) => updateField("metadataUri", event.target.value)}
                  placeholder="https://your-agent.example/.well-known/agent-card.json"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-[16px] text-zinc-100">Capabilities</p>
                    <p className="mt-1 text-xs text-zinc-500">Each capability becomes a priced tool on the marketplace.</p>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    className="rounded-lg border-zinc-800 bg-[#111111] text-zinc-100 hover:bg-zinc-900"
                    onClick={addCapability}
                  >
                    Add Capability
                  </Button>
                </div>
                {form.capabilities.map((capability, capabilityIndex) => (
                  <div
                    key={`${capability.toolKey}-${capabilityIndex}`}
                    className="rounded-2xl border border-zinc-800 bg-[#111111] p-4"
                  >
                    <div className="mb-4 flex items-center justify-between">
                      <p className="text-sm font-medium text-zinc-100">Capability {capabilityIndex + 1}</p>
                      {form.capabilities.length > 1 ? (
                        <button
                          type="button"
                          className="text-xs text-zinc-500 hover:text-zinc-100"
                          onClick={() => removeCapability(capabilityIndex)}
                        >
                          Remove
                        </button>
                      ) : null}
                    </div>
                    <div className="grid gap-4 sm:grid-cols-2">
                      <label className="block">
                        <span className="mb-2 block text-sm text-zinc-100">Capability Key</span>
                        <Input
                          value={capability.toolKey}
                          onChange={(event) => updateCapability(capabilityIndex, "toolKey", event.target.value)}
                          placeholder="analyze-risk"
                          className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                        />
                      </label>
                      <label className="block">
                        <span className="mb-2 block text-sm text-zinc-100">Name</span>
                        <Input
                          value={capability.name}
                          onChange={(event) => updateCapability(capabilityIndex, "name", event.target.value)}
                          placeholder="Analyze Risk"
                          className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                        />
                      </label>
                      <label className="block sm:col-span-2">
                        <span className="mb-2 block text-sm text-zinc-100">Endpoint URL</span>
                        <Input
                          value={capability.endpointUrl}
                          onChange={(event) => updateCapability(capabilityIndex, "endpointUrl", event.target.value)}
                          placeholder="https://api.example.com/agent/analyze"
                          className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                        />
                      </label>
                      <label className="block sm:col-span-2">
                        <span className="mb-2 block text-sm text-zinc-100">Description</span>
                        <textarea
                          value={capability.description}
                          onChange={(event) => updateCapability(capabilityIndex, "description", event.target.value)}
                          className="min-h-[92px] w-full rounded-xl border border-zinc-800 bg-[#0d0d0d] px-4 py-3 text-sm text-zinc-100 outline-none transition-colors focus:border-zinc-700"
                        />
                      </label>
                      <label className="block">
                        <span className="mb-2 block text-sm text-zinc-100">Category</span>
                        <Input
                          value={capability.category}
                          onChange={(event) => updateCapability(capabilityIndex, "category", event.target.value)}
                          placeholder="Analytics"
                          className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                        />
                      </label>
                      <label className="block">
                        <span className="mb-2 block text-sm text-zinc-100">HTTP Method</span>
                        <select
                          value={capability.httpMethod}
                          onChange={(event) => updateCapability(capabilityIndex, "httpMethod", event.target.value)}
                          className="h-11 w-full rounded-xl border border-zinc-800 bg-[#0d0d0d] px-4 text-sm text-zinc-100 outline-none transition-colors focus:border-zinc-700"
                        >
                          <option>POST</option>
                          <option>GET</option>
                        </select>
                      </label>
                      <label className="block">
                        <span className="mb-2 block text-sm text-zinc-100">Tool Price (USDC)</span>
                        <Input
                          value={capability.priceUsdc}
                          onChange={(event) => updateCapability(capabilityIndex, "priceUsdc", event.target.value)}
                          placeholder="0.01"
                          className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                        />
                      </label>
                      <label className="block">
                        <span className="mb-2 block text-sm text-zinc-100">Runtime Price / Request</span>
                        <Input
                          value={capability.runtimePriceUsdc}
                          onChange={(event) =>
                            updateCapability(capabilityIndex, "runtimePriceUsdc", event.target.value)
                          }
                          placeholder="0.00"
                          className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                        />
                      </label>
                    </div>
                    <div className="mt-4 rounded-xl border border-zinc-800 bg-[#0d0d0d] p-4">
                      <p className="text-xs text-zinc-500">
                        Billable skills are disabled in this version. Pricing is tool + optional runtime only.
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="rounded-2xl border border-zinc-800 bg-[#111111] p-5">
              <div className="flex items-start gap-4">
                <div className="flex size-14 items-center justify-center rounded-2xl border border-zinc-800 bg-zinc-900 text-lg font-semibold text-zinc-50">
                  {form.imagePreviewDataUrl ? (
                    <img
                      src={form.imagePreviewDataUrl}
                      alt="Agent preview icon"
                      className="size-14 rounded-2xl object-cover"
                    />
                  ) : (
                    initials
                  )}
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="truncate text-xl font-semibold text-zinc-50">
                    {form.agentName || "Agent Name"}
                  </h3>
                  <p className="mt-2 text-sm text-zinc-500">{form.wallet || "Wallet address"}</p>
                  <p className="mt-4 text-sm leading-6 text-zinc-400">
                    {form.agentDescription || "Agent description"}
                  </p>
                </div>
              </div>
              <div className="mt-4 grid gap-3 text-sm text-zinc-300 sm:grid-cols-2">
                <p>
                  <span className="text-zinc-500">Seller:</span>{" "}
                  {(form.agentName.trim() && `${form.agentName.trim()} Studio`) || "Auto-generated"}
                </p>
                <p>
                  <span className="text-zinc-500">Capabilities:</span> {form.capabilities.length}
                </p>
                <p>
                  <span className="text-zinc-500">Primary Endpoint:</span> {form.capabilities[0]?.endpointUrl || "Not set"}
                </p>
                <p>
                  <span className="text-zinc-500">Starting Price:</span> {form.capabilities[0]?.priceUsdc || "Not set"} USDC
                </p>
                <p className="sm:col-span-2">
                  <span className="text-zinc-500">Catalog:</span>{" "}
                  {form.capabilities.map((capability) => capability.name || capability.toolKey || "Capability").join(", ")}
                </p>
              </div>
            </div>
          ) : null}
        </div>

        <div className="mt-8 flex items-center justify-between">
          <Button
            variant="secondary"
            className="h-10 rounded-lg bg-zinc-800 px-4 text-zinc-100 hover:bg-zinc-700"
            onClick={previousStep}
            disabled={isSubmitting}
          >
            {step === 0 ? "Back" : "Previous"}
          </Button>
          <Button
            className="h-10 rounded-lg bg-zinc-50 px-5 text-zinc-950 hover:bg-zinc-200"
            onClick={step === steps.length - 1 ? finishRegistration : nextStep}
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <Loader2 className="size-4 animate-spin" />
                Creating...
              </>
            ) : step === steps.length - 1 ? (
              "Finish"
            ) : (
              "Continue"
            )}
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
      <span className="font-mono text-zinc-100">{value}</span>
    </div>
  )
}

function AgentEditScreen({ agent, onBack, onSavePricing, isSubmitting, submitError }) {
  const [toolForms, setToolForms] = useState(
    () =>
      (agent.tools || []).map((tool) => ({
        toolId: tool.toolId,
        name: tool.name,
        toolPriceUSDC: String(tool.priceUSDC ?? "0.01"),
        runtimePriceUSDC: String(tool.runtimePriceUSDC ?? "0"),
      })) || [],
  )

  function handleSubmit(event) {
    event.preventDefault()
    onSavePricing(toolForms)
  }

  function updateTool(index, key, value) {
    setToolForms((current) =>
      current.map((tool, toolIndex) => (toolIndex === index ? { ...tool, [key]: value } : tool)),
    )
  }

  return (
    <section className="mx-auto max-w-[860px] py-8">
      <button
        onClick={onBack}
        className="mb-6 inline-flex items-center gap-1.5 text-sm text-zinc-400 transition-colors hover:text-zinc-100"
      >
        <ArrowLeft className="size-4" />
        Back to Registry
      </button>

      <Card className="rounded-2xl border-zinc-800 bg-[#0d0d0d] text-zinc-50 shadow-none">
        <CardHeader className="space-y-2 p-6">
          <h1 className="text-xl font-semibold">Update Capability Pricing</h1>
          <p className="text-sm text-zinc-400">
            Each capability settles on-chain. Update the tool charge and optional runtime charge.
          </p>
        </CardHeader>
        <CardContent className="space-y-4 p-6 pt-0 text-sm text-zinc-300">
          <p>
            <span className="text-zinc-500">Agent:</span> {agent.name}
          </p>
          <p>
            <span className="text-zinc-500">Status:</span> {agent.status}
          </p>
          <p>
            <span className="text-zinc-500">Seller:</span> {agent.owner}
          </p>
          <form className="space-y-4" onSubmit={handleSubmit}>
            {toolForms.map((tool, toolIndex) => (
              <div key={tool.toolId} className="rounded-xl border border-zinc-800 bg-[#111111] p-4">
                <p className="mb-3 text-sm font-medium text-zinc-100">{tool.name}</p>
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="block">
                    <span className="mb-2 block text-zinc-100">Tool Price (USDC)</span>
                    <Input
                      value={tool.toolPriceUSDC}
                      onChange={(event) => updateTool(toolIndex, "toolPriceUSDC", event.target.value)}
                      placeholder="0.01"
                      className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                    />
                  </label>
                  <label className="block">
                    <span className="mb-2 block text-zinc-100">Runtime Price / Request</span>
                    <Input
                      value={tool.runtimePriceUSDC}
                      onChange={(event) => updateTool(toolIndex, "runtimePriceUSDC", event.target.value)}
                      placeholder="0.00"
                      className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
                    />
                  </label>
                </div>
                <div className="mt-4 rounded-xl border border-zinc-800 bg-[#0d0d0d] p-3 text-xs text-zinc-500">
                  Billable skills are disabled in this version.
                </div>
              </div>
            ))}
            {submitError ? (
              <div className="rounded-lg border border-red-900/60 bg-red-950/20 p-2 text-xs text-red-200">
                {submitError}
              </div>
            ) : null}
            <div className="flex items-center gap-2">
              <Button
                type="submit"
                className="h-9 rounded-lg bg-zinc-50 px-4 text-zinc-950 hover:bg-zinc-200"
                disabled={isSubmitting}
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Saving...
                  </>
                ) : (
                  "Save Capability Pricing"
                )}
              </Button>
              <Button
                type="button"
                variant="outline"
                className="h-9 rounded-lg border-zinc-700 bg-zinc-950 px-4 text-zinc-100 hover:bg-zinc-900"
                onClick={onBack}
                disabled={isSubmitting}
              >
                Cancel
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </section>
  )
}

function AgentDetailScreen({ agent, onBack, onEditPricing }) {
  const sellerBalances = agent.sellerBalances || {}
  const [invokeCopied, setInvokeCopied] = useState(false)

  useEffect(() => {
    setInvokeCopied(false)
  }, [agent.id])

  async function handleCopyInvokeUrl() {
    const url = resolveInvokeUrl(agent)
    if (!url) {
      window.alert("No invoke URL is available yet for this agent.")
      return
    }
    const ok = await copyTextToClipboard(url)
    if (ok) {
      setInvokeCopied(true)
      window.setTimeout(() => setInvokeCopied(false), 2000)
    } else {
      window.prompt("Clipboard was blocked. Copy this URL manually:", url)
    }
  }

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
          {agent.avatarImage ? <AvatarImage src={agent.avatarImage} alt={`${agent.name} avatar`} /> : null}
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
            <Badge className="rounded-md border border-emerald-500/30 bg-emerald-500/15 px-3 py-1 text-[13px] text-emerald-400 hover:bg-emerald-500/15">
              • {agent.status}
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-zinc-400">
            <span className="inline-flex items-center gap-1.5 font-mono">
              {agent.shortAddress}
              <Copy className="size-3.5" />
            </span>
            <span>·</span>
            <span>{agent.assetType}</span>
          </div>
          <p className="max-w-3xl text-[15px] leading-7 text-zinc-300">{agent.description}</p>
          <div className="flex flex-wrap gap-3 pt-1">
            {agent.tags.map((tag) => (
              <Badge
                key={tag}
                variant="outline"
                className="rounded-md border-violet-500/40 bg-violet-500/10 px-3 py-1 text-[13px] text-violet-300"
              >
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      </div>

      <div className="mt-7 grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="space-y-6 lg:col-span-8">
          <MetricCard dotClassName="bg-blue-500" icon={Wallet} title="Service Catalog">
            <div className="space-y-4">
              {(agent.tools || []).map((tool) => (
                <div key={tool.toolId} className="rounded-xl border border-zinc-800 bg-zinc-950/70 p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-medium text-zinc-100">{tool.name}</p>
                    <Badge
                      variant="outline"
                      className="rounded-md border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-300"
                    >
                      {tool.toolKey}
                    </Badge>
                    <Badge
                      variant="outline"
                      className="rounded-md border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-300"
                    >
                      {Number(tool.priceUSDC || 0).toFixed(4)} USDC
                    </Badge>
                    {Number(tool.runtimePriceUSDC || 0) > 0 ? (
                      <Badge
                        variant="outline"
                        className="rounded-md border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[10px] text-zinc-300"
                      >
                        Runtime {Number(tool.runtimePriceUSDC || 0).toFixed(4)} USDC
                      </Badge>
                    ) : null}
                  </div>
                  <p className="mt-2 text-sm text-zinc-400">{tool.description || "No description provided."}</p>
                  <div className="mt-3 grid gap-2 text-sm text-zinc-300 sm:grid-cols-2">
                    <p>
                      <span className="text-zinc-500">Endpoint:</span> {tool.endpointUrl}
                    </p>
                    <p>
                      <span className="text-zinc-500">Method:</span> {tool.httpMethod}
                    </p>
                    <p>
                      <span className="text-zinc-500">Category:</span> {tool.category}
                    </p>
                    <p>
                      <span className="text-zinc-500">Runtime Unit:</span> {tool.runtimeUnit}
                    </p>
                  </div>
                  <div className="mt-3 rounded-md border border-zinc-800 bg-zinc-900/30 px-3 py-2 text-[11px] text-zinc-500">
                    Billable skills disabled
                  </div>
                </div>
              ))}
            </div>
          </MetricCard>

          <MetricCard dotClassName="bg-amber-500" icon={Layers3} title="Commercial Terms">
            <div className="space-y-4">
              <div className="grid gap-2 text-sm text-zinc-300 sm:grid-cols-2">
                <p>
                  <span className="text-zinc-500">Pricing Model:</span> {agent.profile?.pricingModel}
                </p>
                <p>
                  <span className="text-zinc-500">Starting Price (USDC):</span> {agent.profile?.basePriceUsdc}
                </p>
                <p className="sm:col-span-2">
                  <span className="text-zinc-500">Capabilities:</span> {agent.toolCount} tools
                </p>
              </div>
            </div>
          </MetricCard>

          <MetricCard dotClassName="bg-emerald-500" icon={Shield} title="Trust & Compliance">
            <div className="space-y-4">
              <div>
                <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">Trust Signals</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(agent.profile?.trustSignals || []).map((signal) => (
                    <Badge
                      key={signal}
                      variant="outline"
                      className="rounded-md border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[11px] text-zinc-300"
                    >
                      {signal}
                    </Badge>
                  ))}
                </div>
              </div>
              <Separator className="bg-zinc-800" />
              <div>
                <p className="text-[12px] uppercase tracking-[0.14em] text-zinc-500">Payment Protocol</p>
                <div className="mt-3 inline-flex rounded-md bg-zinc-800 px-4 py-2 text-sm text-zinc-300">
                  {agent.paymentProtocol}
                </div>
              </div>
              <div className="grid gap-2 text-sm text-zinc-300 sm:grid-cols-2">
                <p>
                  <span className="text-zinc-500">Network:</span> {agent.profile?.network}
                </p>
                <p>
                  <span className="text-zinc-500">Arc Agent ID:</span> {agent.profile?.arcAgentId || "Pending"}
                </p>
                <p className="sm:col-span-2">
                  <span className="text-zinc-500">Identity Tx:</span>{" "}
                  {agent.profile?.identityTxHash || "Pending"}
                </p>
              </div>
            </div>
          </MetricCard>

          <div className="rounded-2xl border border-zinc-800 bg-[#0d0d0d]">
            <details>
              <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm text-zinc-400 transition-colors hover:text-zinc-100">
                <ChevronDown className="size-4" />
                <Copy className="size-4" />
                <span className="font-medium uppercase tracking-[0.04em]">Raw Metadata</span>
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
                <DetailRow icon={Layers3} label="Composite Agent ID" value={agent.id} />
                <DetailRow icon={Wallet} label="Seller Wallet" value={agent.wallet} />
                <DetailRow
                  icon={Wallet}
                  label="Seller USDC Balance"
                  value={sellerBalances.usdc ?? "Unavailable"}
                />
                <DetailRow icon={UserRoundPlus} label="Seller" value={agent.owner} />
                <DetailRow icon={KeyRound} label="Authority" value={agent.authority} />
              </div>
              <div className="space-y-2 pt-4">
                <Button
                  variant="outline"
                  className="h-8 w-full justify-center gap-1.5 rounded-md border-zinc-800 bg-zinc-950 text-xs text-zinc-100 hover:bg-zinc-900"
                  type="button"
                  onClick={() => void handleCopyInvokeUrl()}
                >
                  <ExternalLink data-icon="inline-start" />
                  {invokeCopied ? "Copied" : agent.explorerLabel}
                </Button>
                <Button
                  variant="outline"
                  className="h-8 w-full justify-center gap-1.5 rounded-md border-zinc-800 bg-zinc-950 text-xs text-zinc-100 hover:bg-zinc-900"
                  onClick={() => onEditPricing(agent)}
                >
                  <ArrowUpRight data-icon="inline-start" />
                  Update Pricing
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  )
}

function TransactionsScreen({ transactionsState, isLoading, loadError, onRefresh }) {
  const events = transactionsState?.events || []
  const summary = transactionsState?.summary || {}
  const buyers = transactionsState?.buyers || []
  const txRows = events.filter((event) => event.eventType === "payment")
  const latestRows = txRows.slice(0, 40)

  return (
    <section className="mx-auto max-w-[1240px]">
      <Card className="rounded-2xl border-zinc-800 bg-[#0b0e13] text-zinc-100 shadow-none">
        <CardHeader className="border-b border-zinc-800 p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <CandlestickChart className="size-4 text-sky-300" />
              <p className="text-sm font-semibold tracking-wide text-zinc-100">Arc Transaction Explorer</p>
              <Badge className="rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-300 hover:bg-emerald-500/15">
                <Radio className="mr-1 size-3" />
                LIVE
              </Badge>
            </div>
            <Button
              variant="outline"
              className="h-8 rounded-md border-zinc-700 bg-zinc-950 px-3 text-xs text-zinc-200 hover:bg-zinc-900"
              onClick={onRefresh}
            >
              Refresh
            </Button>
          </div>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">Total Txs</p>
              <p className="mt-1 text-lg font-semibold text-zinc-100">{summary.total ?? 0}</p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">Paid</p>
              <p className="mt-1 text-lg font-semibold text-emerald-300">{summary.paid ?? 0}</p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">Pay Volume</p>
              <p className="mt-1 text-lg font-semibold text-sky-300">{summary.totalPaidAmountUSDC || "0.000000"} USDC</p>
            </div>
            <div className="rounded-lg border border-zinc-800 bg-zinc-950/70 px-3 py-2">
              <p className="text-[10px] uppercase tracking-[0.12em] text-zinc-500">Unique Buyers</p>
              <p className="mt-1 text-lg font-semibold text-violet-300">{summary.uniqueBuyers ?? 0}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          <div className="border-b border-zinc-800 bg-zinc-950/60 px-4 py-2 text-[11px] uppercase tracking-[0.1em] text-zinc-400">
            Transactions
          </div>
          {loadError ? (
            <div className="m-4 rounded-lg border border-red-900/60 bg-red-950/20 p-3 text-sm text-red-200">{loadError}</div>
          ) : null}
          {isLoading ? (
            <div className="m-4 flex items-center gap-2 text-sm text-zinc-300">
              <Loader2 className="size-4 animate-spin" />
              Loading latest chain activity...
            </div>
          ) : null}
          <div className="max-h-[540px] overflow-auto">
            <table className="w-full min-w-[980px] text-left text-xs">
              <thead className="sticky top-0 bg-[#0b0e13] text-zinc-500">
                <tr>
                  <th className="px-4 py-2 font-medium">Txn Hash</th>
                  <th className="px-4 py-2 font-medium">Method</th>
                  <th className="px-4 py-2 font-medium">Block Time</th>
                  <th className="px-4 py-2 font-medium">From</th>
                  <th className="px-4 py-2 font-medium">To</th>
                  <th className="px-4 py-2 font-medium">Value (USDC)</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {latestRows.map((event, idx) => {
                  const details = event.details || {}
                  const statusClass =
                    event.status === "paid" || event.status === "completed"
                      ? "text-emerald-300"
                      : event.status === "failed" || event.status === "provider_failed"
                        ? "text-red-300"
                        : "text-amber-300"
                  const hash = event.onchainTxHash || event.transactionRef || "pending"
                  const fromAddr = details.payer || details.buyerAddress || "n/a"
                  const toAddr = details.payee || details.sellerRecipientAddress || "n/a"
                  return (
                    <tr key={`${event.timestamp || "none"}-${idx}`} className="border-t border-zinc-800/90">
                      <td className="px-4 py-2">
                        <ExplorerTxLink hash={hash} />
                      </td>
                      <td className="px-4 py-2 text-zinc-300">{event.eventType}</td>
                      <td className="px-4 py-2 text-zinc-300">{formatClock(event.timestamp)}</td>
                      <td className="px-4 py-2">
                        <ExplorerAddressLink address={fromAddr} />
                      </td>
                      <td className="px-4 py-2">
                        <ExplorerAddressLink address={toAddr} />
                      </td>
                      <td className="px-4 py-2 text-zinc-200">{details.amountUSDC || "0.000000"}</td>
                      <td className={`px-4 py-2 uppercase tracking-[0.12em] ${statusClass}`}>{event.status}</td>
                    </tr>
                  )
                })}
                {!latestRows.length ? (
                  <tr>
                    <td className="px-4 py-4 text-zinc-500" colSpan={7}>
                      No payment transactions yet.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card className="rounded-xl border-zinc-800 bg-[#0b0e13] text-zinc-100 shadow-none">
          <CardHeader className="p-4 pb-2">
            <p className="text-xs uppercase tracking-[0.12em] text-zinc-400">Live Tape</p>
          </CardHeader>
          <CardContent className="px-0 pb-4 pt-0">
            <div className="overflow-hidden border-y border-zinc-800/80 bg-zinc-950/60 py-2">
              <div className="transactions-ticker whitespace-nowrap px-4 text-xs text-zinc-300">
                {(events.slice(0, 16).length
                  ? events.slice(0, 16)
                  : [{ status: "idle", details: {}, eventType: "waiting", timestamp: "" }]
                ).map((event, idx) => (
                  <span key={`${event.timestamp || "none"}-${idx}`} className="mr-6 inline-flex items-center gap-2">
                    <span className="text-zinc-500">{formatClock(event.timestamp)}</span>
                    <span className="uppercase tracking-[0.12em] text-zinc-300">{event.eventType}</span>
                    <span className="text-zinc-400">{event.details?.amountUSDC || "0.000000"} USDC</span>
                    <span className="text-emerald-300">{event.status}</span>
                  </span>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="rounded-xl border-zinc-800 bg-[#0b0e13] text-zinc-100 shadow-none">
          <CardHeader className="p-4 pb-2">
            <p className="text-xs uppercase tracking-[0.12em] text-zinc-400">Top Buyer Wallets</p>
          </CardHeader>
          <CardContent className="space-y-2 p-4 pt-2">
            {buyers.slice(0, 8).map((buyer) => (
              <div key={buyer.buyerAddress} className="flex items-center justify-between rounded-md border border-zinc-800 bg-zinc-950/60 px-3 py-2">
                <ExplorerAddressLink address={buyer.buyerAddress} className="text-[11px]" />
                <span className="text-[11px] text-zinc-400">{buyer.paymentsCount} trades</span>
                <span className="text-[11px] text-sky-300">{buyer.totalAmountUSDC} USDC</span>
              </div>
            ))}
            {buyers.length === 0 ? <p className="text-xs text-zinc-500">No buyer activity yet.</p> : null}
          </CardContent>
        </Card>
      </div>
    </section>
  )
}

export default function App() {
  const [agents, setAgents] = useState([])
  const [routeState, setRouteState] = useState(() => readRouteFromPath())
  const [selectedAgentDetail, setSelectedAgentDetail] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const [query, setQuery] = useState("")
  const [page, setPage] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState("")
  const [isPricingSubmitting, setIsPricingSubmitting] = useState(false)
  const [pricingSubmitError, setPricingSubmitError] = useState("")
  const [deletingAgentIds, setDeletingAgentIds] = useState(() => new Set())
  const [transactionsState, setTransactionsState] = useState({ events: [], summary: {}, buyers: [] })
  const [isTransactionsLoading, setIsTransactionsLoading] = useState(false)
  const [transactionsError, setTransactionsError] = useState("")
  const mergedAgents = agents
  const selectedAgent = mergedAgents.find((agent) => agent.id === routeState?.agentId) ?? null
  const selectedAgentView = selectedAgent
    ? {
        ...selectedAgent,
        tools: selectedAgentDetail?.tools || selectedAgent.tools || [],
        sellerBalances: selectedAgentDetail?.sellerBalances || null,
      }
    : null

  async function refreshAgents({ showLoading = true } = {}) {
    if (showLoading) setIsLoading(true)
    setLoadError("")

    try {
      const marketplaceAgents = await listMarketplaceAgents()
      setAgents(mapMarketplaceAgentsToCards(marketplaceAgents))
    } catch (error) {
      setLoadError(error.message || "Unknown error while fetching agents.")
      setAgents([])
    } finally {
      setIsLoading(false)
    }
  }

  async function refreshTransactions({ silent = false } = {}) {
    if (!silent) setIsTransactionsLoading(true)
    setTransactionsError("")
    try {
      const payload = await getTransactions()
      setTransactionsState({
        events: payload?.events || [],
        summary: payload?.summary || {},
        buyers: payload?.buyers || [],
      })
    } catch (error) {
      setTransactionsError(error.message || "Could not load transactions.")
      setTransactionsState({ events: [], summary: {}, buyers: [] })
    } finally {
      if (!silent) setIsTransactionsLoading(false)
    }
  }

  useEffect(() => {
    refreshAgents()
  }, [])

  useEffect(() => {
    if (routeState?.page !== "transactions") return undefined
    refreshTransactions()
    const intervalId = window.setInterval(() => {
      refreshTransactions({ silent: true })
    }, 4000)
    return () => window.clearInterval(intervalId)
  }, [routeState?.page])

  useEffect(() => {
    const handlePopState = () => setRouteState(readRouteFromPath())
    window.addEventListener("popstate", handlePopState)
    return () => window.removeEventListener("popstate", handlePopState)
  }, [])

  useEffect(() => {
    document.title =
      routeState?.page === "transactions"
        ? "Live Transactions | ARC-Agents"
        : routeState?.page === "register"
        ? "Register Agent | ARC-Agents"
        : selectedAgent
          ? `${selectedAgent.name} | ARC-Agents`
          : "ARC-Agents"
  }, [routeState?.page, selectedAgent])

  useEffect(() => {
    setPage(1)
  }, [query])

  useEffect(() => {
    let ignore = false
    async function loadAgentDetail() {
      if (!selectedAgent) {
        setSelectedAgentDetail(null)
        return
      }
      try {
        const sellerPayload = await getSeller(selectedAgent.sellerId)
        const detailAgent = (sellerPayload.agents || []).find((agent) => agent.id === selectedAgent.agentId)
        if (ignore || !detailAgent) return
        setSelectedAgentDetail({
          tools: detailAgent.tools || [],
          sellerBalances: sellerPayload.balances || null,
        })
      } catch {
        if (!ignore) {
          setSelectedAgentDetail(null)
        }
      }
    }
    loadAgentDetail()
    return () => {
      ignore = true
    }
  }, [selectedAgent])

  const filteredAgents = useMemo(() => {
    const normalized = normalizeSearch(query)
    if (!normalized) return mergedAgents
    return mergedAgents.filter((agent) => agent.searchableText.includes(normalized))
  }, [mergedAgents, query])

  const pageCount = Math.max(1, Math.ceil(filteredAgents.length / PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pagedAgents = filteredAgents.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)

  function openAgent(agent, pageName = "detail") {
    const basePath = `/agents/${encodeURIComponent(agent.id)}`
    const pathname = pageName === "edit" ? `${basePath}/edit` : basePath
    pushPath(pathname)
    scrollToTop()
    setRouteState({ agentId: agent.id, page: pageName })
  }

  function goBackToRegistry() {
    pushPath("/")
    scrollToTop()
    setRouteState(null)
  }

  function openRegisterScreen() {
    setSubmitError("")
    pushPath("/agents/register")
    scrollToTop()
    setRouteState({ page: "register" })
  }

  function openTransactionsScreen() {
    pushPath("/transactions")
    scrollToTop()
    setRouteState({ page: "transactions" })
  }

  async function registerAgent(form) {
    setIsSubmitting(true)
    setSubmitError("")

    try {
      const agentName = form.agentName.trim() || "Untitled Agent"
      const agentDescription = form.agentDescription.trim() || ""
      if (!agentDescription) {
        throw new Error("Agent description is required.")
      }
      if (!form.capabilities.length) {
        throw new Error("At least one capability is required.")
      }
      const capabilities = form.capabilities.map((capability, index) => {
        const toolPrice = Number(capability.priceUsdc)
        const runtimePrice = Number(capability.runtimePriceUsdc || "0")
        if (!capability.endpointUrl.trim()) {
          throw new Error(`Capability ${index + 1} endpoint URL is required.`)
        }
        if (!Number.isFinite(toolPrice) || toolPrice <= 0 || toolPrice > 0.01) {
          throw new Error(`Capability ${index + 1} tool price must be greater than 0 and no more than 0.01 USDC.`)
        }
        if (!Number.isFinite(runtimePrice) || runtimePrice < 0 || runtimePrice > 0.01) {
          throw new Error(`Capability ${index + 1} runtime price must be between 0 and 0.01 USDC.`)
        }
        return {
          toolKey: capability.toolKey.trim() || `tool-${index + 1}`,
          name: capability.name.trim() || `Capability ${index + 1}`,
          description: capability.description.trim() || agentDescription,
          category: capability.category.trim() || "General",
          endpointUrl: capability.endpointUrl.trim(),
          httpMethod: capability.httpMethod,
          priceUSDC: toolPrice,
          runtimePriceUSDC: runtimePrice,
          runtimeUnit: runtimePrice > 0 ? "per_request" : "none",
          skills: [],
        }
      })
      const seller = await createSeller({
        name: `${agentName} Studio`,
        description: `Seller profile for ${agentName}`,
        ownerWalletAddress: form.wallet.trim(),
        validatorWalletAddress: "",
      })

      const agent = await createAgent(seller.id, {
        name: agentName,
        description: agentDescription,
        category: capabilities[0]?.category || "General",
        endpointUrl: capabilities[0]?.endpointUrl || "",
        httpMethod: capabilities[0]?.httpMethod || "POST",
        priceUSDC: capabilities[0]?.priceUSDC || 0.01,
        apiDocsUrl: form.apiDocsUrl.trim(),
        metadataUri: form.metadataUri.trim(),
        iconDataUrl: form.imagePreviewDataUrl || "",
        capabilities,
      })

      const createdId = makeAgentCompositeId(seller.id, agent.id)
      await refreshAgents({ showLoading: false })

      pushPath(`/agents/${encodeURIComponent(createdId)}`)
      scrollToTop()
      setRouteState({ agentId: createdId, page: "detail" })
    } catch (error) {
      setSubmitError(error.message || "Could not register agent.")
    } finally {
      setIsSubmitting(false)
    }
  }

  async function saveAgentPricing(basePriceValue) {
    if (!selectedAgent) return
    setPricingSubmitError("")
    setIsPricingSubmitting(true)
    try {
      for (const tool of basePriceValue) {
        const toolPrice = Number(tool.toolPriceUSDC)
        const runtimePrice = Number(tool.runtimePriceUSDC || "0")
        if (!Number.isFinite(toolPrice) || toolPrice <= 0 || toolPrice > 0.01) {
          throw new Error(`Tool price for ${tool.name} must be greater than 0 and no more than 0.01 USDC.`)
        }
        if (!Number.isFinite(runtimePrice) || runtimePrice < 0 || runtimePrice > 0.01) {
          throw new Error(`Runtime price for ${tool.name} must be between 0 and 0.01 USDC.`)
        }
        await updateToolPricing(selectedAgent.sellerId, selectedAgent.agentId, tool.toolId, {
          toolPriceUSDC: toolPrice,
          runtimePriceUSDC: runtimePrice,
        })
      }
      await refreshAgents({ showLoading: false })
      openAgent(selectedAgent, "detail")
    } catch (error) {
      setPricingSubmitError(error.message || "Could not update pricing.")
    } finally {
      setIsPricingSubmitting(false)
    }
  }

  async function deleteAgentCard(agent) {
    const confirmed = window.confirm(`Delete ${agent.name}? This will remove it from the marketplace list.`)
    if (!confirmed) return
    setDeletingAgentIds((current) => new Set(current).add(agent.id))
    try {
      await deleteAgent(agent.sellerId, agent.agentId)
      await refreshAgents({ showLoading: false })
      if (routeState?.agentId === agent.id) {
        goBackToRegistry()
      }
    } catch (error) {
      // Deletion errors should not replace the marketplace load state/banner.
      // 404 commonly means backend not restarted or item already removed.
      if (error?.status === 404) {
        await refreshAgents({ showLoading: false })
      } else {
        window.alert(error?.message || "Could not delete agent.")
      }
    } finally {
      setDeletingAgentIds((current) => {
        const next = new Set(current)
        next.delete(agent.id)
        return next
      })
    }
  }

  return (
    <div className="min-h-screen bg-[#111111] text-zinc-100">
      <main className="flex min-h-screen flex-col">
        <header className="border-b border-zinc-900/90 bg-[#101010]/95 backdrop-blur">
          <div className="mx-auto flex max-w-[1060px] items-center justify-between px-4 py-5 lg:px-0">
            <button
              type="button"
              onClick={goBackToRegistry}
              className="flex items-center gap-4 rounded-xl text-left transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-zinc-600 focus-visible:ring-offset-2 focus-visible:ring-offset-[#101010]"
              aria-label="Go to home page"
            >
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
            </button>
            <div className="hidden h-px flex-1 bg-gradient-to-r from-transparent via-zinc-800/80 to-transparent md:ml-10 md:block" />
            <div className="ml-4 flex shrink-0 items-center gap-2">
              <Button
                variant="outline"
                className={`h-8 rounded-md border-zinc-800 px-3 text-xs ${
                  routeState?.page === "transactions"
                    ? "bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/20"
                    : "bg-zinc-950 text-zinc-200 hover:bg-zinc-900"
                }`}
                onClick={openTransactionsScreen}
              >
                <CandlestickChart className="size-3.5" />
                Transactions
              </Button>
              <Button
                variant="outline"
                className={`h-8 rounded-md border-zinc-800 px-3 text-xs ${
                  !routeState || routeState.page === "detail" || routeState.page === "edit" || routeState.page === "register"
                    ? "bg-zinc-100 text-zinc-900 hover:bg-zinc-200"
                    : "bg-zinc-950 text-zinc-200 hover:bg-zinc-900"
                }`}
                onClick={goBackToRegistry}
              >
                Registry
              </Button>
            </div>
          </div>
        </header>

        <div className="flex-1 px-4 py-5 lg:px-6">
          {routeState?.page === "transactions" ? (
            <TransactionsScreen
              transactionsState={transactionsState}
              isLoading={isTransactionsLoading}
              loadError={transactionsError}
              onRefresh={() => refreshTransactions()}
            />
          ) : routeState?.page === "register" ? (
            <RegisterAgentScreen
              onBack={goBackToRegistry}
              onSubmit={registerAgent}
              isSubmitting={isSubmitting}
              submitError={submitError}
            />
          ) : selectedAgent && routeState?.page === "edit" ? (
            <AgentEditScreen
              agent={selectedAgentView}
              onBack={() => openAgent(selectedAgent, "detail")}
              onSavePricing={saveAgentPricing}
              isSubmitting={isPricingSubmitting}
              submitError={pricingSubmitError}
            />
          ) : selectedAgent ? (
            <AgentDetailScreen
              agent={selectedAgentView}
              onBack={goBackToRegistry}
              onEditPricing={(agent) => openAgent(agent, "edit")}
            />
          ) : routeState?.agentId && !isLoading ? (
            <section className="mx-auto max-w-[860px] py-8">
              <Card className="rounded-2xl border-zinc-800 bg-[#0d0d0d] text-zinc-50 shadow-none">
                <CardContent className="space-y-4 p-6">
                  <p className="text-sm text-zinc-300">
                    This agent could not be found in the current backend response.
                  </p>
                  <Button variant="outline" className="border-zinc-800" onClick={goBackToRegistry}>
                    Back to Registry
                  </Button>
                </CardContent>
              </Card>
            </section>
          ) : (
            <AgentListScreen
              agents={pagedAgents}
              allCount={filteredAgents.length}
              query={query}
              onQueryChange={setQuery}
              onOpen={openAgent}
              onRegister={openRegisterScreen}
              page={currentPage}
              pageCount={pageCount}
              isLoading={isLoading}
              loadError={loadError}
              onRetry={() => refreshAgents()}
              onPrevPage={() => setPage((current) => Math.max(current - 1, 1))}
              onNextPage={() => setPage((current) => Math.min(current + 1, pageCount))}
              onSelectPage={setPage}
              onDelete={deleteAgentCard}
              deletingAgentIds={deletingAgentIds}
            />
          )}
        </div>
      </main>
    </div>
  )
}
