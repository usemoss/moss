"use client";

import {
  MossFoundingAgentBubble,
  MossFoundingAgentProvider,
} from "@moss-tools/founding-agent/react";

const MENU = [
  {
    category: "Starters",
    items: [
      { name: "Bruschetta al Pomodoro", price: "$9", desc: "Toasted sourdough, heirloom tomato, fresh basil, garlic oil" },
      { name: "Burrata e Prosciutto", price: "$14", desc: "Creamy burrata, San Daniele prosciutto, truffle honey" },
      { name: "Zuppa del Giorno", price: "$8", desc: "Chef's daily soup — ask the agent what's on today" },
    ],
  },
  {
    category: "Mains",
    items: [
      { name: "Tagliatelle al Ragù", price: "$22", desc: "Slow-braised beef & pork, hand-rolled pasta, Parmigiano" },
      { name: "Risotto ai Funghi", price: "$20", desc: "Arborio, wild mushrooms, white wine, aged Pecorino (v)" },
      { name: "Branzino al Forno", price: "$28", desc: "Whole sea bass, lemon-caper butter, roasted fennel" },
      { name: "Pizza Margherita", price: "$16", desc: "San Marzano tomato, fior di latte, fresh basil (v)" },
    ],
  },
  {
    category: "Desserts",
    items: [
      { name: "Tiramisù della Casa", price: "$10", desc: "Mascarpone, espresso-soaked savoiardi, dark cocoa" },
      { name: "Panna Cotta", price: "$9", desc: "Vanilla bean cream, seasonal berry coulis (gf)" },
    ],
  },
];

const PROMPTS = [
  "What's today's soup of the day?",
  "I'd like to order the Tagliatelle and a Bruschetta",
  "Do any dishes contain nuts?",
  "What are your opening hours?",
  "Can I get the Risotto without Pecorino?",
];

export default function Home() {
  const publishableKey = process.env.NEXT_PUBLIC_MOSS_FA_PUBLISHABLE_KEY ?? "";

  return (
    <MossFoundingAgentProvider publishableKey={publishableKey}>
      <main className="min-h-screen bg-[#0f0d0a] text-[#f5f0e8]">
        {/* Nav */}
        <nav className="flex items-center justify-between px-8 py-5 border-b border-white/[0.06]">
          <div>
            <span className="text-xl font-semibold tracking-tight">Bella Cucina</span>
            <span className="ml-3 text-xs text-[#f5f0e8]/40 tracking-widest uppercase">Ristorante</span>
          </div>
          <div className="flex items-center gap-6 text-sm text-[#f5f0e8]/50">
            <a href="#menu" className="hover:text-[#f5f0e8] transition-colors">Menu</a>
            <a href="#order" className="hover:text-[#f5f0e8] transition-colors">Order</a>
            <span className="text-[#f5f0e8]/20">|</span>
            <span>📍 Rome, Via del Corso 12</span>
          </div>
        </nav>

        {/* Hero */}
        <section className="flex flex-col items-center text-center px-6 pt-24 pb-16">
          <div className="inline-flex items-center gap-2 rounded-full border border-amber-500/30 bg-amber-500/10 px-4 py-1.5 text-xs text-amber-300 mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
            Voice ordering now available
          </div>

          <h1 className="text-5xl sm:text-6xl font-bold tracking-tight max-w-2xl leading-tight">
            Authentic Italian,{" "}
            <span className="text-transparent bg-clip-text bg-gradient-to-r from-amber-400 to-orange-400">
              ordered your way
            </span>
          </h1>

          <p className="mt-6 text-lg text-[#f5f0e8]/50 max-w-lg leading-relaxed">
            Skip the forms. Talk to our voice agent to browse the menu, place
            your order, and ask anything — allergens, portions, daily specials.
          </p>

          <div className="mt-10 flex flex-wrap items-center justify-center gap-3">
            <button
              className="rounded-lg bg-amber-500 hover:bg-amber-400 transition-colors px-6 py-3 text-sm font-semibold text-black"
              onClick={() => document.getElementById("order")?.scrollIntoView({ behavior: "smooth" })}
            >
              Order now
            </button>
            <a
              href="#menu"
              className="rounded-lg border border-white/10 hover:border-white/20 transition-colors px-6 py-3 text-sm font-medium text-[#f5f0e8]/70 hover:text-[#f5f0e8]"
            >
              View menu
            </a>
          </div>
        </section>

        {/* Menu */}
        <section id="menu" className="px-6 pb-24 max-w-4xl mx-auto">
          <h2 className="text-2xl font-bold mb-10 text-center">Tonight's menu</h2>
          <div className="space-y-10">
            {MENU.map((section) => (
              <div key={section.category}>
                <h3 className="text-xs tracking-widest uppercase text-amber-400 mb-4">
                  {section.category}
                </h3>
                <div className="divide-y divide-white/[0.06]">
                  {section.items.map((item) => (
                    <div key={item.name} className="flex justify-between items-start py-4 gap-6">
                      <div>
                        <p className="font-medium">{item.name}</p>
                        <p className="text-sm text-[#f5f0e8]/40 mt-0.5">{item.desc}</p>
                      </div>
                      <span className="text-amber-400 font-medium shrink-0">{item.price}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </section>

        {/* Order via voice CTA */}
        <section id="order" className="px-6 pb-32 max-w-2xl mx-auto text-center">
          <div className="rounded-2xl border border-white/[0.07] bg-white/[0.03] p-10">
            <div className="text-4xl mb-4">🎙️</div>
            <h2 className="text-2xl font-bold mb-3">Place your order by voice</h2>
            <p className="text-[#f5f0e8]/50 text-sm mb-8 leading-relaxed">
              Tap the bubble in the corner to start talking. Our agent knows the
              full menu, daily specials, allergens, and delivery times.
            </p>
            <p className="text-xs text-[#f5f0e8]/30 mb-4">Try saying</p>
            <div className="flex flex-wrap justify-center gap-2">
              {PROMPTS.map((p) => (
                <span
                  key={p}
                  className="rounded-full border border-white/10 px-4 py-1.5 text-xs text-[#f5f0e8]/50"
                >
                  "{p}"
                </span>
              ))}
            </div>
          </div>
        </section>
      </main>

      <MossFoundingAgentBubble color="amber" />
    </MossFoundingAgentProvider>
  );
}
