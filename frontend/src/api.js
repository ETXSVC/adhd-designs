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
  listBlueprints: (q, { limit = 50, offset = 0, category = '' } = {}) => {
    const params = new URLSearchParams({ limit, offset })
    if (q) params.set('q', q)
    if (category) params.set('category', category)
    return request(`/api/catalog/blueprints?${params}`)
  },
  listCategories: () => request('/api/catalog/categories'),
  listPrintProviders: (blueprintId) => request(`/api/catalog/blueprints/${blueprintId}/print-providers`),
  getVariantCatalog: (blueprintId, providerId) =>
    request(`/api/catalog/blueprints/${blueprintId}/print-providers/${providerId}/variants`),
  uploadDesign: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return request('/api/designs/upload', { method: 'POST', body: formData })
  },
  generateDesignMetadata: (designId) => request(`/api/designs/${designId}/ai-metadata`, { method: 'POST' }),
  updateDesignMetadata: (designId, payload) =>
    request(`/api/designs/${designId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
  generateProductMetadata: (designId, blueprintId) =>
    request('/api/products/ai-metadata', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ design_id: designId, blueprint_id: blueprintId }),
    }),
  createProduct: (payload) =>
    request('/api/products', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    }),
}
