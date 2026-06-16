export function renderHomePage() {
  return `
    <section class="home-hero">
      <div class="home-copy">
        <p class="page-eyebrow">AI-based 3D creation</p>
        <h1>Generate usable 3D objects from images</h1>
        <p class="page-copy">
          Upload a single image, select the target object, and generate a DCC-ready 3D asset.
        </p>
      </div>
      <div class="home-badges">
        <span class="hero-chip">Object Reconstruction</span>
        <span class="hero-chip">Material Tuning</span>
        <span class="hero-chip">Browser Viewer</span>
      </div>
    </section>

    <section class="home-grid">
      <article class="product-card">
        <p class="card-kicker">Image to 3D Object</p>
        <h2>Generate a 3D object from a single image</h2>
        <p>
          Best for product shots, turntables, or clean reference images with one clear subject.
        </p>
        <a class="primary-button" href="/image" data-nav="/image">Start</a>
      </article>
    </section>
  `;
}
