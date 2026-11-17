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
    if (!(Number.isFinite(amountUsd) && amountUsd > 0 && Number.isFinite(capUsd) && capUsd > 0)) {
      return false; // fail closed on any malformed amount or cap
    }
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

/** Worst-case cost of one live attempt and the daily cap, or null when either is missing or
 *  malformed. A null result refuses the call: the budget fails closed, never open. */
export function liveBudget(env: Env): { costUsd: number; capUsd: number } | null {
  const inputPerM = Number(env.INPUT_USD_PER_M);
  const outputPerM = Number(env.OUTPUT_USD_PER_M);
  const capUsd = Number(env.DAILY_BUDGET_USD);
  const costUsd = (1000 * inputPerM + 512 * outputPerM) / 1_000_000;
  const valid = [inputPerM, outputPerM, capUsd, costUsd].every((v) => Number.isFinite(v) && v > 0);
  return valid ? { costUsd, capUsd } : null;
}
