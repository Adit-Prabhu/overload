// Global spend cap. One ledger object holds today's reserved spend. A request reserves its
// worst-case cost before calling a provider, and is refused once the daily cap is reached.
// This is the real protection: a game client cannot keep secrets, so the server must.

import { DurableObject } from "cloudflare:workers";

interface Ledger {
  day: string;
  reservedUsd: number;
}

export class BudgetLedger extends DurableObject<Env> {
  async reserve(amountUsd: number, capUsd: number): Promise<boolean> {
    const today = new Date().toISOString().slice(0, 10);
    const ledger = (await this.ctx.storage.get<Ledger>("ledger")) ?? { day: today, reservedUsd: 0 };
    const current = ledger.day === today ? ledger.reservedUsd : 0;
    if (current + amountUsd > capUsd) return false;
    await this.ctx.storage.put("ledger", { day: today, reservedUsd: current + amountUsd });
    return true;
  }

  async spent(): Promise<Ledger | undefined> {
    return this.ctx.storage.get<Ledger>("ledger");
  }
}

/** Worst-case cost of one attempt at the configured token ceilings and prices. */
export function worstCaseUsd(env: Env): number {
  const inputPerM = Number(env.INPUT_USD_PER_M ?? 0.3);
  const outputPerM = Number(env.OUTPUT_USD_PER_M ?? 2.5);
  return (1000 * inputPerM + 512 * outputPerM) / 1_000_000;
}
