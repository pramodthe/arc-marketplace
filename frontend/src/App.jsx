import { useEffect, useMemo, useState } from "react"
import {
  AlertCircle,
  ArrowLeft,
  ArrowUpRight,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Copy,
  ExternalLink,
  KeyRound,
  Layers3,
  Link2,
  Loader2,
  Search,
  Shield,
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
  createAgent,
  createSeller,
  getSeller,
  listMarketplaceTools,
  listSellers,
  updateAgentPricing,
} from "@/api/marketplaceClient.js"
import { makeAgentCompositeId, mapMarketplaceToAgentCards } from "@/lib/agentMappers.js"

const PAGE_SIZE = 9

function pushPath(pathname) {
  window.history.pushState({}, "", pathname)
}

function scrollToTop() {
  window.scrollTo({ top: 0, behavior: "auto" })
}

function readRouteFromPath() {
  if (window.location.pathname === "/agents/register") {
    return { page: "register" }
  }

  const editMatch = window.location.pathname.match(/^\/agents\/([^/]+)\/edit$/)
  if (editMatch) {
    return { agentId: decodeURIComponent(editMatch[1]), page: "edit" }
  }

  const match = window.location.pathname.match(/^\/agents\/([^/]+)$/)
  if (!match) return null
  return { agentId: decodeURIComponent(match[1]), page: "detail" }
}

function normalizeSearch(value) {
  return value.trim().toLowerCase()
}

function splitCommaValues(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean)
}

function mergeAgentProfile(agent, override) {
  if (!override) return agent
  return {
    ...agent,
    ...override,
    profile: {
      ...(agent.profile || {}),
      ...(override.profile || {}),
    },
  }
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

function AgentCard({ agent, onOpen }) {
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
            <AgentCard key={agent.id} agent={agent} onOpen={onOpen} />
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
  const steps = ["Identity", "Services", "Trust & Ops", "Review"]
  const [step, setStep] = useState(0)
  const [form, setForm] = useState({
    imageName: "",
    imagePreviewDataUrl: "",
    agentName: "",
    agentDescription: "",
    wallet: "",
    metadataUri: "",
    category: "General",
    servicesInput: "",
    apiBaseUrl: "",
    apiDocsUrl: "",
    slaTier: "Standard",
    pricingModel: "Per invocation",
    basePriceUsdc: "",
    trustSignalsInput: "",
    complianceNotes: "",
    kycStatus: "Unknown",
    supportEmail: "",
    payoutPolicy: "",
  })

  function updateField(key, value) {
    setForm((current) => ({ ...current, [key]: value }))
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
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Wallet Address (identity + payouts)
                </span>
                <Input
                  value={form.wallet}
                  onChange={(event) => updateField("wallet", event.target.value)}
                  placeholder="0x..."
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
                <p className="mt-2 text-xs text-zinc-500">
                  Used to identify seller and receive payments in this demo.
                </p>
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Metadata Link (optional, advanced)
                </span>
                <Input
                  value={form.metadataUri}
                  onChange={(event) => updateField("metadataUri", event.target.value)}
                  placeholder="ipfs://..."
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
                <p className="mt-2 text-xs text-zinc-500">
                  Optional URI with extra profile data (for future integrations).
                </p>
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">Category</span>
                <Input
                  value={form.category}
                  onChange={(event) => updateField("category", event.target.value)}
                  placeholder="Analytics"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">SLA Tier</span>
                <select
                  value={form.slaTier}
                  onChange={(event) => updateField("slaTier", event.target.value)}
                  className="h-12 w-full rounded-xl border border-zinc-800 bg-[#111111] px-4 text-sm text-zinc-100 outline-none transition-colors focus:border-zinc-700"
                >
                  <option>Standard</option>
                  <option>Priority</option>
                  <option>Enterprise</option>
                </select>
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Services Offered (comma separated)
                </span>
                <Input
                  value={form.servicesInput}
                  onChange={(event) => updateField("servicesInput", event.target.value)}
                  placeholder="Summarize, Analyze, Risk Scoring"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">API Base URL</span>
                <Input
                  value={form.apiBaseUrl}
                  onChange={(event) => updateField("apiBaseUrl", event.target.value)}
                  placeholder="https://api.example.com"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
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
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">Pricing Model</span>
                <select
                  value={form.pricingModel}
                  onChange={(event) => updateField("pricingModel", event.target.value)}
                  className="h-12 w-full rounded-xl border border-zinc-800 bg-[#111111] px-4 text-sm text-zinc-100 outline-none transition-colors focus:border-zinc-700"
                >
                  <option>Per invocation</option>
                  <option>Monthly subscription</option>
                  <option>Tiered usage</option>
                  <option>Custom contract</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">Base Price (USDC)</span>
                <Input
                  value={form.basePriceUsdc}
                  onChange={(event) => updateField("basePriceUsdc", event.target.value)}
                  placeholder="0.01"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
            </div>
          ) : null}

          {step === 2 ? (
            <div className="grid gap-5 sm:grid-cols-2">
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">
                  Trust Signals (comma separated)
                </span>
                <Input
                  value={form.trustSignalsInput}
                  onChange={(event) => updateField("trustSignalsInput", event.target.value)}
                  placeholder="SOC2, Human Review, Reputation Score"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">KYC / Validation Status</span>
                <select
                  value={form.kycStatus}
                  onChange={(event) => updateField("kycStatus", event.target.value)}
                  className="h-12 w-full rounded-xl border border-zinc-800 bg-[#111111] px-4 text-sm text-zinc-100 outline-none transition-colors focus:border-zinc-700"
                >
                  <option>Unknown</option>
                  <option>Pending</option>
                  <option>Verified</option>
                  <option>Not required</option>
                </select>
              </label>
              <label className="block">
                <span className="mb-3 block text-[16px] text-zinc-100">Support Email</span>
                <Input
                  value={form.supportEmail}
                  onChange={(event) => updateField("supportEmail", event.target.value)}
                  placeholder="support@example.com"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">Compliance Notes</span>
                <textarea
                  value={form.complianceNotes}
                  onChange={(event) => updateField("complianceNotes", event.target.value)}
                  className="min-h-[100px] w-full rounded-xl border border-zinc-800 bg-[#111111] px-4 py-3 text-sm text-zinc-100 outline-none transition-colors focus:border-zinc-700"
                />
              </label>
              <label className="block sm:col-span-2">
                <span className="mb-3 block text-[16px] text-zinc-100">Payout Policy</span>
                <Input
                  value={form.payoutPolicy}
                  onChange={(event) => updateField("payoutPolicy", event.target.value)}
                  placeholder="Instant settlement to seller wallet"
                  className="h-12 rounded-xl border-zinc-800 bg-[#111111] text-zinc-100"
                />
              </label>
            </div>
          ) : null}

          {step === 3 ? (
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
                  <span className="text-zinc-500">Category:</span> {form.category || "General"}
                </p>
                <p>
                  <span className="text-zinc-500">Pricing:</span> {form.pricingModel}
                </p>
                <p>
                  <span className="text-zinc-500">Base Price:</span> {form.basePriceUsdc || "Not set"} USDC
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
  const initialBasePrice = agent.profile?.basePriceUsdc
  const [basePriceUsdc, setBasePriceUsdc] = useState(
    initialBasePrice && initialBasePrice !== "Not provided" ? initialBasePrice : "",
  )

  function handleSubmit(event) {
    event.preventDefault()
    onSavePricing(basePriceUsdc)
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
          <h1 className="text-xl font-semibold">Update Agent Pricing</h1>
          <p className="text-sm text-zinc-400">
            Set a new base price for this agent. The backend updates tool prices and the dashboard card
            reflects the new minimum price after save.
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
          <form className="space-y-4 rounded-xl border border-zinc-800 bg-[#111111] p-4" onSubmit={handleSubmit}>
            <label className="block">
              <span className="mb-2 block text-zinc-100">Base Price (USDC)</span>
              <Input
                value={basePriceUsdc}
                onChange={(event) => setBasePriceUsdc(event.target.value)}
                placeholder="0.01"
                className="h-11 rounded-xl border-zinc-800 bg-[#0d0d0d] text-zinc-100"
              />
            </label>
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
                  "Save Pricing"
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
            <div className="mt-1 flex flex-wrap gap-3">
              {(agent.profile?.services || []).map((service) => (
                <Badge
                  key={service}
                  variant="outline"
                  className="rounded-md border-zinc-700 bg-zinc-900 px-2 py-1 text-[11px] text-zinc-300"
                >
                  {service}
                </Badge>
              ))}
            </div>
            <Separator className="my-4 bg-zinc-800" />
            <div className="grid gap-2 text-sm text-zinc-300 sm:grid-cols-2">
              <p>
                <span className="text-zinc-500">API Base:</span> {agent.profile?.apiBaseUrl}
              </p>
              <p>
                <span className="text-zinc-500">API Docs:</span> {agent.profile?.apiDocsUrl}
              </p>
              <p>
                <span className="text-zinc-500">Category:</span> {agent.profile?.category}
              </p>
              <p>
                <span className="text-zinc-500">SLA Tier:</span> {agent.profile?.slaTier}
              </p>
            </div>
          </MetricCard>

          <MetricCard dotClassName="bg-amber-500" icon={Layers3} title="Commercial Terms">
            <div className="space-y-4">
              <div className="grid gap-2 text-sm text-zinc-300 sm:grid-cols-2">
                <p>
                  <span className="text-zinc-500">Pricing Model:</span> {agent.profile?.pricingModel}
                </p>
                <p>
                  <span className="text-zinc-500">Base Price (USDC):</span> {agent.profile?.basePriceUsdc}
                </p>
                <p className="sm:col-span-2">
                  <span className="text-zinc-500">Payout Policy:</span> {agent.profile?.payoutPolicy}
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
                  <span className="text-zinc-500">KYC Status:</span> {agent.profile?.kycStatus}
                </p>
                <p>
                  <span className="text-zinc-500">Support:</span> {agent.profile?.supportEmail}
                </p>
                <p className="sm:col-span-2">
                  <span className="text-zinc-500">Compliance Notes:</span>{" "}
                  {agent.profile?.complianceNotes}
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
                <DetailRow icon={UserRoundPlus} label="Seller" value={agent.owner} />
                <DetailRow icon={KeyRound} label="Authority" value={agent.authority} />
              </div>
              <div className="pt-4 text-xs text-zinc-500">
                Some advanced fields are currently UI placeholders until backend persistence endpoints are
                added.
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

export default function App() {
  const [agents, setAgents] = useState([])
  const [agentUiOverrides, setAgentUiOverrides] = useState({})
  const [routeState, setRouteState] = useState(() => readRouteFromPath())
  const [isLoading, setIsLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const [query, setQuery] = useState("")
  const [page, setPage] = useState(1)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState("")
  const [isPricingSubmitting, setIsPricingSubmitting] = useState(false)
  const [pricingSubmitError, setPricingSubmitError] = useState("")
  const mergedAgents = useMemo(
    () => agents.map((agent) => mergeAgentProfile(agent, agentUiOverrides[agent.id])),
    [agentUiOverrides, agents],
  )
  const selectedAgent = mergedAgents.find((agent) => agent.id === routeState?.agentId) ?? null

  async function refreshAgents({ showLoading = true } = {}) {
    if (showLoading) setIsLoading(true)
    setLoadError("")

    try {
      const tools = await listMarketplaceTools()
      const sellers = await listSellers()
      const sellerDetailEntries = await Promise.all(
        sellers.map(async (seller) => {
          try {
            return await getSeller(seller.id)
          } catch {
            return null
          }
        }),
      )

      const sellerDetailsById = Object.fromEntries(
        sellerDetailEntries
          .filter((detail) => detail?.seller?.id != null)
          .map((detail) => [detail.seller.id, detail]),
      )

      setAgents(mapMarketplaceToAgentCards({ tools, sellerDetailsById }))
    } catch (error) {
      setLoadError(error.message || "Unknown error while fetching agents.")
      setAgents([])
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    refreshAgents()
  }, [])

  useEffect(() => {
    const handlePopState = () => setRouteState(readRouteFromPath())
    window.addEventListener("popstate", handlePopState)
    return () => window.removeEventListener("popstate", handlePopState)
  }, [])

  useEffect(() => {
    document.title =
      routeState?.page === "register"
        ? "Register Agent | ARC-Agents"
        : selectedAgent
          ? `${selectedAgent.name} | ARC-Agents`
          : "ARC-Agents"
  }, [routeState?.page, selectedAgent])

  useEffect(() => {
    setPage(1)
  }, [query])

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

  async function registerAgent(form) {
    setIsSubmitting(true)
    setSubmitError("")

    try {
      const walletAddress = form.wallet.trim() || `demo-wallet-${Date.now()}`
      const agentName = form.agentName.trim() || "Untitled Agent"
      const agentDescription = form.agentDescription.trim() || ""
      const seller = await createSeller({
        name: `${agentName} Studio`,
        description: `Seller profile for ${agentName}`,
        ownerWalletAddress: walletAddress,
        validatorWalletAddress: "",
      })

      const agent = await createAgent(seller.id, {
        name: agentName,
        description: agentDescription,
        metadataUri: form.metadataUri.trim(),
        iconDataUrl: form.imagePreviewDataUrl || "",
        basePriceUSDC: Number(form.basePriceUsdc) > 0 ? Number(form.basePriceUsdc) : undefined,
      })

      const createdId = makeAgentCompositeId(seller.id, agent.id)
      const services = splitCommaValues(form.servicesInput)
      const trustSignals = splitCommaValues(form.trustSignalsInput)
      setAgentUiOverrides((current) => ({
        ...current,
        [createdId]: {
          avatarImage: form.imagePreviewDataUrl || "",
          tags: trustSignals.length ? trustSignals : ["Pending verification"],
          profile: {
            category: form.category.trim() || "General",
            services: services.length ? services : ["Summarize", "Analyze", "Plan", "Response"],
            apiBaseUrl: form.apiBaseUrl.trim() || "Not provided",
            apiDocsUrl: form.apiDocsUrl.trim() || "Not provided",
            slaTier: form.slaTier,
            pricingModel: form.pricingModel,
            trustSignals: trustSignals.length ? trustSignals : ["Not provided"],
            complianceNotes: form.complianceNotes.trim() || "Not provided",
            kycStatus: form.kycStatus,
            supportEmail: form.supportEmail.trim() || "Not provided",
            payoutPolicy: form.payoutPolicy.trim() || "Not provided",
          },
        },
      }))

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
    const parsed = Number(basePriceValue)
    if (!Number.isFinite(parsed) || parsed <= 0) {
      setPricingSubmitError("Base price must be a positive number.")
      return
    }

    setPricingSubmitError("")
    setIsPricingSubmitting(true)
    try {
      await updateAgentPricing(selectedAgent.sellerId, selectedAgent.agentId, { basePriceUSDC: parsed })
      setAgentUiOverrides((current) => {
        const existing = current[selectedAgent.id]
        if (!existing?.profile) return current
        return {
          ...current,
          [selectedAgent.id]: {
            ...existing,
            profile: {
              ...existing.profile,
              basePriceUsdc: parsed.toFixed(2),
            },
          },
        }
      })
      await refreshAgents({ showLoading: false })
      openAgent(selectedAgent, "detail")
    } catch (error) {
      setPricingSubmitError(error.message || "Could not update pricing.")
    } finally {
      setIsPricingSubmitting(false)
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
          </div>
        </header>

        <div className="flex-1 px-4 py-5 lg:px-6">
          {routeState?.page === "register" ? (
            <RegisterAgentScreen
              onBack={goBackToRegistry}
              onSubmit={registerAgent}
              isSubmitting={isSubmitting}
              submitError={submitError}
            />
          ) : selectedAgent && routeState?.page === "edit" ? (
            <AgentEditScreen
              agent={selectedAgent}
              onBack={() => openAgent(selectedAgent, "detail")}
              onSavePricing={saveAgentPricing}
              isSubmitting={isPricingSubmitting}
              submitError={pricingSubmitError}
            />
          ) : selectedAgent ? (
            <AgentDetailScreen
              agent={selectedAgent}
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
            />
          )}
        </div>
      </main>
    </div>
  )
}
