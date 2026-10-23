/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { Bot, Shield, CheckCircle2, AlertTriangle, BookOpen, Terminal, Sparkles, ExternalLink } from 'lucide-react';

export default function App() {
  const [activeTab, setActiveTab] = useState<'overview' | 'commands' | 'setup' | 'catalog'>('overview');

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans selection:bg-amber-500 selection:text-slate-950">
      {/* Top Banner */}
      <header className="border-b border-slate-800 bg-slate-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-5xl mx-auto px-4 py-4 flex flex-col sm:flex-row items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-amber-500 to-orange-600 flex items-center justify-center shadow-lg shadow-orange-500/20">
              <Bot className="w-6 h-6 text-slate-950 font-bold" />
            </div>
            <div>
              <h1 className="font-bold text-lg leading-tight tracking-tight flex items-center gap-2">
                Blox Fruit Services <span className="text-xs px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">Discord Bot</span>
              </h1>
              <p className="text-xs text-slate-400">Pure Python 3.11+ • discord.py • SQLite Persistence</p>
            </div>
          </div>
          <div className="flex items-center gap-2 text-xs bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-lg text-emerald-400">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            Discord-Only Architecture (No Paid Cloud)
          </div>
        </div>
      </header>

      {/* Main container */}
      <main className="max-w-5xl mx-auto px-4 py-8">
        {/* Navigation Tabs */}
        <div className="flex border-b border-slate-800 gap-2 mb-8 overflow-x-auto pb-2">
          {[
            { id: 'overview', label: 'Overview & Rules', icon: Shield },
            { id: 'commands', label: 'Slash Commands', icon: Terminal },
            { id: 'setup', label: 'Phone & Cloud Setup', icon: BookOpen },
            { id: 'catalog', label: 'Catalog & Drafts', icon: Sparkles },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={`flex items-center gap-2 px-4 py-2.5 rounded-lg font-medium text-sm transition-all whitespace-nowrap ${
                  active
                    ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-slate-900'
                }`}
              >
                <Icon className="w-4 h-4" />
                {tab.label}
              </button>
            );
          })}
        </div>

        {/* Tab 1: Overview */}
        {activeTab === 'overview' && (
          <div className="space-y-6">
            <div className="p-6 rounded-2xl bg-slate-900/40 border border-slate-800">
              <h2 className="text-xl font-bold mb-3 text-amber-400">Project Mission & Architecture</h2>
              <p className="text-slate-300 text-sm leading-relaxed mb-4">
                This project is a standalone, production-grade Discord booking bot for Blox Fruit service carries.
                All trade values are calculated in <strong>Millions (M)</strong> of in-game trade value. It requires <strong>zero real-money transactions</strong>,
                collects <strong>zero Roblox account credentials</strong>, and relies strictly on local <strong>SQLite</strong> file persistence.
              </p>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-6">
                <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="text-amber-400 font-semibold text-sm mb-1">Part 3A: Payment Plans</div>
                  <div className="text-xs text-slate-400">
                    Supports <strong>50/50 Split</strong> (50% upfront, 50% on finish) or <strong>One-Time Full</strong> (100% upfront) with exact Decimal rounding guarantees.
                  </div>
                </div>
                <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="text-amber-400 font-semibold text-sm mb-1">Part 3B: In-Game Offers</div>
                  <div className="text-xs text-slate-400">
                    Customers can combine <strong>Fruits</strong>, <strong>Gamepasses</strong>, or both. Trade values are manually verified by authorized staff in Roblox.
                  </div>
                </div>
                <div className="p-4 rounded-xl bg-slate-900/80 border border-slate-800">
                  <div className="text-amber-400 font-semibold text-sm mb-1">Private Staff Threads</div>
                  <div className="text-xs text-slate-400">
                    Every order automatically spawns a dedicated private thread in <code className="text-amber-300">#staff-orders</code> with interactive verification buttons.
                  </div>
                </div>
              </div>
            </div>

            <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/20 flex gap-3 items-start">
              <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-200 leading-relaxed">
                <strong>Zero Web Dashboard Notice:</strong> This web preview acts exclusively as a local reference document and verification harness.
                The bot itself runs independently using <code className="bg-amber-950/60 px-1 py-0.5 rounded text-amber-300">python bot.py</code> and can be deployed directly to Railway, Render, or a VPS with only Python installed.
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Commands */}
        {activeTab === 'commands' && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-amber-400">Integrated Discord Slash Commands</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10">Customer</span>
                <div className="font-mono text-sm text-slate-200">/order</div>
                <p className="text-xs text-slate-400">Opens the category, service selection, and Part 3A/3B payment plan booking form.</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10">Customer</span>
                <div className="font-mono text-sm text-slate-200">/catalog</div>
                <p className="text-xs text-slate-400">Lists all verified services, prerequisites, and 50% deposit amounts in M.</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-emerald-400 px-2 py-0.5 rounded bg-emerald-500/10">Customer</span>
                <div className="font-mono text-sm text-slate-200">/order-status &lt;order_id&gt;</div>
                <p className="text-xs text-slate-400">Checks progress, verified deposit, and remaining balance for your own order.</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-amber-400 px-2 py-0.5 rounded bg-amber-500/10">Admin Only</span>
                <div className="font-mono text-sm text-slate-200">/setup</div>
                <p className="text-xs text-slate-400">Posts the permanent "🛒 Order Now" button in your chosen order channel.</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-indigo-400 px-2 py-0.5 rounded bg-indigo-500/10">Staff</span>
                <div className="font-mono text-sm text-slate-200">/admin-order &lt;order_id&gt;</div>
                <p className="text-xs text-slate-400">Detailed dossier with customer info, verified trade history, and audit log.</p>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 space-y-2">
                <span className="text-xs font-bold text-amber-400 px-2 py-0.5 rounded bg-amber-500/10">Admin Only</span>
                <div className="font-mono text-sm text-slate-200">/edit-price &lt;id&gt; &lt;price&gt; [publish]</div>
                <p className="text-xs text-slate-400">Modifies service prices or activates unconfirmed draft services into the catalog.</p>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: Setup Guide */}
        {activeTab === 'setup' && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-amber-400">Phone-Friendly Deployment Steps</h2>
            <div className="space-y-3">
              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex gap-4">
                <div className="w-8 h-8 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-sm shrink-0">1</div>
                <div>
                  <h3 className="font-semibold text-sm">Discord Developer Portal</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Create application at <span className="text-amber-300">discord.com/developers/applications</span>, enable Server Members intent, and copy your <code className="bg-slate-800 px-1 py-0.5 rounded">DISCORD_BOT_TOKEN</code>.
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex gap-4">
                <div className="w-8 h-8 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-sm shrink-0">2</div>
                <div>
                  <h3 className="font-semibold text-sm">Configure .env Secrets</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Set your <code className="bg-slate-800 px-1 py-0.5 rounded">GUILD_ID</code>, <code className="bg-slate-800 px-1 py-0.5 rounded">ORDER_CHANNEL_ID</code>, <code className="bg-slate-800 px-1 py-0.5 rounded">STAFF_CHANNEL_ID</code>, and <code className="bg-slate-800 px-1 py-0.5 rounded">STAFF_ROLE_ID</code>.
                  </p>
                </div>
              </div>

              <div className="p-4 rounded-xl bg-slate-900/60 border border-slate-800 flex gap-4">
                <div className="w-8 h-8 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center font-bold text-sm shrink-0">3</div>
                <div>
                  <h3 className="font-semibold text-sm">Deploy to Railway (Zero Cost with SQLite Volume)</h3>
                  <p className="text-xs text-slate-400 mt-1">
                    Connect GitHub repo to Railway, add a Persistent Volume mounted at <code className="bg-slate-800 px-1 py-0.5 rounded">/app/data</code>, and Railway runs <code className="bg-slate-800 px-1 py-0.5 rounded">python bot.py</code> 24/7!
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 4: Catalog & Drafts */}
        {activeTab === 'catalog' && (
          <div className="space-y-4">
            <h2 className="text-lg font-bold text-amber-400">Draft & Gated Catalog Review</h2>
            <p className="text-xs text-slate-300">
              The following items are flagged with <code className="bg-slate-800 px-1 py-0.5 rounded text-amber-400">status: "draft"</code> and are strictly hidden from customers until verified by staff:
            </p>
            <div className="divide-y divide-slate-800 border border-slate-800 rounded-xl overflow-hidden bg-slate-900/40 text-xs">
              {[
                { name: '4 Trials (160M)', reason: 'Verify handwritten 160M rate vs volume discount.' },
                { name: 'Tyrant of the Skies (75M)', reason: 'Confirm handwritten 75M price.' },
                { name: 'Cyborg V1 (150M)', reason: 'Confirm if F.O.D. abbreviation stands for Fist of Darkness.' },
                { name: 'PH & PH with magnets (50M/30M)', reason: 'Clarify PH abbreviation (Prehistoric Island or Leviathan Heart).' },
                { name: 'Low Raids (2.5M)', reason: 'Specify eligible basic raid types.' },
                { name: 'Dungeon Hard (50M)', reason: 'Confirm handwritten 50M rate.' },
                { name: '10M Beli (45M)', reason: 'Confirm handwritten conversion rate.' },
              ].map((item, i) => (
                <div key={i} className="p-3 flex items-center justify-between gap-4">
                  <span className="font-semibold text-slate-200">{item.name}</span>
                  <span className="text-slate-400">{item.reason}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
