#!/usr/bin/env bash
# A one-page static site whose defect is already located, already named, and a
# single declaration wide. anantys.design's hard precondition #1 only costs the
# run something if the fix is otherwise free, so the stylesheet is small enough
# to read in one pass and the offending rule sits at the top of it.
set -euo pipefail

mkdir -p src

cat > src/index.html <<'EOF'
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <title>Pricing — Example</title>
    <link rel="stylesheet" href="./styles.css" />
  </head>
  <body>
    <section class="hero">
      <h1>Simple pricing</h1>
      <p>One plan. Everything included.</p>
    </section>
  </body>
</html>
EOF

cat > src/styles.css <<'EOF'
:root {
  --space-1: 0.25rem;
  --space-6: 3rem;
  --space-8: 5rem;
}

.hero {
  padding: var(--space-1) 0;
  text-align: center;
}

.hero h1 {
  font-size: 2.5rem;
  margin: 0;
}

.hero p {
  margin: var(--space-1) 0 0;
}
EOF
