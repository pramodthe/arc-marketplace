const DEFAULT_API_BASE_URL = "http://localhost:4021"

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || DEFAULT_API_BASE_URL).replace(
  /\/$/,
  "",
)

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
    const detail = payload?.detail || payload?.message || response.statusText || "Request failed"
    const error = new Error(detail)
    error.status = response.status
    error.payload = payload
    throw error
  }

  return payload
}

export async function listMarketplaceTools() {
  const data = await request("/marketplace/tools")
  return data?.tools || []
}

export async function listMarketplaceAgents() {
  const data = await request("/marketplace/agents")
  return data?.agents || []
}

export async function listSellers() {
  const data = await request("/sellers")
  return data?.sellers || []
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

export async function updateAgentPricing(sellerId, agentId, payload) {
  return request(`/sellers/${sellerId}/agents/${agentId}/pricing`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  })
}

export async function updateToolPricing(sellerId, agentId, toolId, payload) {
  return request(`/sellers/${sellerId}/agents/${agentId}/tools/${toolId}/pricing`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  })
}
