import { ChevronLeft } from 'lucide-react'

/** One back control, so every screen goes back the same way and looks the same
 *  doing it. The label is what you are going back *to* when the caller knows;
 *  otherwise just "Back". */
export function BackButton({ onBack, label = 'Back' }: { onBack: () => void; label?: string }) {
  return (
    <button
      onClick={onBack}
      className="t-secondary flex items-center gap-1 rounded-chip px-2 py-1 text-ink-faint hover:bg-sunken hover:text-ink-mid"
    >
      <ChevronLeft className="size-4 shrink-0" />
      {label}
    </button>
  )
}
