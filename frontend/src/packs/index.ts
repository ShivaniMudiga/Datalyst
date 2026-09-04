// The pack registry. This file is the seam: the runtime imports *this*, learns
// that packs exist and how to render one, and never names any of them. Every
// domain word stays on the other side of it (Rule 4).
import type { ComponentType } from 'react'
import { ReconLanding } from './recon/Landing'
import { Reconciliation } from './recon/Reconciliation'

export type PackScreenProps = {
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  user: { email: string } | null
  connection: { database?: string; db_type?: string } | null
  onOpenSchema?: () => void
  onAsk?: () => void
  onSignOut: () => void
}

export const packPages: Record<string, ComponentType<PackScreenProps>> = {
  recon: Reconciliation,
}

/** The pack a signed-in user lands on. Null puts the generic conversation back
 *  at the front, which is what a runtime with no pack installed does. */
export const packHome: string | null = 'recon'

/** The front door. The runtime no longer ships a generic one: this
 *  installation is a single product, and a visitor should land on it. */
export const PackLanding: ComponentType<{
  theme: 'dark' | 'light'
  onToggleTheme: () => void
  onTry: () => void
}> = ReconLanding
