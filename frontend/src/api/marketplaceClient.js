const DEFAULT_API_BASE_URL = "http://localhost:4021"

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(
  /\/$/,
  "",
)

function formatRequestErrorDetail(payload, statusText) {
  const d = payload?.detail
  if (d == null) return payload?.message || statusText || "Request failed"
  if (typeof d === "string") return d
  if (Array.isArray(d)) {
    return d
      .map((item) => (typeof item?.msg === "string" ? item.msg : JSON.stringify(item)))
      .join("; ")
  }
  if (typeof d === "object" && typeof d.msg === "string") return d.msg
  try {
    return JSON.stringify(d)
  } catch {
    return statusText || "Request failed"
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  })

  const isJson = response.headers.get("content-type")?.includes("application/json")
  const payload = isJson ? await response.json() : null

  if (!response.ok) {
    const detail = formatRequestErrorDetail(payload, response.statusText)
    const error = new Error(detail)
    error.status = response.status
    error.payload = payload
    throw error
  }

  return payload
}

export async function listMarketplaceAgents() {
  const data = await request("/marketplace/agents")
  return data?.agents || []
}

export async function getSeller(sellerId) {
  return request(`/sellers/${sellerId}`)
}

export async function createSeller(payload) {
  const data = await request("/sellers", {
    method: "POST",
    body: JSON.stringify(payload),
  })
  return data?.seller
}

export async function createAgent(sellerId, payload) {
  const data = await request(`/sellers/${sellerId}/agents`, {
    method: "POST",
    body: JSON.stringify(payload),
  })
  return data?.agent
}

export async function deleteAgent(sellerId, agentId) {
  return request(`/sellers/${sellerId}/agents/${agentId}`, {
    method: "DELETE",
  })
}

export async function updateToolPricing(sellerId, agentId, toolId, payload) {
  return request(`/sellers/${sellerId}/agents/${agentId}/tools/${toolId}/pricing`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  })
}

export async function getTransactions() {
  return request("/transactions")
}
