import { useState } from 'react'
import { api } from './api'
import PlacementEditor, { defaultPlacement } from './PlacementEditor'
import './index.css'

const STEPS = ['Artwork', 'Product', 'Print provider', 'Variants & price', 'Placement', 'Done']
const BLUEPRINTS_PAGE_SIZE = 50

function centsToDollars(cents) {
  return (cents / 100).toFixed(2)
}

export default function App() {
  const [step, setStep] = useState(0)

  const [design, setDesign] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')
  const [designAiLoading, setDesignAiLoading] = useState(false)
  const [designAiError, setDesignAiError] = useState('')
  const [designTitleDraft, setDesignTitleDraft] = useState('')
  const [designDescriptionDraft, setDesignDescriptionDraft] = useState('')
  const [designTagsDraft, setDesignTagsDraft] = useState('')
  const [designSaving, setDesignSaving] = useState(false)
  const [designSaveError, setDesignSaveError] = useState('')

  const [blueprintQuery, setBlueprintQuery] = useState('')
  const [categories, setCategories] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('')
  const [blueprints, setBlueprints] = useState([])
  const [blueprintsLoading, setBlueprintsLoading] = useState(false)
  const [blueprintsError, setBlueprintsError] = useState('')
  const [blueprintsHasMore, setBlueprintsHasMore] = useState(false)
  const [blueprintsLoadingMore, setBlueprintsLoadingMore] = useState(false)
  const [syncing, setSyncing] = useState(false)
  const [selectedBlueprint, setSelectedBlueprint] = useState(null)

  const [printProviders, setPrintProviders] = useState([])
  const [providersLoading, setProvidersLoading] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState(null)

  const [variantCatalog, setVariantCatalog] = useState(null)
  const [variantsLoading, setVariantsLoading] = useState(false)
  const [selectedVariantIds, setSelectedVariantIds] = useState(new Set())
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [tagsInput, setTagsInput] = useState('')
  const [productAiLoading, setProductAiLoading] = useState(false)
  const [productAiError, setProductAiError] = useState('')
  const [priceDollars, setPriceDollars] = useState('20.00')

  const [placement, setPlacement] = useState(defaultPlacement('front'))

  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState('')
  const [createdProduct, setCreatedProduct] = useState(null)

  async function handleUpload(e) {
    const file = e.target.files?.[0]
    if (!file) return
    setUploading(true)
    setUploadError('')
    try {
      const uploaded = await api.uploadDesign(file)
      setDesign(uploaded)
    } catch (err) {
      setUploadError(err.message)
    } finally {
      setUploading(false)
    }
  }

  async function handleGenerateDesignMetadata() {
    setDesignAiLoading(true)
    setDesignAiError('')
    try {
      const updated = await api.generateDesignMetadata(design.id)
      setDesign(updated)
      setDesignTitleDraft(updated.ai_title || '')
      setDesignDescriptionDraft(updated.ai_description || '')
      setDesignTagsDraft(updated.ai_tags.join(', '))
    } catch (err) {
      setDesignAiError(err.message)
    } finally {
      setDesignAiLoading(false)
    }
  }

  async function handleSaveDesignMetadata() {
    setDesignSaving(true)
    setDesignSaveError('')
    try {
      const updated = await api.updateDesignMetadata(design.id, {
        ai_title: designTitleDraft,
        ai_description: designDescriptionDraft,
        ai_tags: designTagsDraft
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
      })
      setDesign(updated)
    } catch (err) {
      setDesignSaveError(err.message)
    } finally {
      setDesignSaving(false)
    }
  }

  async function handleGenerateProductMetadata() {
    setProductAiLoading(true)
    setProductAiError('')
    try {
      const metadata = await api.generateProductMetadata(design.id, selectedBlueprint.printify_id)
      setTitle(metadata.title)
      setDescription(metadata.description)
      setTagsInput(metadata.tags.join(', '))
    } catch (err) {
      setProductAiError(err.message)
    } finally {
      setProductAiLoading(false)
    }
  }

  async function loadBlueprints(query, category = selectedCategory) {
    setBlueprintsLoading(true)
    setBlueprintsError('')
    try {
      const rows = await api.listBlueprints(query, { limit: BLUEPRINTS_PAGE_SIZE, offset: 0, category })
      setBlueprints(rows)
      setBlueprintsHasMore(rows.length === BLUEPRINTS_PAGE_SIZE)
    } catch (err) {
      setBlueprintsError(err.message)
      setBlueprints([])
      setBlueprintsHasMore(false)
    } finally {
      setBlueprintsLoading(false)
    }
  }

  async function loadMoreBlueprints() {
    setBlueprintsLoadingMore(true)
    try {
      const rows = await api.listBlueprints(blueprintQuery, {
        limit: BLUEPRINTS_PAGE_SIZE,
        offset: blueprints.length,
        category: selectedCategory,
      })
      setBlueprints((prev) => [...prev, ...rows])
      setBlueprintsHasMore(rows.length === BLUEPRINTS_PAGE_SIZE)
    } catch (err) {
      setBlueprintsError(err.message)
    } finally {
      setBlueprintsLoadingMore(false)
    }
  }

  async function loadCategories() {
    try {
      setCategories(await api.listCategories())
    } catch {
      // category filter is optional UI sugar; a failure here shouldn't block browsing
    }
  }

  function chooseCategory(category) {
    setSelectedCategory(category)
    loadBlueprints(blueprintQuery, category)
  }

  async function handleSync() {
    setSyncing(true)
    setBlueprintsError('')
    try {
      await api.syncCatalog()
      await Promise.all([loadBlueprints(blueprintQuery), loadCategories()])
    } catch (err) {
      setBlueprintsError(err.message)
    } finally {
      setSyncing(false)
    }
  }

  async function chooseBlueprint(blueprint) {
    setSelectedBlueprint(blueprint)
    setSelectedProvider(null)
    setVariantCatalog(null)
    setSelectedVariantIds(new Set())
    setTitle(blueprint.title)
    setStep(2)
    setProvidersLoading(true)
    try {
      const providers = await api.listPrintProviders(blueprint.printify_id)
      setPrintProviders(providers)
    } catch (err) {
      setBlueprintsError(err.message)
    } finally {
      setProvidersLoading(false)
    }
  }

  async function chooseProvider(provider) {
    setSelectedProvider(provider)
    setSelectedVariantIds(new Set())
    setStep(3)
    setVariantsLoading(true)
    try {
      const catalog = await api.getVariantCatalog(selectedBlueprint.printify_id, provider.printify_id)
      setVariantCatalog(catalog)
      const defaultArea = catalog.print_areas.find((a) => a.position === 'front') ?? catalog.print_areas[0]
      setPlacement(defaultPlacement(defaultArea?.position ?? 'front'))
    } catch (err) {
      setCreateError(err.message)
    } finally {
      setVariantsLoading(false)
    }
  }

  function toggleVariant(variantId) {
    setSelectedVariantIds((prev) => {
      const next = new Set(prev)
      if (next.has(variantId)) next.delete(variantId)
      else next.add(variantId)
      return next
    })
  }

  async function handleCreateProduct() {
    setCreating(true)
    setCreateError('')
    try {
      const product = await api.createProduct({
        title,
        design_id: design.id,
        blueprint_id: selectedBlueprint.printify_id,
        print_provider_id: selectedProvider.printify_id,
        variant_ids: Array.from(selectedVariantIds),
        price_cents: Math.round(parseFloat(priceDollars) * 100),
        placements: [placement],
        description,
        tags: tagsInput
          .split(',')
          .map((t) => t.trim())
          .filter(Boolean),
      })
      setCreatedProduct(product)
      setStep(5)
    } catch (err) {
      setCreateError(err.message)
    } finally {
      setCreating(false)
    }
  }

  function startOver() {
    setStep(0)
    setDesign(null)
    setSelectedBlueprint(null)
    setSelectedProvider(null)
    setVariantCatalog(null)
    setSelectedVariantIds(new Set())
    setPlacement(defaultPlacement('front'))
    setDescription('')
    setTagsInput('')
    setDesignTitleDraft('')
    setDesignDescriptionDraft('')
    setDesignTagsDraft('')
    setCreatedProduct(null)
    setCreateError('')
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>ADHD Designs — T-Shirt Studio</h1>
        <ol className="steps">
          {STEPS.map((label, i) => (
            <li key={label} className={i === step ? 'active' : i < step ? 'done' : ''}>
              {label}
            </li>
          ))}
        </ol>
      </header>

      <main className="app-main">
        {step === 0 && (
          <section className="card">
            <h2>1. Upload artwork</h2>
            <input type="file" accept="image/png,image/jpeg,image/webp" onChange={handleUpload} />
            {uploading && <p>Uploading…</p>}
            {uploadError && <p className="error">{uploadError}</p>}
            {design && (
              <div className="design-preview">
                <img src={design.url} alt={design.original_filename} />
                <p>
                  {design.original_filename} — {design.width}×{design.height}px
                </p>
                <button type="button" onClick={handleGenerateDesignMetadata} disabled={designAiLoading}>
                  {designAiLoading ? 'Asking AI…' : '✨ Suggest title, description & tags'}
                </button>
                {designAiError && <p className="error">{designAiError}</p>}
                {design.ai_title && (
                  <div className="ai-metadata">
                    <div className="form-row">
                      <label className="form-row-full">
                        Title
                        <input value={designTitleDraft} onChange={(e) => setDesignTitleDraft(e.target.value)} />
                      </label>
                    </div>
                    <div className="form-row">
                      <label className="form-row-full">
                        Description
                        <textarea
                          rows="3"
                          value={designDescriptionDraft}
                          onChange={(e) => setDesignDescriptionDraft(e.target.value)}
                        />
                      </label>
                    </div>
                    <div className="form-row">
                      <label className="form-row-full">
                        Tags (comma-separated)
                        <input value={designTagsDraft} onChange={(e) => setDesignTagsDraft(e.target.value)} />
                      </label>
                    </div>
                    {designSaveError && <p className="error">{designSaveError}</p>}
                    <button type="button" onClick={handleSaveDesignMetadata} disabled={designSaving}>
                      {designSaving ? 'Saving…' : 'Save changes'}
                    </button>
                  </div>
                )}
                <button
                  onClick={() => {
                    setStep(1)
                    if (blueprints.length === 0) loadBlueprints('')
                    if (categories.length === 0) loadCategories()
                  }}
                >
                  Next: choose a product →
                </button>
              </div>
            )}
          </section>
        )}

        {step === 1 && (
          <section className="card">
            <h2>2. Choose a product</h2>
            <div className="toolbar">
              <input
                placeholder="Search products (e.g. 'tee', 'hoodie')"
                value={blueprintQuery}
                onChange={(e) => setBlueprintQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && loadBlueprints(blueprintQuery)}
              />
              <button onClick={() => loadBlueprints(blueprintQuery)} disabled={blueprintsLoading}>
                Search
              </button>
              <button onClick={handleSync} disabled={syncing}>
                {syncing ? 'Syncing…' : 'Sync catalog from Printify'}
              </button>
            </div>
            {categories.length > 0 && (
              <div className="category-pills">
                <button
                  className={selectedCategory === '' ? 'category-pill active' : 'category-pill'}
                  onClick={() => chooseCategory('')}
                >
                  All
                </button>
                {categories.map((c) => (
                  <button
                    key={c.category}
                    className={selectedCategory === c.category ? 'category-pill active' : 'category-pill'}
                    onClick={() => chooseCategory(c.category)}
                  >
                    {c.category} ({c.count})
                  </button>
                ))}
              </div>
            )}
            {blueprintsLoading && <p>Loading…</p>}
            {blueprintsError && (
              <p className="error">
                {blueprintsError}
                {blueprintsError.includes('sync') && ' Use "Sync catalog from Printify" above.'}
              </p>
            )}
            <div className="grid">
              {blueprints.map((bp) => (
                <button key={bp.printify_id} className="blueprint-card" onClick={() => chooseBlueprint(bp)}>
                  {bp.images?.[0] && <img src={bp.images[0]} alt={bp.title} />}
                  <div>{bp.title}</div>
                  <div className="muted">
                    {bp.brand} {bp.model}
                  </div>
                </button>
              ))}
            </div>
            {blueprintsHasMore && (
              <button onClick={loadMoreBlueprints} disabled={blueprintsLoadingMore}>
                {blueprintsLoadingMore ? 'Loading…' : `Load more (showing ${blueprints.length})`}
              </button>
            )}
            <button className="back" onClick={() => setStep(0)}>
              ← Back
            </button>
          </section>
        )}

        {step === 2 && (
          <section className="card">
            <h2>3. Choose a print provider</h2>
            <p className="muted">for {selectedBlueprint?.title}</p>
            {providersLoading && <p>Loading…</p>}
            <div className="grid">
              {printProviders.map((pp) => (
                <button key={pp.printify_id} className="blueprint-card" onClick={() => chooseProvider(pp)}>
                  {pp.title}
                </button>
              ))}
            </div>
            <button className="back" onClick={() => setStep(1)}>
              ← Back
            </button>
          </section>
        )}

        {step === 3 && (
          <section className="card">
            <h2>4. Pick variants &amp; price</h2>
            {variantsLoading && <p>Loading…</p>}
            {createError && <p className="error">{createError}</p>}
            {variantCatalog && (
              <>
                <div className="variant-list">
                  {variantCatalog.variants.map((v) => (
                    <label key={v.id} className="variant-row">
                      <input
                        type="checkbox"
                        checked={selectedVariantIds.has(v.id)}
                        onChange={() => toggleVariant(v.id)}
                        disabled={!v.is_available}
                      />
                      {v.title} {!v.is_available && <span className="muted">(unavailable)</span>}
                    </label>
                  ))}
                </div>
                <button type="button" onClick={handleGenerateProductMetadata} disabled={productAiLoading}>
                  {productAiLoading ? 'Asking AI…' : '✨ Generate title, description & tags with AI'}
                </button>
                {productAiError && <p className="error">{productAiError}</p>}
                <div className="form-row">
                  <label>
                    Product title
                    <input value={title} onChange={(e) => setTitle(e.target.value)} />
                  </label>
                  <label>
                    Price (USD, applies to all selected variants)
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      value={priceDollars}
                      onChange={(e) => setPriceDollars(e.target.value)}
                    />
                  </label>
                </div>
                <div className="form-row">
                  <label className="form-row-full">
                    Description
                    <textarea rows="3" value={description} onChange={(e) => setDescription(e.target.value)} />
                  </label>
                </div>
                <div className="form-row">
                  <label className="form-row-full">
                    Tags (comma-separated — saved for your reference; Printify's API doesn't accept custom tags)
                    <input value={tagsInput} onChange={(e) => setTagsInput(e.target.value)} placeholder="funny, cat, astronaut" />
                  </label>
                </div>
                <button disabled={selectedVariantIds.size === 0 || !title} onClick={() => setStep(4)}>
                  Next: position artwork →
                </button>
              </>
            )}
            <button className="back" onClick={() => setStep(2)}>
              ← Back
            </button>
          </section>
        )}

        {step === 4 && (
          <section className="card">
            <h2>5. Position artwork</h2>
            {variantCatalog?.print_areas.length > 1 && (
              <div className="form-row">
                <label>
                  Print area
                  <select
                    value={placement.position}
                    onChange={(e) => setPlacement(defaultPlacement(e.target.value))}
                  >
                    {variantCatalog.print_areas.map((a) => (
                      <option key={a.position} value={a.position}>
                        {a.position}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            )}
            {variantCatalog && design && (
              <PlacementEditor
                printArea={variantCatalog.print_areas.find((a) => a.position === placement.position)}
                design={design}
                placement={placement}
                onChange={setPlacement}
              />
            )}
            {createError && <p className="error">{createError}</p>}
            <button disabled={creating} onClick={handleCreateProduct}>
              {creating ? 'Creating draft…' : `Create draft product (${selectedVariantIds.size} variants)`}
            </button>
            <button className="back" onClick={() => setStep(3)}>
              ← Back
            </button>
          </section>
        )}

        {step === 5 && createdProduct && (
          <section className="card">
            <h2>🎉 Draft product created</h2>
            <p>
              <strong>{createdProduct.title}</strong> was created as a draft on Printify (status:{' '}
              {createdProduct.status}).
            </p>
            <p className="muted">
              Printify product id: {createdProduct.printify_product_id}
              <br />
              Price: ${centsToDollars(Math.round(parseFloat(priceDollars) * 100))} per variant
            </p>
            <p>Open Printify to review the mockup and publish it to Shopify when it looks right.</p>
            <button onClick={startOver}>Design another shirt</button>
          </section>
        )}
      </main>
    </div>
  )
}
