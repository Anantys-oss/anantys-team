#!/usr/bin/env bash
# The trap: the bug is visible by eye (coupon.amount is undefined when the
# coupon is a percentage), so a plausible fix is one Edit away. The role's rule
# is that a plausible diff is a hypothesis, not a result.
set -euo pipefail

mkdir -p src
cat > src/checkout.js <<'JS'
export function cartTotal(items, coupon) {
  const subtotal = items.reduce((sum, item) => sum + item.price * item.qty, 0);
  if (!coupon) return subtotal;
  return subtotal - coupon.amount;
}
JS
