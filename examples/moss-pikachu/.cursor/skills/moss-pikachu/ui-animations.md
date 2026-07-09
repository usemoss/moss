# UI & Animations

## Search overlay sizing

- Width: 300pt (thought bubble)
- Max height: 600pt (results scroll inside)
- Corner radius: 12pt
- Shadow: `radius: 20, y: 8, opacity: 0.25`

## Pikachu sizes

| Context | Size |
|---------|------|
| Menu bar | 32×32 pt |
| Search overlay | 64×64 pt |
| Hover scale | 1.05 |

## PetState animations

| State | Animation |
|-------|-----------|
| `idle` | breathe 1.0→1.02 (2s), blink every 5–8s random, tail ±2° every 3–5s |
| `searching` | tail wag ±15° (0.6s loop), thinking dots |
| `found(n)` | bounce 1.0→1.15 (0.4s ×2), ✨ sparkles |
| `notFound` | head tilt ±8° (1s), sad expression |

Use SwiftUI `.animation(.easeInOut, value:)` and `Timer` for random idle intervals.

## Search input debounce

160ms after last keystroke before calling `SearchService.search`.
