async function request(path, options = {}) {
  const response = await fetch(path, options)
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // response wasn't JSON; keep statusText
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail))
  }
  if (response.status === 204) return null
  return response.json()
}

export const api = {
  syncCatalog: () => request('/api/catalog/sync', { method: 'POST' }),
  listBlueprints: (q) => request(`/api/catalog/blueprints${q ? `?q=${encodeURIComponent(q)}` : ''}`),
  listPrintProviders: (blueprintId) => request(`/api/catalog/blueprints/${blueprintId}/print-providers`),
  getVariantCatalog: (blueprintId, providerId) =>
    request(`/api/catalog/blueprints/${blueprintId}/print-providers/${providerId}/variants`),
  uploadDesign: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request('/api/designs/upload', { method: 'POST', body: formData })
  },
  createProduct: (payload) =>
    request('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
}
