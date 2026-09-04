// The pack registry. This file is the seam: the runtime imports *this*, learns
// that packs exist and how to render one, and never names any of them. Every
// domain word stays on the other side of it (Rule 4).
import type { ComponentType } from 'react'
import { Reconciliation } from './recon/Reconciliation'

export const packPages: Record<string, ComponentType<{ onBack: () => void }>> = {
  recon: Reconciliation,
}
