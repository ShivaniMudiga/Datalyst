// The pack registry. This file is the seam: the runtime imports *this*, learns
// that packs exist and how to render one, and never names any of them. Every
// domain word stays on the other side of it (Rule 4).
import type { ComponentType } from 'react'
import { ReconLanding } from './recon/Landing'
import { Reconciliation } from './recon/Reconciliation'

export const packPages: Record<string, ComponentType<{ onBack: () => void }>> = {
  recon: Reconciliation,
}

/** The front door, when a pack ships one.
 *
 *  The runtime's own landing page cannot describe what this installation is
 *  for - Rule 1 keeps every industry word out of `src/`. So the pack provides
 *  one, and the runtime shows it without knowing what it says. Remove this and
 *  the generic page comes back, unchanged. */
export const packLanding: ComponentType<{
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  onTry: () => void
}> | null = ReconLanding
