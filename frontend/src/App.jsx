import { useState } from 'react'
import { api } from './api'
import PlacementEditor, { defaultPlacement } from './PlacementEditor'
import './index.css'

const STEPS = ['Artwork', 'Product', 'Print provider', 'Variants & price', 'Placement', 'Done']

function centsToDollars(cents) {
  return (cents / 100).toFixed(2)
}

export default function App() {
  const [step, setStep] = useState(0)

  const [design, setDesign] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [uploadError, setUploadError] = useState('')

  const [blueprintQuery, setBlueprintQuery] = useState('')
  const [blueprints, setBlueprints] = useState([])
  const [blueprintsLoading, setBlueprintsLoading] = useState(false)
  const [blueprintsError, setBlueprintsError] = useState('')
  const [syncing, setSyncing] = useState(false)
  const [selectedBlueprint, setSelectedBlueprint] = useState(null)

  const [printProviders, setPrintProviders] = useState([])
  const [providersLoading, setProvidersLoading] = useState(false)
  const [selectedProvider, setSelectedProvider] = useState(null)

  const [variantCatalog, setVariantCatalog] = useState(null)
  const [variantsLoading, setVariantsLoading] = useState(false)
  const [selectedVariantIds, setSelectedVariantIds] = useState(new Set())
  const [title, setTitle] = useState('')
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

  async function loadBlueprints(query) {
    setBlueprintsLoading(true)
    setBlueprintsError('')
    try {
      const rows = await api.listBlueprints(query)
      setBlueprints(rows)
    } catch (err) {
      setBlueprintsError(err.message)
      setBlueprints([])
    } finally {
      setBlueprintsLoading(false)
    }
  }

  async function handleSync() {
    setSyncing(true)
    setBlueprintsError('')
    try {
      await api.syncCatalog()
      await loadBlueprints(blueprintQuery)
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
                <button
                  onClick={() => {
                    setStep(1)
                    if (blueprints.length === 0) loadBlueprints('')
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
